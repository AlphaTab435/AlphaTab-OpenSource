import os
import sys
import shutil
import asyncio
import argparse
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.database import db

def parse_args():
    parser = argparse.ArgumentParser(description="ShortsForge Delete Story Utility")
    parser.add_argument("story_id", type=int, help="The ID of the story_series to completely delete.")
    return parser.parse_args()

async def main():
    args = parse_args()
    await db.connect()
    
    story_id = args.story_id
    
    # 1. Fetch story details
    story_row = await db.fetch_one("""
        SELECT s.topic, c.name 
        FROM story_series s
        JOIN channels c ON s.channel_id = c.id
        WHERE s.id = ?
    """, [story_id])
    
    if not story_row:
        print(f"ERROR: Story series {story_id} not found.")
        await db.close()
        return
        
    topic, channel_name = story_row
    
    # Format safe names for folders
    safe_title = "".join([c if c.isalnum() else "_" for c in topic]).lower()
    safe_channel = channel_name if channel_name else "UnknownChannel"
    
    print(f"WARNING: You are about to completely delete Story {story_id}: '{topic}' (Channel: {channel_name})")
    confirm = input("Type 'YES' to confirm deletion: ")
    if confirm != 'YES':
        print("Deletion cancelled.")
        await db.close()
        return

    print("--- Deleting Database Records ---")
    # Delete from Videos
    await db.execute("DELETE FROM videos WHERE series_id = ?", [story_id])
    print("Deleted video records.")
    
    # Delete from Story Parts
    await db.execute("DELETE FROM story_parts WHERE series_id = ?", [story_id])
    print("Deleted story_parts records.")
    
    # Delete from Story Series
    await db.execute("DELETE FROM story_series WHERE id = ?", [story_id])
    print("Deleted story_series record.")
    
    print("--- Deleting Files on Disk ---")
    
    # 1. raw_stories
    raw_dir = Path("data/raw_stories") / safe_channel / safe_title
    if raw_dir.exists() and raw_dir.is_dir():
        try:
            shutil.rmtree(raw_dir)
            print(f"Deleted raw text directory: {raw_dir}")
        except Exception as e:
            print(f"Error deleting {raw_dir}: {e}")
    else:
        print(f"Directory not found (Skipped): {raw_dir}")
        
    # 2. final_shorts
    final_dir = Path("data/final_shorts") / safe_channel / safe_title
    if final_dir.exists() and final_dir.is_dir():
        try:
            shutil.rmtree(final_dir)
            print(f"Deleted final output directory: {final_dir}")
        except Exception as e:
            print(f"Error deleting {final_dir}: {e}")
    else:
        print(f"Directory not found (Skipped): {final_dir}")

    print("\nSUCCESS: Story completely deleted.")
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
