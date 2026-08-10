import os
import shutil
import zipfile
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STAGING_DIR = PROJECT_ROOT / "temp_deploy_build"
ZIP_NAME = PROJECT_ROOT / "deploy.zip"

# Strict Whitelist of items to include
INCLUDES = [
    "core",
    "scripts/scraper",
    "scripts/story_maker",
    "scripts/utils",
    "scripts/autopilot.py",
    "scripts/seed_db.py",
    "scripts/delete_story.py",
]

# Strict Blacklist of items to ignore during directory copying
EXCLUDES = {
    "__pycache__",
    "output",          # scraper output
    "scraper.db",      # scraper database
    "test_*.py",       # any testing scripts inside allowed folders
    # V1 Legacy Core Folders not used by V2 Autopilot
    "ai",              # core/ai is legacy
    "analytics",       # core/analytics is legacy
    "media",           # core/media is legacy
    
    # V1 Legacy YouTube Scripts (V2 uses scripts/story_maker/run_upload.py instead)
    "uploader.py",
    "metadata.py",
    # V1 Legacy Core Files not used by V2 Autopilot
    "notifications.py",
    "pro_features.py",
    "rate_limiter.py",
    
    # Active V2 Code (Excluded because add_channel.py requires a local browser pop-up for OAuth and cannot be run on the headless Oracle VM)
    "add_channel.py",      # Main script requiring local browser pop-up
    "channels.py",         # Dependency of add_channel.py
    "logging_config.py",   # Dependency of add_channel.py
}

# The clean, stripped-down V2 requirements
DEPLOY_REQUIREMENTS = """# ShortsForge V2 Autopilot Dependencies
# Core
python-dotenv>=1.1.1
libsql-client>=0.3.1

# Story Maker & Scraper
google-genai>=1.65.0
openai>=1.12.0
gTTS>=2.5.4
edge-tts>=7.2.8
Pillow>=11.0.0
ffmpeg-python>=0.2.0
httpx>=0.28.1
primp>=0.6.2
beautifulsoup4>=4.12.3
praw>=7.7.1
ddgs>=9.14.0
playwright>=1.49.1

# YouTube & Google Drive
google-api-python-client>=2.190.0
google-auth>=2.38.0
google-auth-oauthlib>=1.2.4
google-auth-httplib2>=0.3.0
"""

def should_exclude(src: Path) -> bool:
    name = src.name
    if name in EXCLUDES:
        return True
    if name.endswith(".pyc") or name.startswith("."):
        return True
    if name.startswith("test_"):
        return True
    
    # Specifically exclude V1 files inside core/content
    if "core\\content" in str(src) or "core/content" in str(src):
        # Don't skip the directory itself
        if name == "content" and src.is_dir():
            return False
        if name not in ["ai_config.py", "__init__.py"]:
            return True
            
    return False

def copy_allowed_items():
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    STAGING_DIR.mkdir()

    for item_path in INCLUDES:
        src = PROJECT_ROOT / item_path
        if not src.exists():
            print(f"[WARNING] Included path does not exist: {src}")
            continue

        dest = STAGING_DIR / item_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        if src.is_dir():
            shutil.copytree(
                src, dest,
                ignore=lambda d, files: [f for f in files if should_exclude(Path(d) / f)]
            )
        else:
            if not should_exclude(src):
                shutil.copy2(src, dest)

def write_requirements():
    req_file = STAGING_DIR / "deploy_requirements.txt"
    with open(req_file, "w") as f:
        f.write(DEPLOY_REQUIREMENTS)

def zip_staging():
    if ZIP_NAME.exists():
        ZIP_NAME.unlink()

    print(f"Zipping deployment package to {ZIP_NAME.name}...")
    with zipfile.ZipFile(ZIP_NAME, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(STAGING_DIR):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(STAGING_DIR)
                zf.write(file_path, arcname)

def cleanup():
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)

if __name__ == "__main__":
    print("=== ShortsForge V2 Deployment Packager ===")
    print("1. Copying whitelisted files...")
    copy_allowed_items()
    
    print("2. Generating strict deploy_requirements.txt...")
    write_requirements()
    
    print("3. Building zip archive...")
    zip_staging()
    
    print("4. Cleaning up staging area...")
    cleanup()
    
    print(f"\\n[SUCCESS] Deployment package ready: {ZIP_NAME}")
    print("\\nIMPORTANT: Transfer the following to your Oracle Server:")
    print("  1. deploy.zip")
    print("  2. .env")
    print("  3. data/shortsforge.db")
    print("  4. data/credentials/drive_token.json (if using Google Drive Backups)")
    print("  5. data/credentials/client_secret.json (Required master key: automatically refreshes expired YT/Drive tokens)")
