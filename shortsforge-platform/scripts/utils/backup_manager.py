import os
import zipfile
import datetime
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"

TARGETS = [
    ".env",
    "data/shortsforge.db",
    "scripts/scraper/scraper.db",
    "scripts/scraper/configs",
    "data/raw_stories",
    "data/credentials"
]

def create_backup() -> str:
    """
    Creates a timestamped zip of all critical targets.
    Returns the absolute path to the generated zip file.
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H%M")
    zip_filename = f"shortsforge_backup_{timestamp}.zip"
    zip_path = BACKUP_DIR / zip_filename
    
    logger.info(f"Starting backup: {zip_path}")
    
    added_count = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for target in TARGETS:
            target_path = PROJECT_ROOT / target
            
            if not target_path.exists():
                logger.warning(f"Target not found, skipping: {target}")
                continue
                
            if target_path.is_file():
                # Write file directly at the root of the zip
                zipf.write(target_path, arcname=target)
                added_count += 1
                logger.info(f"Added file: {target}")
            elif target_path.is_dir():
                # Walk the directory
                for root, _, files in os.walk(target_path):
                    for file in files:
                        file_path = Path(root) / file
                        # Keep the directory structure inside the zip
                        arcname = file_path.relative_to(PROJECT_ROOT)
                        zipf.write(file_path, arcname=str(arcname))
                        added_count += 1
                logger.info(f"Added directory: {target}")

    if added_count == 0:
        logger.error("No files were added to the backup. Deleting empty zip.")
        zip_path.unlink(missing_ok=True)
        return ""
        
    logger.info(f"Backup complete! Successfully archived {added_count} files.")
    return str(zip_path)

if __name__ == "__main__":
    result = create_backup()
    if result:
        print(f"\n[SUCCESS] Backup saved to: {result}")
    else:
        print("\n[FAILED] Backup could not be created.")
