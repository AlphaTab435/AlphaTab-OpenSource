import os
import sys
import argparse
import asyncio
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from core.database import db

def parse_args():
    parser = argparse.ArgumentParser(description="ShortsForge SLA Queue Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    subparsers.add_parser("list", help="List the full hierarchical quota tree")

    # Set Global
    parser_global = subparsers.add_parser("set-global", help="Update global master quotas")
    parser_global.add_argument("--gen", type=int, help="New global generation quota")
    parser_global.add_argument("--upload", type=int, help="New global upload quota")

    # Set Channel
    parser_channel = subparsers.add_parser("set-channel", help="Update a channel's quotas")
    parser_channel.add_argument("id", type=str, help="Channel ID")
    parser_channel.add_argument("--gen", type=int, help="New channel generation quota")
    parser_channel.add_argument("--upload", type=int, help="New channel upload quota")

    # Set Story
    parser_story = subparsers.add_parser("set-story", help="Update a story's priority quota")
    parser_story.add_argument("id", type=int, help="Story ID")
    parser_story.add_argument("--quota", type=int, required=True, help="New assigned_quota value")

    return parser.parse_args()

async def list_tree():
    global_row = await db.fetch_one("SELECT global_gen_quota, global_upload_quota FROM global_settings WHERE id = 1")
    g_gen, g_up = global_row if global_row else (0, 0)
    
    print("=== Quota Hierarchy Tree ===")
    print(f"[GLOBAL] Gen Limit: {g_gen} | Upload Limit: {g_up}\n")
    
    channels = await db.fetch_all("SELECT id, name, channel_gen_quota, channel_upload_quota FROM channels")
    for c in channels:
        cid, cname, c_gen, c_up = c
        print(f"  |- [CHANNEL] {cname} (ID: {cid}) - Gen Quota: {c_gen} | Upload Quota: {c_up}")
        
        stories = await db.fetch_all("""
            SELECT id, topic, status, assigned_quota 
            FROM story_series 
            WHERE channel_id = ? AND status IN ('pending', 'inProgress')
            ORDER BY assigned_quota DESC, CASE WHEN status = 'inProgress' THEN 1 ELSE 2 END ASC, id ASC
        """, [cid])
        
        for s in stories:
            sid, stopic, sstat, squota = s
            print(f"       |- [STORY {sid}] {stopic[:30]}... ({sstat}) - Quota: {squota}")
    print("============================")

async def set_global(gen_quota, upload_quota):
    if gen_quota is not None:
        sum_row = await db.fetch_one("SELECT SUM(channel_gen_quota) FROM channels")
        c_sum = sum_row[0] if sum_row and sum_row[0] else 0
        if gen_quota < c_sum:
            print(f"ERROR: Cannot set Global Gen Quota to {gen_quota}. It must be >= SUM(Channel Gen Quotas) which is {c_sum}.")
            return
        await db.execute("UPDATE global_settings SET global_gen_quota = ? WHERE id = 1", [gen_quota])
        print(f"SUCCESS: Global Gen Quota updated to {gen_quota}")

    if upload_quota is not None:
        sum_row = await db.fetch_one("SELECT SUM(channel_upload_quota) FROM channels")
        c_sum = sum_row[0] if sum_row and sum_row[0] else 0
        if upload_quota < c_sum:
            print(f"ERROR: Cannot set Global Upload Quota to {upload_quota}. It must be >= SUM(Channel Upload Quotas) which is {c_sum}.")
            return
        await db.execute("UPDATE global_settings SET global_upload_quota = ? WHERE id = 1", [upload_quota])
        print(f"SUCCESS: Global Upload Quota updated to {upload_quota}")

async def set_channel(cid, gen_quota, upload_quota):
    ch_row = await db.fetch_one("SELECT channel_gen_quota, channel_upload_quota FROM channels WHERE id = ?", [cid])
    if not ch_row:
        print(f"ERROR: Channel {cid} not found.")
        return
    old_gen, old_up = ch_row

    global_row = await db.fetch_one("SELECT global_gen_quota, global_upload_quota FROM global_settings WHERE id = 1")
    g_gen, g_up = global_row if global_row else (0, 0)

    if gen_quota is not None:
        # Check against Global Limit
        sum_row = await db.fetch_one("SELECT SUM(channel_gen_quota) FROM channels WHERE id != ?", [cid])
        other_sum = sum_row[0] if sum_row and sum_row[0] else 0
        if other_sum + gen_quota > g_gen:
            print(f"ERROR: Channel Gen Quota {gen_quota} + other channels ({other_sum}) exceeds Global Gen Quota ({g_gen}).")
            return
        
        # Check against Children Stories Limit
        s_sum_row = await db.fetch_one("SELECT SUM(assigned_quota) FROM story_series WHERE channel_id = ? AND status IN ('pending', 'inProgress')", [cid])
        s_sum = s_sum_row[0] if s_sum_row and s_sum_row[0] else 0
        if gen_quota < s_sum:
            print(f"ERROR: Cannot set Channel Gen Quota to {gen_quota}. It must be >= SUM(Active Story Quotas in channel) which is {s_sum}.")
            return

        await db.execute("UPDATE channels SET channel_gen_quota = ? WHERE id = ?", [gen_quota, cid])
        print(f"SUCCESS: Channel {cid} Gen Quota updated to {gen_quota}")

    if upload_quota is not None:
        sum_row = await db.fetch_one("SELECT SUM(channel_upload_quota) FROM channels WHERE id != ?", [cid])
        other_sum = sum_row[0] if sum_row and sum_row[0] else 0
        if other_sum + upload_quota > g_up:
            print(f"ERROR: Channel Upload Quota {upload_quota} + other channels ({other_sum}) exceeds Global Upload Quota ({g_up}).")
            return
        await db.execute("UPDATE channels SET channel_upload_quota = ? WHERE id = ?", [upload_quota, cid])
        print(f"SUCCESS: Channel {cid} Upload Quota updated to {upload_quota}")

async def set_story(sid, quota):
    s_row = await db.fetch_one("SELECT channel_id, assigned_quota, topic FROM story_series WHERE id = ?", [sid])
    if not s_row:
        print(f"ERROR: Story {sid} not found.")
        return
    cid, old_quota, topic = s_row

    if quota < 0:
        print("ERROR: Quota cannot be negative.")
        return

    # Check against Channel Limit
    ch_row = await db.fetch_one("SELECT channel_gen_quota FROM channels WHERE id = ?", [cid])
    c_gen = ch_row[0] if ch_row else 0

    s_sum_row = await db.fetch_one("SELECT SUM(assigned_quota) FROM story_series WHERE channel_id = ? AND id != ? AND status IN ('pending', 'inProgress')", [cid, sid])
    other_sum = s_sum_row[0] if s_sum_row and s_sum_row[0] else 0

    if other_sum + quota > c_gen:
        print(f"ERROR: Story Quota {quota} + other stories in channel ({other_sum}) exceeds Channel Gen Quota ({c_gen}).")
        return

    await db.execute("UPDATE story_series SET assigned_quota = ? WHERE id = ?", [quota, sid])
    print(f"SUCCESS: Story {sid} '{topic[:20]}...' assigned_quota updated to {quota}")

async def main():
    args = parse_args()
    await db.connect()
    
    try:
        if args.command == "list":
            await list_tree()
        elif args.command == "set-global":
            await set_global(args.gen, args.upload)
        elif args.command == "set-channel":
            await set_channel(args.id, args.gen, args.upload)
        elif args.command == "set-story":
            await set_story(args.id, args.quota)
        else:
            print("Use --help for usage.")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
