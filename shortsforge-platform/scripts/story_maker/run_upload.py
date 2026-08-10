import os
import sys
from pathlib import Path
import asyncio
import argparse
import traceback

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from core.database import db
from core.youtube.auth import load_credentials, get_token_from_db
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from datetime import datetime, timedelta, timezone

def parse_args():
    parser = argparse.ArgumentParser(description="ShortsForge Upload Queue")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed dev-style logging")
    parser.add_argument("--dry-run", action="store_true", help="Simulate uploads and playlists without hitting YouTube API")
    parser.add_argument("--public", action="store_true", help="Upload videos as Public instead of Private")
    parser.add_argument("--schedule", action="store_true", help="Use YouTube native scheduling (publishAt)")
    parser.add_argument("--schedule-start-delay", type=float, default=1.0, help="Hours to wait before first video")
    parser.add_argument("--schedule-interval", type=float, default=2.5, help="Hours to wait between subsequent videos")
    parser.add_argument("--peak-us", action="store_true", help="Snap scheduled uploads to Peak US Hours (22:00-02:00 UTC)")
    parser.add_argument("--dynamic-interval", action="store_true", help="Calculate interval dynamically to fit quota into a 4-hour window")
    return parser.parse_args()

def get_next_peak_time(current_dt):
    """
    Given a datetime, returns the next available slot within the US Peak Window (22:00 - 02:00 UTC).
    If current_dt is already in the window, it returns current_dt.
    If it's outside the window, it snaps to 22:00 of the next available window.
    """
    if current_dt.hour >= 22 or current_dt.hour < 2:
        return current_dt
        
    next_peak = current_dt.replace(hour=22, minute=0, second=0, microsecond=0)
    return next_peak

def upload_video_sync(youtube, video_path, title, description, thumbnail_path, privacy_status, publish_at=None):
    """Executes the actual YouTube API upload synchronously."""
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "24" # Entertainment
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }
    
    if publish_at:
        body["status"]["publishAt"] = publish_at
        
    # Execute upload
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    response = request.execute()
    
    video_id = response["id"]
    youtube_url = f"https://youtube.com/watch?v={video_id}"
    
    # Upload Thumbnail
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
        except Exception as e:
            # Strip < and > so Gmail doesn't hide it as an HTML tag in the email
            safe_error = str(e).replace('<', '[').replace('>', ']')
            print(f"    [WARNING] Thumbnail upload failed (Is your channel Phone Verified?): {safe_error}")
            
    return video_id, youtube_url

def create_playlist_sync(youtube, title, privacy_status):
    """Creates a new YouTube playlist."""
    body = {
        "snippet": {
            "title": title,
            "description": f"Full story: {title}"
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }
    response = youtube.playlists().insert(
        part="snippet,status",
        body=body
    ).execute()
    return response["id"]
    
def add_to_playlist_sync(youtube, playlist_id, video_id):
    """Adds a video to an existing YouTube playlist."""
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id
            }
        }
    }
    youtube.playlistItems().insert(
        part="snippet",
        body=body
    ).execute()

