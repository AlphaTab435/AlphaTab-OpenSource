"""
ShortsForge — Add YouTube Channel Script
One-time OAuth setup per channel.
Run this locally to authorize a YouTube channel, then the encrypted token
is stored in the database for automated uploads.

Usage:
  python scripts/add_channel.py --channel rendermind
  python scripts/add_channel.py --channel rendermind --secrets path/to/client_secret.json

Prerequisites:
  1. Google Cloud Project created (see YOUTUBE_SETUP.md)
  2. YouTube Data API v3 enabled
  3. OAuth 2.0 Client ID created (Desktop App)
  4. client_secret.json downloaded to data/credentials/
"""

import os
import sys
import argparse
import asyncio

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logging_config import setup_logging
from core.channels import get_channels
from core.database import db
from core.youtube.auth import authorize_channel, save_token_to_db
from scripts.story_maker.voice_engine import EDGE_VOICES
import json

setup_logging()


async def add_channel(channel_id: str, client_secrets_path: str = None):
    """
    Runs the full channel authorization flow:
    1. Validates channel exists in config
    2. Runs OAuth flow (opens browser)
    3. Encrypts and stores token in database
    """
    # Initialize DB and fetch channels
    await db.connect()
    
    # Ensure schema is initialized (creates tables if starting 100% fresh)
    try:
        await db.init_schema()
    except Exception as e:
        print(f"Warning during schema init: {e}")
        
    CHANNELS = await get_channels()
    
    # Validate channel
    if channel_id not in CHANNELS:
        print(f"\nChannel '{channel_id}' not found in database.")
        create = input("Would you like to create it now? [y/n]: ").strip().lower()
        if create == 'y':
            niche = input("Enter the channel's niche (e.g., 'scary stories'): ").strip()
            search_style = input("Enter Image Search Style (e.g., 'anime style 4k wallpaper') [Press Enter to skip]: ").strip()
            if not search_style:
                search_style = ""
                
            is_shorts = input("Is this channel EXCLUSIVELY for Shorts? (y/n): ").strip().lower()
            is_shorts_only = 1 if is_shorts == 'y' else 0
                
            print("\n--- Language & Audio Configuration ---")
            language_pair = input("Output format? (en, ur, en,ur) [Default: en]: ").strip() or "en"
            dynamic_toggle = input("Enable Dynamic Gender? (y/n) [Default: n]: ").strip().lower()
            enable_dynamic_gender = True if dynamic_toggle == 'y' else False

            ENGLISH_MALE = ["male_narrator", "dramatic_male", "casual_male", "british_male", "authoritative_male"]
            ENGLISH_FEMALE = ["female_narrator", "british_female", "australian_female"]
            URDU_MALE = ["hindi_male"]
            URDU_FEMALE = ["hindi_female"]
            
            print("\n[English Voices]")
            en_male = input(f"Select English MALE voice (List: {ENGLISH_MALE}) [Default: british_male]: ").strip() or "british_male"
            en_female = input(f"Select English FEMALE voice (List: {ENGLISH_FEMALE}) [Default: female_narrator]: ").strip() or "female_narrator"
            en_fallback_val = input("Which is DEFAULT? (1=Male, 2=Female) [Default: 1]: ").strip() or "1"
            en_default = "male" if en_fallback_val == "1" else "female"

            print("\n[Urdu Voices]")
            ur_male = input(f"Select Urdu MALE voice (List: {URDU_MALE}) [Default: hindi_male]: ").strip() or "hindi_male"
            ur_female = input(f"Select Urdu FEMALE voice (List: {URDU_FEMALE}) [Default: hindi_female]: ").strip() or "hindi_female"
            ur_fallback_val = input("Which is DEFAULT? (1=Male, 2=Female) [Default: 1]: ").strip() or "1"
            ur_default = "male" if ur_fallback_val == "1" else "female"
                    
            enable_music = input("\nEnable Background Music? (y/n) [Default: y]: ").strip().lower()
            music_enabled = False if enable_music == 'n' else True
            
            from scripts.story_maker.constants import AVAILABLE_SUBTITLE_STYLES
            
            print("\nAvailable Subtitle Styles:")
            style_keys = list(AVAILABLE_SUBTITLE_STYLES.keys())
            for i, key in enumerate(style_keys, 1):
                print(f"  {i}. {key}")
                
            sub_style_choice = input(f"Select Subtitle Color/Style (1-{len(style_keys)}) [Default: 1]: ").strip()
            
            selected_sub_style = style_keys[0]
            if sub_style_choice.isdigit():
                choice_idx = int(sub_style_choice) - 1
                if 0 <= choice_idx < len(style_keys):
                    selected_sub_style = style_keys[choice_idx]
            
            visual_mode_choice = input("Select Visual Mode (1: classic [1 background], 2: dynamic [scene-by-scene], 3: infographic [animated nodes], 4: infographic_record [real-time]) [Default: classic]: ").strip()
            if visual_mode_choice == "2":
                selected_visual_mode = "dynamic"
            elif visual_mode_choice == "3":
                selected_visual_mode = "infographic"
            elif visual_mode_choice == "4":
                selected_visual_mode = "infographic_record"
            else:
                selected_visual_mode = "classic"
            
            format_choice = input("Select Long Video Format (1: vertical, 2: horizontal) [Default: vertical]: ").strip()
            selected_format = "horizontal" if format_choice == "2" else "vertical"
            
            internet_choice = input("Allow downloading images from DuckDuckGo? (y/n) [Default: y]: ").strip().lower()
            allow_internet_images = 0 if internet_choice == 'n' else 1
            
            shadow_choice = input("Enable Massive Thumbnail Text Shadows? (y/n) [Default: y]: ").strip().lower()
            enable_heavy_shadows = 0 if shadow_choice == 'n' else 1
            
            box_choice = input("Enable Dark Gradient Box behind Thumbnail Text? (y/n) [Default: y]: ").strip().lower()
            enable_dark_gradient_box = 0 if box_choice == 'n' else 1
                    
            voice_config_json = json.dumps({
                "enable_dynamic_gender": enable_dynamic_gender,
                "voices": {
                    "en": { "male": en_male, "female": en_female, "default": en_default },
                    "ur": { "male": ur_male, "female": ur_female, "default": ur_default }
                },
                "music": music_enabled,
                "subtitle_style": selected_sub_style
            })
            
            await db.execute(
                "INSERT INTO channels (id, workspace_id, name, niche, image_search_style, channel_gen_quota, channel_upload_quota, is_shorts_only, voice_config, visual_mode, dynamic_media_type, video_format, allow_internet_images, enable_heavy_shadows, enable_dark_gradient_box, language_pair) VALUES (?, 'default_workspace', ?, ?, ?, 0, 0, ?, ?, ?, 'image', ?, ?, ?, ?, ?)",
                [channel_id, channel_id, niche, search_style, is_shorts_only, voice_config_json, selected_visual_mode, selected_format, allow_internet_images, enable_heavy_shadows, enable_dark_gradient_box, language_pair]
            )
            
            # Scaffold folders
            os.makedirs(f"data/raw_stories/{channel_id}", exist_ok=True)
            os.makedirs(f"data/backgrounds/{channel_id}", exist_ok=True)
            os.makedirs(f"data/backgrounds/{channel_id}/music", exist_ok=True)
            print(f"Scaffolded data directories for '{channel_id}'")
            
            print(f"Created channel '{channel_id}' in the database!")
            # Reload channels
            CHANNELS = await get_channels()
        else:
            print(f"Available channels: {list(CHANNELS.keys())}")
            await db.close()
            return
    
    channel = CHANNELS[channel_id]
    print(f"\n{'='*50}")
    print(f"  Adding YouTube Channel: {channel['name']}")
    print(f"  Niche: {channel['niche']}")
    print(f"{'='*50}")
    
    # Check for client_secret.json
    if not client_secrets_path:
        client_secrets_path = os.path.join("data", "credentials", "client_secret.json")
    
    if not os.path.exists(client_secrets_path):
        print(f"\nError: client_secret.json not found at: {client_secrets_path}")
        print("\nTo fix this:")
        print("  1. Go to Google Cloud Console → APIs & Services → Credentials")
        print("  2. Create OAuth 2.0 Client ID (Desktop App)")
        print("  3. Download the JSON file")
        print(f"  4. Save it as: {client_secrets_path}")
        print("\nSee YOUTUBE_SETUP.md for detailed instructions.")
        return
    
    if channel.get('oauth_token'):
        print(f"\n[INFO] Channel '{channel['name']}' already has an authorized YouTube token!")
        reauth = input("Do you want to re-authenticate and replace it? [y/N]: ").strip().lower()
        if reauth != 'y':
            print("Skipping YouTube authorization.")
            await db.close()
            return

    print("\nOpening browser for YouTube authorization...")
    print("Grant access to your YouTube channel when prompted.\n")
    
    try:
        # Run OAuth flow
        result = authorize_channel(channel_id, client_secrets_path)
        
        # Ensure channel exists in DB (add oauth_token column if needed)
        # First try to add the column (SQLite will error if it exists — that's fine)
        try:
            await db.execute("ALTER TABLE channels ADD COLUMN oauth_token TEXT", [])
        except Exception:
            pass  # Column already exists
        
        # Save encrypted token
        await save_token_to_db(channel_id, result["encrypted_token"])
        
        print(f"\n{'='*50}")
        print(f"  SUCCESS!")
        print(f"  Channel '{channel['name']}' is now connected to YouTube.")
        print(f"  Encrypted token stored in database.")
        print(f"{'='*50}")
        print(f"\nYou can now upload videos with:")
        print(f"  python scripts/story_maker/run_upload.py")
        
    except FileNotFoundError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nAuthorization failed: {e}")
        print("Check YOUTUBE_SETUP.md → Troubleshooting section.")
    finally:
        await db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a YouTube channel to ShortsForge")
    parser.add_argument("--channel", help="Channel ID (e.g., rendermind)", default=None)
    parser.add_argument("--secrets", help="Path to client_secret.json", default=None)
    args = parser.parse_args()
    
    channel_id = args.channel
    if not channel_id:
        channel_id = input("Enter the Channel ID you want to add/authorize (e.g., my_scary_channel): ").strip()
        if not channel_id:
            print("Channel ID is required.")
            sys.exit(1)
            
    asyncio.run(add_channel(channel_id, args.secrets))
