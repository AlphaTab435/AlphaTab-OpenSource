import os
import sys
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SCOPES = ['https://www.googleapis.com/auth/drive.file']
CREDENTIALS_FILE = PROJECT_ROOT / "data" / "credentials" / "client_secret.json"
TOKEN_FILE = PROJECT_ROOT / "data" / "credentials" / "drive_token.json"

def get_drive_service():
    """
    Authenticates using User OAuth and returns the Drive service.
    """
    creds = None
    
    # Try to load existing token
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception as e:
            logger.warning(f"Failed to load existing drive_token.json: {e}")
            creds = None
            
    # If no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Google Drive token...")
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning(f"Failed to refresh token, forcing re-auth: {e}")
                creds = None
                
        if not creds:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(f"client_secret.json not found at {CREDENTIALS_FILE}. Please follow Phase 1 of the guide.")
                
            logger.info("No valid Drive token found. Initiating OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            logger.info("Saved new drive_token.json for future autonomous runs.")

    return build('drive', 'v3', credentials=creds)

def upload_file(file_path: str) -> bool:
    """
    Uploads a file to Google Drive using User OAuth.
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        logger.error(f"File not found: {file_path}")
        return False
        
    folder_id = os.environ.get("DRIVE_BACKUP_FOLDER_ID")
    if not folder_id:
        logger.warning("DRIVE_BACKUP_FOLDER_ID not found in .env. Skipping Drive Upload.")
        return False

    try:
        service = get_drive_service()
        
        file_metadata = {
            'name': path_obj.name,
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(str(path_obj), resumable=True)
        
        logger.info(f"Uploading {path_obj.name} to Google Drive...")
        # Execute the upload
        file_response = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        logger.info(f"Upload Successful! Google Drive File ID: {file_response.get('id')}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to upload to Google Drive: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Uploads a file to Google Drive using User OAuth")
    parser.add_argument("file_path", help="Path to the local file to upload")
    args = parser.parse_args()
    
    upload_file(args.file_path)
