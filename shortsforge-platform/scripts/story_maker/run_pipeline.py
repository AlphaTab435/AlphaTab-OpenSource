import os
import sys
from pathlib import Path
import json
import argparse
import asyncio
import time

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from scripts.story_maker.script_editor import StoryEditor
from scripts.story_maker.assembler import StoryAssembler
from scripts.story_maker.voice_engine import VoiceEngine
from scripts.story_maker.metrics import PipelineMonitor
from core.database import db

SHORT_MAX_SECONDS = 180

def parse_args():
    parser = argparse.ArgumentParser(description="ShortsForge SLA Pipeline")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed dev-style logging")
    parser.add_argument("--video-dim", type=float, default=-0.15, help="Brightness adjustment for videos (default: -0.15, 0 to disable)")
    parser.add_argument("--thumb-dim", type=float, default=-0.35, help="Brightness adjustment for thumbnails (default: -0.35, 0 to disable)")
    return parser.parse_args()

async def get_active_channels_with_stories():
    """Fetch channels sorted by Quota DESC, then their active stories sorted by Quota DESC."""
    channels_query = """
        SELECT id, name, channel_gen_quota, channel_upload_quota 
        FROM channels 
        WHERE is_active = 1
        ORDER BY channel_gen_quota DESC, id ASC
    """
    ch_rows = await db.fetch_all(channels_query)
    
    active_tree = []
    for c in ch_rows:
        cid, cname, c_gen, c_up = c
        
        stories_query = """
            SELECT id, topic, target_language, protagonist_gender, channel_id, status, assigned_quota, global_hook, bg_image_path, base_description
            FROM story_series 
            WHERE channel_id = ? AND status IN ('pending', 'inProgress') 
            ORDER BY assigned_quota DESC, CASE WHEN status = 'inProgress' THEN 1 ELSE 2 END ASC, id ASC
        """
        st_rows = await db.fetch_all(stories_query, [cid])
        
        if st_rows:
            stories = []
            for row in st_rows:
                s_dict = dict(zip(['id', 'topic', 'target_language', 'protagonist_gender', 'channel_id', 'status', 'assigned_quota', 'global_hook', 'bg_image_path', 'base_description'], row))
                s_dict['channel_name'] = cname
                stories.append(s_dict)
                
            active_tree.append({
                'channel': {'id': cid, 'name': cname, 'channel_gen_quota': c_gen},
                'stories': stories
            })
            
    return active_tree

