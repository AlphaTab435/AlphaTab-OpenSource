# Google Drive Authentication Troubleshooting

## The Error: "could not locate runnable browser"
If your daily cron logs show this error:
```
ERROR - Failed to upload to Google Drive: could not locate runnable browser
```
This means your Google Drive authorization has expired. While the system usually refreshes the token automatically, occasionally Google requires a **full manual re-authentication** for security reasons.

Because the system is running on a headless Ubuntu server, it tries to open a web browser to show you the Google Login page, but fails because there is no desktop GUI.

## The Solution

You must generate a new authentication token on your local Windows PC (which has a web browser), and then transfer that fresh token up to the Ubuntu server.

### Step-by-Step Fix:

1. **Run the Auth Script Locally:**
   Open PowerShell on your Windows machine, navigate to your `shortsforge-platform` project folder, and run the upload script pointing to any small, harmless file (like `requirements.txt`) just to trigger the login:
   ```bash
   python scripts/utils/upload_to_drive.py requirements.txt
   ```
2. **Log In:**
   A browser window will pop up. Log into the Google Account that you use for backups and click "Allow."
3. **Locate the New Token:**
   The script will generate a fresh `drive_token.json` file inside your local `data/credentials/` folder.
4. **Upload to Server:**
   Upload this fresh `drive_token.json` file to your Ubuntu server, specifically placing it in:
   `/home/ubuntu/shortsforge/data/credentials/drive_token.json`
   *(Note: Overwrite the old, expired file).*
5. **Verify:**
   The next time the cron job runs, the backup script will detect the fresh token and seamlessly upload the ZIP file without needing a browser.
