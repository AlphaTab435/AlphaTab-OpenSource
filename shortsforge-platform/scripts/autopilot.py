import os
import sys
import subprocess
import logging
from pathlib import Path

# Setup Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from scripts.utils.mailer import send_email
from scripts.utils.email_templates import get_crash_alert_template, get_daily_report_template
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def save_local_report(subject: str, html: str):
    """Saves the email HTML to disk as a backup in case SMTP fails."""
    try:
        report_dir = PROJECT_ROOT / "data" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_subject = "".join([c if c.isalnum() else "_" for c in subject])[:30]
        report_path = report_dir / f"{timestamp}_{safe_subject}.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Saved local report backup to {report_path}")
    except Exception as e:
        logger.error(f"Failed to save local report backup: {e}")

def run_command(command: list, phase_name: str) -> tuple[str, str]:
    """Runs a subprocess command and returns (status, output)."""
    logger.info(f"Starting Phase: {phase_name} -> {' '.join([str(c) for c in command])}")
    try:
        # Run with project root as CWD
        result = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        output = result.stdout.strip() if result.stdout else ""
        status = "Success" if result.returncode == 0 else "Failed"
        if status == "Failed":
            logger.error(f"Phase {phase_name} failed with exit code {result.returncode}")
            
        return status, output
        
    except Exception as e:
        logger.error(f"Critical exception in phase {phase_name}: {e}")
        import traceback
        tb = traceback.format_exc()
        
        # Fire crash alert immediately
        html = get_crash_alert_template(phase_name, str(e), tb)
        save_local_report(f"CRASH ALERT: ShortsForge Phase '{phase_name}' Failed", html)
        send_email(f"CRASH ALERT: ShortsForge Phase '{phase_name}' Failed", html)
        
        return "Failed", f"Exception: {e}\n{tb}"

def main():
    logger.info("=== Starting ShortsForge Master Autopilot ===")
    
    stats = {}
    
    # --- PHASE 1: SCRAPER ---
    scraper_cmd = [sys.executable, "-u", str(PROJECT_ROOT / "scripts" / "scraper" / "main.py")]
    status, out = run_command(scraper_cmd, "1. Scraper")
    stats['scraper_status'] = status
    stats['scraper_output'] = out
    
    # --- PHASE 2: ZIPPING & INGESTION ---
    ingest_out_log = []
    ingest_status = "Skipped"
    
    staging_dir = PROJECT_ROOT / "scripts" / "scraper" / "output" / "staging"
    if staging_dir.exists():
        channels = [d for d in staging_dir.iterdir() if d.is_dir()]
        if channels:
            ingest_status = "Success"
            for channel_dir in channels:
                channel_name = channel_dir.name
                # Zip
                zip_path = PROJECT_ROOT / "scripts" / "scraper" / "output" / "ready_for_video" / f"{channel_name}.zip"
                zip_cmd = [
                    sys.executable, "-u",
                    str(PROJECT_ROOT / "scripts" / "utils" / "zip_folder.py"),
                    "--source", str(channel_dir),
                    "--output", str(zip_path)
                ]
                z_stat, z_out = run_command(zip_cmd, f"2a. Zip {channel_name}")
                ingest_out_log.append(f"--- Zip {channel_name} ---\n{z_out}")
                
                # Ingest
                if z_stat == "Success":
                    ingest_cmd = [
                        sys.executable, "-u",
                        str(PROJECT_ROOT / "scripts" / "story_maker" / "ingest_zip.py"),
                        str(zip_path),
                        "--auto"
                    ]
                    i_stat, i_out = run_command(ingest_cmd, f"2b. Ingest {channel_name}")
                    ingest_out_log.append(f"--- Ingest {channel_name} ---\n{i_out}")
                    if i_stat == "Failed":
                        ingest_status = "Failed"
                else:
                    ingest_status = "Failed"
        else:
            ingest_out_log.append("No active channels found in staging directory.")
    else:
        ingest_out_log.append(f"Staging directory not found: {staging_dir}")
        
    stats['ingestion_status'] = ingest_status
    stats['ingestion_output'] = "\n\n".join(ingest_out_log)

    # --- PHASE 3: VIDEO GENERATION ---
    video_cmd = [
        sys.executable, "-u", 
        str(PROJECT_ROOT / "scripts" / "story_maker" / "run_pipeline.py"),
        "--video-dim", "-0.15",
        "--thumb-dim", "-0.15"
    ]
    v_stat, v_out = run_command(video_cmd, "3. Video Generation")
    stats['pipeline_status'] = v_stat
    stats['pipeline_output'] = v_out
    
    # --- PHASE 4: UPLOAD ---
    # Uploading via YouTube Native Scheduling targeting Peak US Hours with dynamic spacing
    upload_cmd = [sys.executable, "-u", str(PROJECT_ROOT / "scripts" / "story_maker" / "run_upload.py"), "--schedule", "--peak-us", "--dynamic-interval"]
    u_stat, u_out = run_command(upload_cmd, "4. YouTube Upload")
    stats['upload_status'] = u_stat
    stats['upload_output'] = u_out
    
    # --- PHASE 5: LOCAL BACKUP ---
    backup_cmd = [sys.executable, "-u", str(PROJECT_ROOT / "scripts" / "utils" / "backup_manager.py")]
    b_stat, b_out = run_command(backup_cmd, "5a. Local Backup")
    stats['backup_status'] = b_stat
    stats['backup_output'] = b_out
    
    # Extract the zip path from the backup output to pass to the drive uploader
    zip_path = None
    if b_stat == "Success":
        for line in b_out.split('\n'):
            if "[SUCCESS] Backup saved to:" in line:
                zip_path = line.split("Backup saved to:")[1].strip()
                break
                
    # --- PHASE 5b: GOOGLE DRIVE UPLOAD ---
    if zip_path:
        drive_cmd = [sys.executable, "-u", str(PROJECT_ROOT / "scripts" / "utils" / "upload_to_drive.py"), zip_path]
        d_stat, d_out = run_command(drive_cmd, "5b. Google Drive Upload")
        stats['drive_status'] = d_stat
        stats['drive_output'] = d_out
    else:
        stats['drive_status'] = "Skipped"
        stats['drive_output'] = "Skipped because local backup failed or was not found."
    
    # --- REPORTING ---
    logger.info("=== Autopilot Execution Complete. Sending Daily Report ===")
    html_report = get_daily_report_template(stats)
    
    # Gather thumbnails to attach
    attachments = []
    thumbnails_file = PROJECT_ROOT / "data" / "metrics" / "uploaded_thumbnails.txt"
    if thumbnails_file.exists():
        with open(thumbnails_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            attachments = list(dict.fromkeys(lines))  # Remove duplicates while preserving order
        thumbnails_file.unlink() # Cleanup

    # Determine subject based on overall success
    any_failures = any(s == "Failed" for s in [
        stats.get('scraper_status'), 
        stats.get('ingestion_status'), 
        stats.get('pipeline_status'), 
        stats.get('upload_status'),
        stats.get('backup_status'),
        stats.get('drive_status')
    ])
    
    subject = "⚠️ ShortsForge Daily Report: Issues Detected" if any_failures else "✅ ShortsForge Daily Report: Success"
    save_local_report(subject, html_report)
    send_email(subject, html_report, attachments=attachments)
    
    logger.info("Autopilot fully terminated.")

if __name__ == "__main__":
    main()