async def process_series(series: dict, editor: StoryEditor, assembler: StoryAssembler, voice: VoiceEngine, monitor: PipelineMonitor, video_dim: float = -0.15, thumb_dim: float = -0.35) -> str:
    """Processes exactly ONE video for the given series. Returns 'GENERATED', 'PART_COMPLETED', or 'SERIES_COMPLETED'."""
    series_id = series['id']
    topic = series['topic']
    target_language = series.get('target_language', 'en')
    protagonist_gender = series.get('protagonist_gender')
    channel_id = series['channel_id']
    channel_name = series.get('channel_name', 'UnknownChannel')
    global_hook = series['global_hook']
    base_description = series.get('base_description')
    
    safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).lower()
    import re
    safe_topic = re.sub(r'_+', '_', safe_topic).strip('_')[:50]
    
    # 1. Get Channel Name and Voice Config
    channel_row = await db.fetch_one("SELECT name, image_search_style, is_shorts_only, voice_config, visual_mode, allow_internet_images, video_format, enable_heavy_shadows, enable_dark_gradient_box FROM channels WHERE id = ?", [channel_id])
    if not channel_row:
        return "SERIES_COMPLETED"
    channel_name, search_style, is_shorts_only, voice_config_str, visual_mode, allow_internet, video_format, heavy_shadows, dark_gradient_box = channel_row
    is_shorts_only = is_shorts_only or 0
    visual_mode = visual_mode or "classic"
    is_infographic_mode = visual_mode.startswith("infographic")
    if not search_style:
        search_style = "anime illustration digital art"
        
    # Extract Voice and Music Config
    voice_key = "male_narrator"
    music_enabled = True
    subtitle_style = "classic" # Failsafe default for legacy channels
    if voice_config_str:
        try:
            config = json.loads(voice_config_str)
            if isinstance(config, dict):
                if "voices" in config:
                    enable_dynamic = config.get("enable_dynamic_gender", False)
                    lang_config = config["voices"].get(target_language, config["voices"].get("en", {}))
                    if enable_dynamic and protagonist_gender:
                        voice_key = lang_config.get(protagonist_gender, lang_config.get("default", "male_narrator"))
                    else:
                        default_pointer = lang_config.get("default", "male")
                        voice_key = lang_config.get(default_pointer, "male_narrator")
                if "music" in config:
                    music_enabled = config["music"]
                if "subtitle_style" in config:
                    subtitle_style = config["subtitle_style"]
        except Exception as e:
            print(f"CRITICAL ERROR parsing voice_config for {channel_name}: {e}\nRaw DB string: {voice_config_str!r}")
            
    sub_dir = f"{channel_name}/{safe_topic}"
        
    # 2. Get active part
    part_row = await db.fetch_one("""
        SELECT id, file_path, sequence_order, chunk_progress, total_chunks, shorts_generated 
        FROM story_parts 
        WHERE series_id = ? AND status IN ('pending', 'inProgress') 
        ORDER BY CASE WHEN status = 'inProgress' THEN 1 ELSE 2 END ASC, sequence_order ASC LIMIT 1
    """, [series_id])
    
    if not part_row:
        return "SERIES_COMPLETED" # Series has no active parts left
        
    part_id, file_path_str, seq_order, chunk_progress, total_chunks, shorts_generated = part_row
    
    file_path = Path("data/raw_stories") / file_path_str
    if not file_path.exists():
        print(f"ERROR: File {file_path} not found.")
        await db.execute("UPDATE story_parts SET status = 'completed' WHERE id = ?", [part_id])
        return "PART_COMPLETED" # Skip to next part without burning quota
        
    # 3. Read Raw Text
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read().strip()
        
    # Parse Optional Passthrough Metadata
    meta_json = {}
    meta_path = file_path.parent / "meta.json"
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_json = json.load(f)
        except Exception as e:
            print(f"[{topic}] WARNING: Could not parse meta.json: {e}")
            
    # Check for Safe AI Bypass Flag
    bypass_ai_grammar = meta_json.get("bypass_ai_grammar", False)
    if bypass_ai_grammar:
        print(f"[{topic}] Safe AI Mode: Bypassing grammar edits, using Sanitization Prompt.")

    # 4. Global Hook Extraction & Gender Detection (Once per series)
    if not global_hook:
        if meta_json.get("hook"):
            hook_text = meta_json["hook"]
            if target_language == "ur":
                print(f"[{topic}] Translating manual hook to Roman Urdu...")
                global_hook = await editor.translate_hook_to_roman_urdu(hook_text)
            else:
                global_hook = hook_text
            print(f"[{topic}] Using Global Hook from meta.json")
        else:
            print(f"[{topic}] Extracting Global Hook for series...")
            global_hook = await editor.extract_global_hook(raw_text, fallback_topic=topic, target_language=target_language)
        await db.execute("UPDATE story_series SET global_hook = ? WHERE id = ?", [global_hook, series_id])
        series['global_hook'] = global_hook
        
    if not protagonist_gender:
        print(f"[{topic}] Detecting Protagonist Gender (Language-Agnostic)...")
        protagonist_gender = await editor.detect_gender(raw_text)
        await db.execute("UPDATE story_series SET protagonist_gender = ? WHERE id = ?", [protagonist_gender, series_id])
        series['protagonist_gender'] = protagonist_gender
        
        # Re-resolve voice if dynamic is enabled and we just detected gender
        if voice_config_str:
            try:
                config = json.loads(voice_config_str)
                if isinstance(config, dict) and "voices" in config:
                    enable_dynamic = config.get("enable_dynamic_gender", False)
                    lang_config = config["voices"].get(target_language, config["voices"].get("en", {}))
                    if enable_dynamic and protagonist_gender:
                        voice_key = lang_config.get(protagonist_gender, lang_config.get("default", "male_narrator"))
            except Exception:
                pass
        
    # 4.2. Global Base Description Extraction (Once per series)
    if not base_description:
        if meta_json.get("description"):
            base_description = meta_json["description"]
            print(f"[{topic}] Using Base Description from meta.json")
        else:
            print(f"[{topic}] Extracting Base YouTube Description for series...")
            base_description = await editor.extract_description(raw_text)
        await db.execute("UPDATE story_series SET base_description = ? WHERE id = ?", [base_description, series_id])
        series['base_description'] = base_description
        
    # 4.5. Global Background Image Selection (Once per series)
    bg_image_path = series.get('bg_image_path')
    if bg_image_path and not Path(bg_image_path).exists():
        print(f"[{topic}] Cached background image missing from disk. Will re-download.")
        bg_image_path = None
        await db.execute("UPDATE story_series SET bg_image_path = NULL WHERE id = ?", [series_id])
    
    if not bg_image_path and not is_infographic_mode:
        if allow_internet == 1:
            print(f"[{topic}] Fetching Primary Background Image for series using Safe Query...")
            safe_query = await editor.extract_safe_background_query(raw_text, fallback_topic=topic)
            bg_image_path = assembler.media.fetch_internet_image(safe_query, style=search_style, sub_dir=sub_dir)
            if bg_image_path:
                print("[MEDIA] Successfully downloaded internet image.")
        else:
            print(f"[{topic}] Safe Mode ON (allow_internet_images=0). Bypassing DuckDuckGo.")
            bg_image_path = None
            
        if not bg_image_path:
            print("[MEDIA] Internet search failed or bypassed. FALLBACK: Fetching channel static image.")
            bg_image_path = assembler.media.get_static_image(channel_name=channel_name)
            if not bg_image_path:
                print("[MEDIA] Channel static image not found. FALLBACK: Fetching global static image.")
                bg_image_path = assembler.media.get_static_image(channel_name=None)
            
        await db.execute("UPDATE story_series SET bg_image_path = ? WHERE id = ?", [bg_image_path, series_id])
        series['bg_image_path'] = bg_image_path
        
    # Determine total parts across ALL .txt files in this series to decide if "Part X" is needed
    total_series_chunks_row = await db.fetch_one("""
        SELECT SUM(total_chunks) FROM story_parts WHERE series_id = ?
    """, [series_id])
    total_series_parts = total_series_chunks_row[0] if total_series_chunks_row[0] else 1
    # Also count how many .txt files exist (even if not yet chunked, they imply more parts)
    total_files_row = await db.fetch_one("""
        SELECT COUNT(*) FROM story_parts WHERE series_id = ?
    """, [series_id])
    total_files = total_files_row[0] if total_files_row[0] else 1
    has_multiple_parts = total_series_parts > 1 or total_files > 1
    
    # 5. Upfront Shorts Generation (Bypass & Dynamic Scaling)
    if not shorts_generated:
        if is_shorts_only:
            # Bypass upfront generation for shorts-only channels (they use sequential mathematical chunker)
            print(f"[{topic}] is_shorts_only channel. Bypassing upfront random trailer extraction.")
            await db.execute("UPDATE story_parts SET shorts_generated = 1 WHERE id = ?", [part_id])
            shorts_generated = 1
        else:
            print(f"[{topic}] Extracting Shorts/Trailers upfront...")
            trailers = await editor.extract_shorts(raw_text, count=3, target_language=target_language)
            
            for t_idx, trailer_script in enumerate(trailers, 1):
                is_standalone = len(raw_text.split()) < 375
                
                # Title Truncation Logic (100 char limit)
                lang_prefix = f"[{'Hindi/Urdu' if target_language == 'ur' else 'English'}] "
                suffix = " #shorts"
                max_base_len = 100 - len(suffix) - len(lang_prefix)
                if meta_json.get("title"):
                    base_title = meta_json["title"]
                else:
                    clean_topic = topic[:-3] if topic.endswith((" EN", " UR")) else topic
                    base_title = clean_topic if global_hook.lower() == clean_topic.lower() else f"{global_hook} | {clean_topic}"
                
                if len(base_title) > max_base_len:
                    base_title = base_title[:max_base_len - 3].strip() + "..."
                short_title = f"{lang_prefix}{base_title}{suffix}"
                
                lang_full = 'Urdu' if target_language == 'ur' else 'English'
                thumb_text = f"[{lang_full}] {global_hook}"
                spoken_trailer = f"{global_hook}. {trailer_script}"
                if not is_standalone:
                    spoken_trailer += " Watch the full story on our channel, link in description!"
                    visual_cta = "Full Story in Description!"
                else:
                    spoken_trailer += " Like, comment & subscribe for more!"
                    visual_cta = "Like & Subscribe!"
                    
                print(f"\n--- Generating Short Video ({t_idx}/{len(trailers)}) ---")
                
                if visual_mode == "dynamic":
                    print(f"[{topic}] Dynamic Mode Activated for Short {t_idx}: Extracting scenes...")
                    dynamic_scenes = await editor.split_into_dynamic_scenes(spoken_trailer)
                    video_path, thumbnail_path = assembler.build_dynamic_part(
                        title=short_title,
                        dynamic_scenes=dynamic_scenes,
                        part_num=seq_order,
                        is_last=True,
                        total_parts=total_chunks if total_chunks > 0 else 1,
                        channel_name=channel_name,
                        topic=topic,
                        has_multiple_parts=has_multiple_parts,
                        video_dim=video_dim,
                        thumb_dim=thumb_dim,
                        is_short=True,
                        voice_override=voice_key,
                        music_enabled=music_enabled,
                        subtitle_style=subtitle_style,
                        video_format=video_format,
                        enable_heavy_shadows=heavy_shadows,
                        enable_dark_gradient_box=dark_gradient_box,
                        cta=visual_cta,
                        max_duration=SHORT_MAX_SECONDS,
                        trailer_idx=t_idx,
                        hook=thumb_text
                    )
                elif is_infographic_mode:
                    print(f"[{topic}] Infographic Mode Activated for Short {t_idx}: Generating layout...")
                    ai_config = await editor.split_into_infographic_scenes(spoken_trailer, video_format)
                    video_path, thumbnail_path = await assembler.build_infographic_part(
                        title=short_title,
                        ai_config=ai_config,
                        part_num=seq_order,
                        is_last=True,
                        total_parts=total_chunks if total_chunks > 0 else 1,
                        channel_name=channel_name,
                        topic=topic,
                        has_multiple_parts=has_multiple_parts,
                        video_dim=video_dim,
                        thumb_dim=thumb_dim,
                        visual_mode=visual_mode,
                        is_short=True,
                        voice_override=voice_key,
                        music_enabled=music_enabled,
                        subtitle_style=subtitle_style,
                        video_format=video_format,
                        enable_heavy_shadows=heavy_shadows,
                        enable_dark_gradient_box=dark_gradient_box,
                        cta=visual_cta,
                        max_duration=SHORT_MAX_SECONDS,
                        trailer_idx=t_idx,
                        hook=thumb_text,
                        bg_image_path=bg_image_path
                    )
                else:
                    audio_path, srt_path = voice.generate_audio(spoken_trailer, f"{safe_topic}_short_{seq_order}_{t_idx}", sub_dir=sub_dir, voice_override=voice_key, subtitle_style=subtitle_style)
                    
                    if not audio_path or not srt_path:
                        print(f"[{topic}] Short {t_idx} audio generation failed. Skipping.")
                        continue
                        
                    video_path, thumbnail_path = assembler.build_short_story(
                        title=short_title,
                        audio_path=audio_path,
                        subtitle_path=srt_path,
                        max_duration=SHORT_MAX_SECONDS,
                        cta=visual_cta,
                        force_bg_type="video",
                        hook=thumb_text,
                        channel_name=channel_name,
                        search_style=search_style,
                        bg_image_path=bg_image_path,
                        topic=topic,
                        part_num=seq_order,
                        trailer_idx=t_idx,
                        has_multiple_parts=has_multiple_parts,
                        video_dim=video_dim,
                        thumb_dim=thumb_dim,
                        music_enabled=music_enabled,
                        subtitle_style=subtitle_style,
                        video_format=video_format,
                        enable_heavy_shadows=heavy_shadows,
                        enable_dark_gradient_box=dark_gradient_box
                    )
                
                if video_path:
                    await db.execute(
                        "INSERT INTO videos (series_id, part_id, video_path, youtube_url, thumbnail_path, title, is_short) VALUES (?, ?, ?, NULL, ?, ?, 1)",
                        [series_id, part_id, video_path, thumbnail_path, short_title]
                    )
                
            await db.execute("UPDATE story_parts SET shorts_generated = 1 WHERE id = ?", [part_id])
            shorts_generated = 1
            
            if len(raw_text.split()) < 375:
                print(f"[{topic}] Standalone Short generated. Bypassing long video logic.")
                await db.execute("UPDATE story_parts SET status = 'completed' WHERE id = ?", [part_id])
                return "GENERATED" # Skip long video generation entirely
            
    # 6. Dual-Key JSON Cache (Mathematical Pre-Chunking for Long Videos)
    cache_file = file_path.with_name(file_path.name + "_compiled.json")
    if not cache_file.exists() or total_chunks == 0:
        if is_shorts_only:
            print(f"[{topic}] Shorts-Only Mode: Performing Balanced Pre-Chunking on {file_path.name}...")
            chunks = editor.pre_chunk_mathematically(raw_text, target_mins=2.5, min_mins=1, balanced=True)
        else:
            print(f"[{topic}] Performing Mathematical Pre-Chunking on {file_path.name}...")
            chunks = editor.pre_chunk_mathematically(raw_text, target_mins=60, min_mins=30)
            
        total_chunks = len(chunks)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2)
        await db.execute("UPDATE story_parts SET total_chunks = ?, status = 'inProgress' WHERE id = ?", [total_chunks, part_id])
    else:
        with open(cache_file, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            
    if chunk_progress >= total_chunks and total_chunks > 0:
        # Part is completely finished generating long videos.
        await db.execute("UPDATE story_parts SET status = 'completed' WHERE id = ?", [part_id])
        return "PART_COMPLETED" # Did not generate anything, just flipped status
        
    # Fetch the exact chunk to process
    current_chunk = chunks[chunk_progress]
    
    # Check if AI processing is needed
    if current_chunk["ai_text"] is None:
        print(f"[{topic}] JIT AI Processing for Part {seq_order}, Chunk {chunk_progress+1}...")
        ai_edited = await editor.process_ai_grammar(current_chunk["raw_text"], bypass_grammar=bypass_ai_grammar, target_language=target_language)
        current_chunk["ai_text"] = ai_edited
        current_chunk["status"] = "completed"
        # Save cache immediately
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2)
            
    # Assembly Formatting
    script_text = current_chunk["ai_text"]
    
    # Calculate Global Part Number across all .txt files
    prev_chunks_row = await db.fetch_one("""
        SELECT SUM(total_chunks) FROM story_parts 
        WHERE series_id = ? AND sequence_order < ?
    """, [series_id, seq_order])
    prev_chunks = prev_chunks_row[0] if prev_chunks_row[0] else 0
    
    global_part_id = prev_chunks + chunk_progress + 1
    
    is_last_chunk_in_file = (chunk_progress == total_chunks - 1)
    is_last_file_in_series = (seq_order == total_files)
    is_last = is_last_chunk_in_file and is_last_file_in_series
    
    # Recompute has_multiple_parts locally using the updated total_chunks
    has_multiple_parts = total_chunks > 1 or total_files > 1
    
    if has_multiple_parts:
        suffix = f" (Part {global_part_id})"
        if global_part_id == 1:
            spoken_text = f"{global_hook}. Part 1. {script_text}"
        else:
            if is_shorts_only:
                spoken_text = f"{global_hook}. Part {global_part_id}. {script_text}"
            else:
                spoken_text = f"Part {global_part_id}. {script_text}"
        hook_label = f"{global_hook} (Part {global_part_id})"
    else:
        suffix = ""
        spoken_text = f"{global_hook}. {script_text}"
        hook_label = global_hook
        
    # Title Truncation Logic (100 char limit)
    lang_prefix = f"[{'Hindi/Urdu' if target_language == 'ur' else 'English'}] "
    shorts_suffix = " #shorts" if is_shorts_only else ""
    max_base_len = 100 - len(suffix) - len(shorts_suffix) - len(lang_prefix)
    
    if meta_json.get("title"):
        base_title = meta_json["title"]
    else:
        clean_topic = topic[:-3] if topic.endswith((" EN", " UR")) else topic
        base_title = clean_topic if global_hook.lower() == clean_topic.lower() else f"{global_hook} | {clean_topic}"
        
    if len(base_title) > max_base_len:
        base_title = base_title[:max_base_len - 3].strip() + "..."
        
    long_title = f"{lang_prefix}{base_title}{suffix}{shorts_suffix}".strip()
    
    # Prepend full language tag to thumbnail hook
    lang_full = 'Urdu' if target_language == 'ur' else 'English'
    hook_label = f"[{lang_full}] {hook_label}"
        
    print(f"\n--- Assembling Video: {topic} (Global Part {global_part_id}) ---")
    
    # Update chunk with formatted audio text
    chunk_dict = {"text": spoken_text, "chunk_id": global_part_id} 
    
    monitor.start_stage("Video Assembly")
    
    if visual_mode == "dynamic":
        print(f"[{topic}] Dynamic Mode Activated: Extracting scene-by-scene visuals...")
        dynamic_scenes = await editor.split_into_dynamic_scenes(script_text)
        video_path, thumbnail_path = assembler.build_dynamic_part(
            title=long_title, 
            dynamic_scenes=dynamic_scenes,
            part_num=global_part_id,
            is_last=is_last,
            total_parts=total_chunks,
            channel_name=channel_name,
            topic=topic,
            has_multiple_parts=has_multiple_parts,
            is_short=is_shorts_only,
            video_dim=video_dim,
            thumb_dim=thumb_dim,
            voice_override=voice_key,
            music_enabled=music_enabled,
            subtitle_style=subtitle_style,
            video_format=video_format,
            enable_heavy_shadows=heavy_shadows,
            enable_dark_gradient_box=dark_gradient_box,
            hook=hook_label
        )
    elif is_infographic_mode:
        print(f"[{topic}] Infographic Mode Activated: Extracting layout...")
        ai_config = await editor.split_into_infographic_scenes(script_text, video_format)
        video_path, thumbnail_path = await assembler.build_infographic_part(
            title=long_title, 
            ai_config=ai_config,
            part_num=global_part_id,
            is_last=is_last,
            total_parts=total_chunks,
            channel_name=channel_name,
            topic=topic,
            has_multiple_parts=has_multiple_parts,
            is_short=is_shorts_only,
            video_dim=video_dim,
            thumb_dim=thumb_dim,
            visual_mode=visual_mode,
            voice_override=voice_key,
            music_enabled=music_enabled,
            subtitle_style=subtitle_style,
            video_format=video_format,
            enable_heavy_shadows=heavy_shadows,
            enable_dark_gradient_box=dark_gradient_box,
            hook=hook_label,
            bg_image_path=bg_image_path
        )
    else:
        video_path, thumbnail_path = assembler.build_part(
            title=long_title, 
            chunk=chunk_dict, 
            is_last=is_last, 
            total_parts=total_chunks, 
            force_bg_type="video", 
            hook=hook_label,
            channel_name=channel_name, 
            search_style=search_style,
            bg_image_path=bg_image_path,
            topic=topic,
            has_multiple_parts=has_multiple_parts,
            is_short=is_shorts_only,
            video_dim=video_dim,
            thumb_dim=thumb_dim,
            voice_override=voice_key,
            music_enabled=music_enabled,
            subtitle_style=subtitle_style,
            video_format=video_format,
            enable_heavy_shadows=heavy_shadows,
            enable_dark_gradient_box=dark_gradient_box
        )
    
    monitor.end_stage()
    
    if not video_path:
        print(f"[{topic}] Part {global_part_id} video assembly failed (possible network error). Skipping.")
        return "FAILED"
    
    # Save to Videos Table
    is_short_val = 1 if is_shorts_only else 0
    await db.execute(
        "INSERT INTO videos (series_id, part_id, video_path, youtube_url, thumbnail_path, title, is_short) VALUES (?, ?, ?, NULL, ?, ?, ?)",
        [series_id, part_id, video_path, thumbnail_path, long_title, is_short_val]
    )
    
    # Increment Progress
    new_progress = chunk_progress + 1
    await db.execute("UPDATE story_parts SET chunk_progress = ? WHERE id = ?", [chunk_progress + 1, part_id])
    return "GENERATED"

