import os
import zipfile
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def zip_folder(source_folder: str, output_zip: str):
    """
    Zips the contents of source_folder into output_zip.
    The zip file will contain the files relative to source_folder.
    """
    if not os.path.exists(source_folder):
        logger.error(f"Source folder does not exist: {source_folder}")
        return False
        
    os.makedirs(os.path.dirname(os.path.abspath(output_zip)), exist_ok=True)
    
    logger.info(f"Zipping {source_folder} into {output_zip}...")
    base_folder_name = os.path.basename(os.path.abspath(source_folder))
    
    try:
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Preserve the base folder name in the zip archive
                    rel_path = os.path.relpath(file_path, source_folder)
                    arcname = os.path.join(base_folder_name, rel_path)
                    zipf.write(file_path, arcname)
                    
        logger.info(f"Successfully created {output_zip}")
        return True
    except Exception as e:
        logger.error(f"Failed to create zip file: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generic utility to zip a folder.")
    parser.add_argument("--source", required=True, help="Path to the folder to zip")
    parser.add_argument("--output", required=True, help="Path to the output .zip file")
    
    args = parser.parse_args()
    zip_folder(args.source, args.output)
