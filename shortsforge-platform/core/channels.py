import json
from typing import Dict, Any, List
import logging
from core.database import db
from core.config import NICHE_VOICES

logger = logging.getLogger(__name__)

async def get_channels(workspace_id: str = "default_workspace") -> Dict[str, Dict[str, Any]]:
    """
    Fetches all active channels from the database and returns them
    as a dictionary keyed by channel_id, matching the legacy CHANNELS config struct.
    """
    columns = [
        "id", "workspace_id", "name", "youtube_id", "niche", "language", "voice_config", 
        "schedule", "is_active", "language_pair", "caption_style", "oauth_token",
        "created_at"
    ]
    
    rows = await db.fetch_all("SELECT * FROM channels WHERE workspace_id = ? AND is_active = 1", [workspace_id])
    channels = {}
    for r in rows:
        # Create a dict from the row using predefined columns
        row_dict = dict(zip(columns, r))
        
        ch_id = row_dict.get("id")
        niche = row_dict.get("niche")
        
        # Safely parse JSON columns
        try:
            voice_config = json.loads(row_dict.get("voice_config")) if row_dict.get("voice_config") else {}
        except (json.JSONDecodeError, TypeError):
            voice_config = {}
            
        try:
            schedule = json.loads(row_dict.get("schedule")) if row_dict.get("schedule") else {}
        except (json.JSONDecodeError, TypeError):
            schedule = {}
            
        channels[ch_id] = {
            "id": ch_id,
            "name": row_dict.get("name"),
            "niche": niche,
            "language": row_dict.get("language") or "en",
            "voice": voice_config.get("voice", NICHE_VOICES.get(niche, "Charon")),
            "upload_time": schedule.get("time", "12:00"),
            "language_pair": row_dict.get("language_pair", "en-only"),
            "caption_style": row_dict.get("caption_style", "highlight"),
            "oauth_token": row_dict.get("oauth_token")
        }
    return channels

async def get_channel(channel_id: str, workspace_id: str = "default_workspace") -> Dict[str, Any]:
    """Fetches a single channel by ID."""
    columns = [
        "id", "workspace_id", "name", "youtube_id", "niche", "language", "voice_config", 
        "schedule", "is_active", "language_pair", "caption_style", "oauth_token",
        "created_at"
    ]
    
    row = await db.fetch_one("SELECT * FROM channels WHERE id = ? AND workspace_id = ?", [channel_id, workspace_id])
    if not row:
        return {}
        
    row_dict = dict(zip(columns, row))
        
    niche = row_dict.get("niche")
    try:
        voice_config = json.loads(row_dict.get("voice_config")) if row_dict.get("voice_config") else {}
    except (json.JSONDecodeError, TypeError):
        voice_config = {}
        
    try:
        schedule = json.loads(row_dict.get("schedule")) if row_dict.get("schedule") else {}
    except (json.JSONDecodeError, TypeError):
        schedule = {}
        
    return {
        "id": row_dict.get("id"),
        "name": row_dict.get("name"),
        "niche": niche,
        "language": row_dict.get("language") or "en",
        "voice": voice_config.get("voice", NICHE_VOICES.get(niche, "Charon")),
        "upload_time": schedule.get("time", "12:00"),
        "language_pair": row_dict.get("language_pair", "en-only"),
        "caption_style": row_dict.get("caption_style", "highlight"),
        "oauth_token": row_dict.get("oauth_token")
    }