async def main():
    args = parse_args()
    privacy_status = "public" if args.public else "private"
    
    if args.schedule and args.public:
        print("[WARNING] Both --schedule and --public provided. YouTube requires scheduled videos to be 'private'. Overriding to 'private' just for this run.")
        privacy_status = "private"

    # 0. Initialize Thumbnail Export List
    export_file = PROJECT_ROOT / "data" / "metrics" / "uploaded_thumbnails.txt"
    if export_file.exists():
        export_file.unlink()
        
    print(f"=== ShortsForge Upload Queue (Privacy: {privacy_status}{', Scheduled' if args.schedule else ''}) ===")
    
    await db.connect()
    
    try:
        # 0. Fetch Master Global Upload Quota
        global_row = await db.fetch_one("SELECT global_upload_quota FROM global_settings WHERE id = 1")
        if not global_row or global_row[0] <= 0:
            print("[INFO] Global Upload Quota is 0. Nothing to do. Exiting.")
            return
            
        global_quota = global_row[0]
        
        # 1. Fetch pending videos with Priority
        query = """
            SELECT v.id, v.video_path, v.is_short, v.title, v.thumbnail_path, 
                   s.topic, s.channel_id, c.channel_upload_quota, c.name, 
                   s.base_description, s.youtube_playlist_id, s.id as series_id, s.global_hook
            FROM videos v
            JOIN story_series s ON v.series_id = s.id
            JOIN channels c ON s.channel_id = c.id
            WHERE v.status = 'pending'
            ORDER BY 
                c.channel_upload_quota DESC,
                v.id ASC
        """
        pending_videos = await db.fetch_all(query)
        
        if not pending_videos:
            print("[INFO] No pending videos in the queue.")
            return
    
        uploaded_count = 0
        channel_upload_counts = {}
        session_playlists = {}
        channel_timers = {}
        
        for row in pending_videos:
            if uploaded_count >= global_quota:
                print(f"\n[INFO] Reached Global Upload Limit ({global_quota}). Stopping.")
                break
                
            video_id, video_path, is_short, title, thumbnail_path, topic, channel_id, channel_upload_quota, channel_name, base_description, playlist_id, series_id, global_hook = row
            
            if series_id in session_playlists:
                playlist_id = session_playlists[series_id]
                
            if channel_upload_quota > 0 and channel_upload_counts.get(channel_id, 0) >= channel_upload_quota:
                if args.verbose:
                    print(f"[DEBUG] Skipping video {video_id} because Channel '{channel_name}' reached its limit ({channel_upload_quota}).")
                continue
            
            # Authentication
            encrypted_token = await get_token_from_db(channel_id)
            if not encrypted_token:
                print(f"[ERROR] Channel '{channel_name}' has no OAuth token. Run 'python scripts/add_channel.py --channel {channel_id}' first.")
                continue
                
            creds = load_credentials(encrypted_token)
            if not creds:
                print(f"[ERROR] Invalid or expired credentials for Channel '{channel_name}'. You may need to re-authorize.")
                continue
                
            youtube = build("youtube", "v3", credentials=creds)
            
            # Prepare Base Titles and Descriptions
            final_description = base_description or ""
            
            # Base Title Logic for Playlists
            base_title = topic if global_hook.lower() == topic.lower() else f"{global_hook} | {topic}"
            if len(base_title) > 140:
                base_title = base_title[:140].strip() + "..."
            
            # 2. Handle Standalone vs Trailer Short Detection
            long_video_count = 0
            total_shorts = 0
            if is_short:
                long_videos_row = await db.fetch_one("SELECT COUNT(*) FROM videos WHERE series_id = ? AND is_short = 0", [series_id])
                long_video_count = long_videos_row[0] if long_videos_row else 0
                
                shorts_row = await db.fetch_one("SELECT COUNT(*) FROM videos WHERE series_id = ? AND is_short = 1", [series_id])
                total_shorts = shorts_row[0] if shorts_row else 0
                
            is_standalone = is_short and long_video_count == 0 and total_shorts == 1
            
            if not is_standalone and not playlist_id:
                print(f"  |- Creating new Playlist for series: {base_title}")
                if args.dry_run:
                    print("     [DRY-RUN] Bypassing YouTube API. Mocking playlist creation.")
                    playlist_id = f"mock_playlist_{series_id}"
                else:
                    try:
                        # Playlists should always be public. If videos are scheduled or private, they simply won't be visible in the playlist until they go live.
                        playlist_id = await asyncio.to_thread(create_playlist_sync, youtube, base_title, "public")
                        await db.execute("UPDATE story_series SET youtube_playlist_id = ? WHERE id = ?", [playlist_id, series_id])
                    except Exception as e:
                        safe_error = str(e).replace('<', '[').replace('>', ']')
                        print(f"    [WARNING] Failed to create Playlist (YouTube limits new playlists per day): {safe_error}")
                        playlist_id = None
                
                if playlist_id:
                    session_playlists[series_id] = playlist_id
                
            # 4. Handle Shorts & Long Video Linking Logic
            playlist_url = f"https://youtube.com/playlist?list={playlist_id}" if playlist_id else None
            
            if is_short:
                if is_standalone:
                    if not args.verbose: print(f"\n--- Processing Upload ({uploaded_count+1}) ---")
                    print(f"[{topic}] TYPE 2 (Standalone Short). Uploading immediately.")
                else:
                    if not args.verbose: print(f"\n--- Processing Upload ({uploaded_count+1}) ---")
                    if long_video_count == 0:
                        print(f"[{topic}] TYPE 3 (Multipart Short). Linking to Playlist: {playlist_url}")
                    else:
                        print(f"[{topic}] TYPE 1 (Trailer Short). Linking to Playlist: {playlist_url}")
                    
                    # Inject URL at the TOP of description
                    final_description = f"📺 Watch the full story here: {playlist_url}\n\n{final_description}"
            else:
                if not args.verbose: print(f"\n--- Processing Upload ({uploaded_count+1}) ---")
                if playlist_url:
                    # Inject URL at the TOP of description for long videos too
                    final_description = f"📺 Watch the full story here: {playlist_url}\n\n{final_description}"
                
            try:
                # 4. Execute YouTube Upload
                publish_at_iso = None
                if args.schedule:
                    # Dynamically calculate interval to fit quota into a 4-hour window
                    interval = (4.0 / channel_upload_quota) if (args.dynamic_interval and channel_upload_quota > 0) else args.schedule_interval
                    
                    if channel_id not in channel_timers:
                        base_time = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=args.schedule_start_delay)
                        if args.peak_us:
                            base_time = get_next_peak_time(base_time)
                        channel_timers[channel_id] = base_time
                    else:
                        next_time = channel_timers[channel_id] + timedelta(hours=interval)
                        if args.peak_us:
                            next_time = get_next_peak_time(next_time)
                        channel_timers[channel_id] = next_time
                    publish_at_iso = channel_timers[channel_id].isoformat() + "Z"
                
                print(f"  |- Uploading: {title} (Privacy: {privacy_status}{f', Scheduled: {publish_at_iso}' if publish_at_iso else ''})")
                
                if args.dry_run:
                    print(f"     [DRY-RUN] Bypassing YouTube API upload.")
                    print(f"     [DRY-RUN] Final Description:\n---\n{final_description}\n---")
                    yt_vid_id = f"mock_vid_{video_id}"
                    yt_url = f"https://youtube.com/watch?v={yt_vid_id}"
                else:
                    yt_vid_id, yt_url = await asyncio.to_thread(
                        upload_video_sync, youtube, video_path, title, final_description, thumbnail_path, privacy_status, publish_at_iso
                    )
                print(f"  |- Success! URL: {yt_url}")
                
                # 5. Add Video to Playlist
                should_add_to_playlist = not is_short or (is_short and long_video_count == 0 and not is_standalone)
                if should_add_to_playlist and playlist_id:
                    print(f"  |- Adding to Playlist...")
                    if args.dry_run:
                        print(f"     [DRY-RUN] Bypassing YouTube API playlist insert.")
                    else:
                        try:
                            await asyncio.to_thread(add_to_playlist_sync, youtube, playlist_id, yt_vid_id)
                        except Exception as pe:
                            print(f"     [WARNING] Failed to add video to playlist: {pe}")
                            # We intentionally catch this and continue so the database is still updated to 'uploaded'
                
                # 5. Update Database
                if args.dry_run:
                    print(f"     [DRY-RUN] Bypassing database update.")
                else:
                    await db.execute(
                        "UPDATE videos SET status = 'uploaded', youtube_url = ?, completed_at = CURRENT_TIMESTAMP, error_log = NULL WHERE id = ?",
                        [yt_url, video_id]
                    )
                
                uploaded_count += 1
                channel_upload_counts[channel_id] = channel_upload_counts.get(channel_id, 0) + 1
                
                # 6. Save thumbnail path for email attachment (Shorts only)
                if is_short and thumbnail_path and os.path.exists(thumbnail_path):
                    os.makedirs(export_file.parent, exist_ok=True)
                    with open(export_file, "a", encoding="utf-8") as f:
                        f.write(f"{thumbnail_path}\n")
                
            except Exception as e:
                error_msg = str(e).replace('<', '[').replace('>', ']')
                print(f"[ERROR] Upload failed for video {video_id}: {error_msg}")
                traceback.print_exc()
                await db.execute("UPDATE videos SET error_log = ? WHERE id = ?", [error_msg, video_id])
                
                # Check for YouTube Data API Quota exhaustion
                if "quotaExceeded" in error_msg:
                    print("\n[CRITICAL] YouTube API Quota Reached! Halting all further uploads for today.")
                    break
    
        print(f"\n=== Upload Queue Complete ({uploaded_count} uploaded) ===")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
