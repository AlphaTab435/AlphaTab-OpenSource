"""
ShortsForge — YouTube OAuth Token Management
Handles OAuth 2.0 flow, token storage (encrypted), and refresh.
Per WEEK_BY_WEEK_PROMPTS Week 4 + TECHNICAL_ADDENDUM: tokens MUST be encrypted.

Free tier: YouTube Data API v3 has 10,000 quota units/day (free).
  Upload = 1,600 units. So ~6 uploads/day on free tier.
  GOOGLE_AI_PRO doesn't affect YouTube quota — it's always free.
"""

import os
import sys
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from core.config import DEV_MODE
from core.security import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

# YouTube API scope — upload + manage videos (full scope required for Playlist creation)
SCOPES = ["https://www.googleapis.com/auth/youtube"]

# Path to store credentials (encrypted in DB, file for initial setup)
CREDENTIALS_DIR = os.path.join("data", "credentials")


def get_oauth_flow(client_secrets_path: str = None) -> InstalledAppFlow:
    """
    Creates an OAuth 2.0 flow for YouTube API authorization.
    
    Args:
        client_secrets_path: Path to client_secret.json from Google Cloud Console.
                            Defaults to data/credentials/client_secret.json
    
    Returns:
        InstalledAppFlow instance ready for authorization.
    """
    if not client_secrets_path:
        client_secrets_path = os.path.join(CREDENTIALS_DIR, "client_secret.json")
    
    if not os.path.exists(client_secrets_path):
        raise FileNotFoundError(
            f"client_secret.json not found at {client_secrets_path}.\n"
            "Download it from Google Cloud Console → Credentials → OAuth 2.0 Client IDs.\n"
            "See YOUTUBE_SETUP.md for step-by-step instructions."
        )
    
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
    return flow


def authorize_channel(channel_id: str, client_secrets_path: str = None) -> Dict[str, str]:
    """
    Runs the OAuth 2.0 authorization flow for a YouTube channel.
    Opens a browser for the user to grant access.
    Returns encrypted token data for database storage.
    
    Args:
        channel_id: The channel identifier in our system (e.g., "rendermind").
        client_secrets_path: Path to client_secret.json.
        
    Returns:
        Dict with encrypted token data: {access_token, refresh_token, token_uri, client_id, client_secret, expiry}
    """
    flow = get_oauth_flow(client_secrets_path)
    
    # Run local server for OAuth callback
    credentials = flow.run_local_server(port=8090, prompt="consent")
    
    logger.info(f"OAuth authorization successful for channel: {channel_id}")
    
    # Prepare token data
    token_data = {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }
    
    # Encrypt the entire token payload
    token_json = json.dumps(token_data)
    encrypted = encrypt_token(token_json)
    
    return {"channel_id": channel_id, "encrypted_token": encrypted}


def load_credentials(encrypted_token: str) -> Optional[Credentials]:
    """
    Decrypts stored token data and returns Google Credentials object.
    Automatically refreshes expired tokens.
    
    Args:
        encrypted_token: Encrypted token string from database.
        
    Returns:
        Valid Credentials object, or None if token is invalid/expired beyond repair.
    """
    try:
        decrypted = decrypt_token(encrypted_token)
        if not decrypted:
            logger.error("Failed to decrypt token.")
            return None
        
        token_data = json.loads(decrypted)
        
        credentials = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            token_uri=token_data["token_uri"],
            client_id=token_data["client_id"],
            client_secret=token_data["client_secret"],
        )
        
        # Refresh if expired
        if credentials.expired and credentials.refresh_token:
            logger.info("Access token expired — refreshing...")
            credentials.refresh(Request())
            logger.info("Token refreshed successfully.")
        
        if not credentials.valid:
            logger.error("Credentials are invalid after refresh attempt.")
            return None
        
        return credentials
        
    except json.JSONDecodeError as e:
        logger.error(f"Token data is corrupted: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        return None


async def save_token_to_db(channel_id: str, encrypted_token: str):
    """
    Saves encrypted OAuth token to the channels table.
    Called after initial authorization or token refresh.
    """
    from core.database import db
    await db.execute(
        "UPDATE channels SET oauth_token = ? WHERE id = ?",
        [encrypted_token, channel_id]
    )
    logger.info(f"Encrypted token saved for channel: {channel_id}")


async def get_token_from_db(channel_id: str) -> Optional[str]:
    """
    Retrieves encrypted OAuth token from the channels table.
    """
    from core.database import db
    row = await db.fetch_one(
        "SELECT oauth_token FROM channels WHERE id = ?",
        [channel_id]
    )
    return row[0] if row and row[0] else None