async def main():
    args = parse_args()
    print("=== ShortsForge SLA Pipeline ===")
    
    optimized_chain = ["groq", "gemini", "cerebras"]
    editor = StoryEditor(custom_fallback_chain=optimized_chain)
    assembler = StoryAssembler()
    voice = VoiceEngine()
    monitor = PipelineMonitor()
    
    # 1. Fetch Master Global Quota
    global_row = await db.fetch_one("SELECT global_gen_quota FROM global_settings WHERE id = 1")
    if not global_row or global_row[0] <= 0:
        print("[INFO] Global Gen Quota is 0. Nothing to do. Exiting.")
        await db.close()
        return
        
    global_quota = global_row[0]
    
    # 2. Fetch Channel-First Active Tree
    try:
        active_tree = await get_active_channels_with_stories()
        generated_count = 0
        channel_run_counts = {}
        story_run_counts = {}
        
        while active_tree and generated_count < global_quota:
            # Pick the highest priority channel
            current_channel_node = active_tree[0]
            channel = current_channel_node['channel']
            stories = current_channel_node['stories']
            
            # If no stories left, the channel is exhausted
            if not stories:
                print(f"[{channel['name']}] Channel exhausted (no active stories). Auto-resetting.")
                # await db.execute("UPDATE channels SET channel_gen_quota = 0, channel_upload_quota = 0 WHERE id = ?", [channel['id']])
                active_tree.pop(0)
                continue
                
            # Pick highest priority story in channel
            series = stories.pop(0)
            
            if args.verbose:
                print(f"\n[DEBUG] Pipeline Step:")
                print(f"  -> Global Quota: {generated_count}/{global_quota}")
                print(f"  -> Selected Channel: {channel['name']} (ID: {channel['id']}) | Channel Gen Quota: {channel['channel_gen_quota']}")
                print(f"  -> Selected Story: {series['topic']} (ID: {series['id']}) | Status: {series['status']} | Story Quota: {series['assigned_quota']}")
    
            # Work loop step
            monitor.start_run(series['topic'])
            status_result = await process_series(series, editor, assembler, voice, monitor, args.video_dim, args.thumb_dim)
            monitor.end_run(status_result)
            
            if status_result == "GENERATED":
                generated_count += 1
                channel_run_counts[channel['id']] = channel_run_counts.get(channel['id'], 0) + 1
                story_run_counts[series['id']] = story_run_counts.get(series['id'], 0) + 1
                
                # Transition status from pending -> inProgress
                if series['status'] == 'pending':
                    await db.execute("UPDATE story_series SET status = 'inProgress' WHERE id = ?", [series['id']])
                    series['status'] = 'inProgress'
                    if args.verbose:
                        print(f"[DEBUG] DB Update: Story {series['id']} status changed from pending -> inProgress")
                
                initial_ch_quota = channel['channel_gen_quota']
                initial_st_quota = series['assigned_quota']
                
                # Requeue logic based on explicit quota eviction
                if initial_ch_quota > 0 and channel_run_counts[channel['id']] >= initial_ch_quota:
                    print(f"[{channel['name']}] Channel explicit priority limit ({initial_ch_quota}) reached for this run. Evicting from queue.")
                    active_tree.pop(0)
                elif initial_st_quota > 0 and story_run_counts[series['id']] >= initial_st_quota:
                    print(f"[{series['topic']}] Story explicit priority limit ({initial_st_quota}) reached for this run. Evicting from queue.")
                    # We don't re-insert, effectively evicting it
                else:
                    # Either it still has priority left, OR it was already a default (0) node. Re-insert at front.
                    stories.insert(0, series)
                    
            elif status_result == "PART_COMPLETED":
                # We didn't generate a video, just flipped a part to completed. Re-insert to process next part instantly without burning quota.
                stories.insert(0, series)
            elif status_result == "FAILED":
                # Network or generation error. Evict from queue but keep status as inProgress.
                print(f"[{series['topic']}] Pipeline step failed. Evicting from queue for this run.")
            else:
                # Series completely exhausted text
                print(f"[{series['topic']}] Series Completed. Revoking Quota.")
                await db.execute("UPDATE story_series SET status = 'completed', assigned_quota = 0 WHERE id = ?", [series['id']])
                if args.verbose:
                    print(f"[DEBUG] DB Update: Story {series['id']} status changed to completed")
                
        print(f"\n=== Pipeline Complete ({generated_count} videos generated) ===")
        if generated_count >= global_quota:
            print(f"[INFO] Reached Global Gen Limit ({global_quota}). Pipeline halted.")
    finally:
        await db.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Pipeline forcefully stopped by user (Ctrl+C). Exiting cleanly.")
        os._exit(0)
