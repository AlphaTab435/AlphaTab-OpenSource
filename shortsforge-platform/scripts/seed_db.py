import os
import sys
import asyncio
from datetime import datetime, timezone

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import db
from core.config import NICHE_VOICES
import json


def make_password_hash(password: str) -> str:
    """Creates a bcrypt hash from a password string."""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()
    except ImportError:
        return "$2b$12$devmodehashplaceholder"  # Fallback if bcrypt not installed


DEFAULT_CHANNELS = {
    "rendermind": {
        "id": "rendermind", "name": "RenderMind", "niche": "space", "language": "en",
        "language_pair": "en+ur",
        "voice": NICHE_VOICES["space"], "upload_time": "12:00",
        "caption_style": "highlight",
    },
    "mtabish": {
        "id": "mtabish", "name": "MTabish", "niche": "motivation", "language": "en",
        "language_pair": "en+ur",
        "voice": NICHE_VOICES["motivation"], "upload_time": "14:00",
        "caption_style": "highlight",
    },
    "stunners": {
        "id": "stunners", "name": "Stunners", "niche": "mystery", "language": "en",
        "language_pair": "en+ur",
        "voice": NICHE_VOICES["mystery"], "upload_time": "16:00",
        "caption_style": "highlight",
    },
    "aimoney": {
        "id": "aimoney", "name": "AI Money Maker", "niche": "money", "language": "en",
        "language_pair": "en+ur",
        "voice": NICHE_VOICES["money"], "upload_time": "13:00",
        "caption_style": "highlight",
    },
    "movieurdu": {
        "id": "movieurdu", "name": "Movie Explainer Urdu", "niche": "movie_explainer", "language": "ur",
        "language_pair": "ur-only",
        "voice": NICHE_VOICES["movie_explainer"], "upload_time": "15:00",
        "caption_style": "subtitles",
    },
}

WORKSPACES = [
    {
        "id": "default_workspace",
        "name": "Default Workspace",
        "owner_id": "user_1",
        "plan": "free"
    }
]

# Use ADMIN_PASSWORD from env if set, else use a placeholder
_admin_password = os.environ.get("ADMIN_PASSWORD", "admin")
USERS = [
    {
        "id": "user_1",
        "email": "admin@shortsforge.local",
        "password_hash": make_password_hash(_admin_password),
        "full_name": "Admin",
        "is_verified": True
    }
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def seed():
    print("=" * 40)
    print("  ShortsForge Database Seeder")
    print(f"  Admin password: {_admin_password!r}")
    print("=" * 40)
    
    await db.connect()
    await db.init_schema()

    # Seed Users
    print("\n[1/4] Seeding Users...")
    for user in USERS:
        try:
            await db.execute(
                "INSERT OR IGNORE INTO users (id, email, password_hash, full_name, is_verified, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                [user['id'], user['email'], user['password_hash'], user['full_name'], user['is_verified'], now_iso()]
            )
            print(f"  > User: {user['full_name']} ({user['email']})")
        except Exception as e:
            print(f"  ! User {user['id']}: {e}")

    # Seed Workspaces
    print("\n[2/4] Seeding Workspaces...")
    for ws in WORKSPACES:
        try:
            await db.execute(
                "INSERT OR IGNORE INTO workspaces (id, name, owner_id, plan, created_at) VALUES (?, ?, ?, ?, ?)",
                [ws['id'], ws['name'], ws['owner_id'], ws['plan'], now_iso()]
            )
            print(f"  > Workspace: {ws['name']}")
        except Exception as e:
            print(f"  ! Workspace {ws['id']}: {e}")

    # Seed Workspace Members (CRITICAL — auth.py looks this up for workspace_id)
    print("\n[3/4] Seeding Workspace Membership...")
    try:
        await db.execute(
            "INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)",
            ["default_workspace", "user_1", "owner"]
        )
        print("  > user_1 -> default_workspace (owner)")
    except Exception as e:
        print(f"  ! Membership: {e}")

    # Seed ALL Channels from config
    print(f"\n[4/4] Seeding {len(DEFAULT_CHANNELS)} Channels...")
    for ch_id, ch_config in DEFAULT_CHANNELS.items():
        try:
            voice_json = json.dumps({"voice": ch_config["voice"]})
            schedule_json = json.dumps({"time": ch_config["upload_time"]})
            await db.execute(
                "INSERT OR IGNORE INTO channels (id, workspace_id, name, niche, language, language_pair, voice_config, schedule, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [ch_id, "default_workspace", ch_config['name'], ch_config['niche'], ch_config['language'], ch_config.get('language_pair', 'en-only'), voice_json, schedule_json, now_iso()]
            )
            print(f"  > Channel: {ch_config['name']} ({ch_config['niche']}, {ch_config['language']})")
        except Exception as e:
            print(f"  ! Channel {ch_id}: {e}")

    print(f"\n{'=' * 40}")
    print(f"  Seed complete!")
    print(f"  Login: admin@shortsforge.local / {_admin_password}")
    print(f"  Or use ADMIN_PASSWORD from your .env file")
    print(f"  Run: uvicorn dashboard.backend.main:app --port 8000 --reload")
    print(f"{'=' * 40}")


if __name__ == "__main__":
    asyncio.run(seed())
    sys.exit(0)
