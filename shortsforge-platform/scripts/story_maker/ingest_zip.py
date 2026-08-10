import os
import sys
import time
import zipfile
import shutil
import tempfile
import asyncio
import re
import argparse
from pathlib import Path

# Add project root to path so we can import core
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.database import db

RAW_STORIES_DIR = Path("data/raw_stories")

def extract_sequence(filename: str) -> int:
    """Extracts integer from filename for sequence ordering (e.g. 2.txt -> 2)"""
    match = re.search(r'\d+', filename)
    return int(match.group()) if match else 999

async def main():
    parser = argparse.ArgumentParser(description="Ingest zipped stories into ShortsForge.")
    parser.add_argument("zip_path", help="Path to the zip file to ingest.")
    parser.add_argument("--auto", action="store_true", help="Run automatically, skipping all duplicates without prompting.")
    args = parser.parse_args()

    zip_path = Path(args.zip_path)
    is_auto = args.auto
    
    if not zip_path.exists():
        print(f"ERROR: Zip file not found at {zip_path}")
        sys.exit(1)

    print(f"=== ShortsForge Ingestion Tool ===")
    print(f"Source: {zip_path}")
    
    # 1. Create temp directory and extract
    temp_dir = Path(tempfile.mkdtemp(prefix="shortsforge_ingest_"))
    print(f"Temporary extraction workspace: {temp_dir}")
    print(f"Extracting zip contents...")
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
        # 2. Find all text files
        print("Verifying contents against database...")
        all_files = []
        
        # We expect the zip to have structure: Channel_Name/Story_Name/file.txt
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith(".txt"):
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(temp_dir)
                    source_file_str = str(rel_path).replace("\\", "/")
                    
                    parts = rel_path.parts
                    topic = parts[-2] if len(parts) >= 2 else parts[0]
                    channel_name = parts[-3] if len(parts) >= 3 else "default_channel"
                    sequence_order = extract_sequence(file)
                    
                    all_files.append({
                        "temp_path": file_path,
                        "rel_path": rel_path,
                        "source_file_str": source_file_str,
                        "file_name": file,
                        "topic": topic,
                        "channel_name": channel_name,
                        "sequence_order": sequence_order
                    })

        # Sort files naturally
        all_files.sort(key=lambda x: (x["channel_name"], x["topic"], x["sequence_order"]))

        if not all_files:
            print("No .txt files found in the zip archive.")
            return

        # --- Pre-Execution Validation against DB ---
        valid_files = []
        overwrites = []
        missing_channels = set()
        
        for f in all_files:
            # Check Channel
            channel_row = await db.fetch_one("SELECT id, language_pair FROM channels WHERE name = ?", [f["channel_name"]])
            if not channel_row:
                missing_channels.add(f["channel_name"])
                continue
                
            channel_id = channel_row[0]
            language_pair = channel_row[1] if channel_row[1] else "en"
            f["channel_id"] = channel_id
            
            target_langs = language_pair.split(",")
            for lang in target_langs:
                f_lang = dict(f)
                f_lang["target_language"] = lang
                if len(target_langs) > 1:
                    new_topic = f"{f['topic']} {lang.upper()}"
                    f_lang["topic"] = new_topic
                    parts = list(f_lang["rel_path"].parts)
                    if len(parts) >= 2:
                        parts[-2] = new_topic
                    f_lang["rel_path"] = Path(*parts)
                    f_lang["source_file_str"] = str(f_lang["rel_path"]).replace("\\", "/")
                
                # Check if Story Part already exists (Duplicate/Overwrite)
                series_row = await db.fetch_one("SELECT id FROM story_series WHERE topic = ? AND channel_id = ? AND target_language = ?", [f["topic"], channel_id, lang])
                if series_row:
                    series_id = series_row[0]
                    part_row = await db.fetch_one("SELECT id FROM story_parts WHERE series_id = ? AND file_path = ?", [series_id, f_lang["source_file_str"]])
                    if part_row:
                        overwrites.append(f_lang)
                        valid_files.append(f_lang)
                        continue
                        
                valid_files.append(f_lang)

        # Display Validation Results
        print(f"\n--- Validation Results ---")
        print(f"Total Text Files Found: {len(all_files)}")
        print(f"Valid Files to Ingest: {len(valid_files)}")
        
        if missing_channels:
            print(f"\n[WARNING] The following channels were NOT FOUND in the database. Their files will be skipped:")
            print("  -> Please create them with 'python scripts/add_channel.py' before ingesting.")
            for ch in missing_channels:
                print(f"  - {ch}")
                
        if overwrites:
            print(f"\n[WARNING] The following files are DUPLICATES and already exist:")
            for f in overwrites:
                print(f"  - {f['source_file_str']}")

        print("\n")
        
        # Granular Overwrite Confirmation
        final_valid_files = []
        yes_to_all = False
        skip_all = is_auto
        
        if is_auto and overwrites:
            print("[AUTO MODE] Skipping all duplicates automatically.")
        
        for f in valid_files:
            if f in overwrites:
                if skip_all:
                    continue
                if not yes_to_all:
                    resp = input(f"Overwrite '{f['source_file_str']}'? [y/n/a/s] (a=all, s=skip all): ").strip().lower()
                    if resp == 'a':
                        yes_to_all = True
                    elif resp == 's':
                        skip_all = True
                        continue
                    elif resp != 'y':
                        continue
            
            final_valid_files.append(f)
            
        valid_files = final_valid_files
        
        if not valid_files:
            print("No files to ingest. Cancelled.")
            return
            
        # Extract and copy any .json metadata files (like meta.json passthrough)
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith(".json"):
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(temp_dir)
                    parts = rel_path.parts
                    channel_name = parts[-3] if len(parts) >= 3 else "default_channel"
                    topic = parts[-2] if len(parts) >= 2 else parts[0]
                    
                    channel_row = await db.fetch_one("SELECT language_pair FROM channels WHERE name = ?", [channel_name])
                    language_pair = channel_row[0] if channel_row and channel_row[0] else "en"
                    target_langs = language_pair.split(",")
                    
                    for lang in target_langs:
                        if len(target_langs) > 1:
                            new_topic = f"{topic} {lang.upper()}"
                            new_parts = list(parts)
                            if len(new_parts) >= 2:
                                new_parts[-2] = new_topic
                            dest_rel_path = Path(*new_parts)
                        else:
                            dest_rel_path = rel_path
                            
                        dest_path = RAW_STORIES_DIR / dest_rel_path
                        os.makedirs(dest_path.parent, exist_ok=True)
                        shutil.copy(str(file_path), str(dest_path))
                        print(f"  -> Copied metadata file: {dest_rel_path}")
        
        # 3. Execution Phase
        print("\n--- Execution Phase ---")
        moved_count = 0
        
        for f in valid_files:
            channel_name = f["channel_name"]
            channel_id = f["channel_id"]
            topic = f["topic"]
            target_language = f["target_language"]
            file_path_str = f["source_file_str"]
            seq_order = f["sequence_order"]
            
            # Ensure destination directory exists
            dest_path = RAW_STORIES_DIR / f["rel_path"]
            os.makedirs(dest_path.parent, exist_ok=True)
            
            # Copy file (using copy because temp file might be needed again for 2nd language)
            shutil.copy(str(f["temp_path"]), str(dest_path))
            moved_count += 1
            
            # Database Operations
            # 1. Resolve Channel (Channel ID already retrieved in validation)
            # 2. Resolve Story Series (Folder)
            series_row = await db.fetch_one("SELECT id, status FROM story_series WHERE topic = ? AND channel_id = ? AND target_language = ?", [topic, channel_id, target_language])
            if series_row:
                series_id = series_row[0]
                series_status = series_row[1]
                # Serial Rule: If adding a file to a completed folder, bump it to inProgress
                if series_status == 'completed':
                    await db.execute("UPDATE story_series SET status = 'inProgress' WHERE id = ?", [series_id])
                    print(f"  -> Bumped series '{topic}' status to inProgress")
            else:
                # Create new series
                await db.execute(
                    "INSERT INTO story_series (workspace_id, channel_id, topic, target_language, status, assigned_quota) VALUES (?, ?, ?, ?, 'pending', 0)",
                    ['default_workspace', channel_id, topic, target_language]
                )
                # Fetch the new auto-incremented ID
                series_row = await db.fetch_one("SELECT id FROM story_series WHERE topic = ? AND channel_id = ? AND target_language = ?", [topic, channel_id, target_language])
                series_id = series_row[0]
                print(f"  -> Created new series Folder: {topic} ({target_language})")

            # 3. Resolve Story Part (File)
            part_row = await db.fetch_one("SELECT id, sequence_order FROM story_parts WHERE series_id = ? AND file_path = ?", [series_id, file_path_str])
            
            if part_row:
                # Overwrite logic (Cascading Reset)
                part_id = part_row[0]
                existing_seq = part_row[1]
                
                print(f"Overwriting duplicate: {file_path_str}")
                
                # Reset this specific part
                await db.execute(
                    "UPDATE story_parts SET status = 'pending', chunk_progress = 0, total_chunks = 0, shorts_generated = 0 WHERE id = ?",
                    [part_id]
                )
                cache_file = dest_path.with_name(dest_path.name + "_compiled.json")
                if cache_file.exists():
                    cache_file.unlink()
                    
                # Aggressively purge TEMP media for this story to prevent stale cache reuse
                import re
                safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).lower()
                safe_topic = re.sub(r'_+', '_', safe_topic).strip('_')[:50]
                audio_dir = Path("data/audio_temp") / channel_name / safe_topic
                video_dir = Path("data/video_temp") / channel_name / safe_topic
                
                for d in [audio_dir, video_dir]:
                    if d.exists():
                        shutil.rmtree(str(d), ignore_errors=True)
                        print(f"  -> Purged stale cache: {d}")
                    
                # CASCADE RESET to subsequent parts
                cascaded_parts = await db.fetch_all("SELECT id, file_path FROM story_parts WHERE series_id = ? AND sequence_order > ?", [series_id, existing_seq])
                for c_part in cascaded_parts:
                    c_part_id = c_part[0]
                    c_file_path = c_part[1]
                    await db.execute(
                        "UPDATE story_parts SET status = 'pending', chunk_progress = 0, total_chunks = 0, shorts_generated = 0 WHERE id = ?",
                        [c_part_id]
                    )
                    # Delete cascaded part's json cache
                    c_dest_path = RAW_STORIES_DIR / c_file_path
                    c_cache_file = c_dest_path.with_name(c_dest_path.name + "_compiled.json")
                    if c_cache_file.exists():
                        c_cache_file.unlink()
                    print(f"  -> Cascaded Reset to subsequent part: {c_file_path}")
            else:
                # Insert new part
                await db.execute(
                    "INSERT INTO story_parts (series_id, file_path, sequence_order, status, chunk_progress, total_chunks, shorts_generated) VALUES (?, ?, ?, 'pending', 0, 0, 0)",
                    [series_id, file_path_str, seq_order]
                )
                print(f"Registered new file part: {file_path_str}")

        print("\n=== Ingestion Complete ===")
        print(f"Files Processed: {moved_count}")
        
    except (KeyboardInterrupt, EOFError):
        print("\n\n[!] Ingestion cancelled by user (Ctrl+C).")
    except Exception as e:
        print(f"\n[!] An error occurred during ingestion: {e}")
    finally:
        # 4. Cleanup Guarantee
        print("\n--- Cleanup ---")
        if temp_dir.exists():
            print("Removing temporary extraction data...")
            shutil.rmtree(temp_dir)
        
        if zip_path.exists():
            print(f"Removing original zip file: {zip_path.name}...")
            try:
                os.remove(zip_path)
            except Exception as e:
                print(f"Warning: Could not remove zip file automatically: {e}")
                
        # Ensure background thread closes so script exits
        try:
            await db.close()
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        os._exit(0)
