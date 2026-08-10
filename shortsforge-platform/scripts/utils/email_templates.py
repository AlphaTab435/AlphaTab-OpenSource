def get_crash_alert_template(phase: str, error_msg: str, traceback_str: str) -> str:
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="background-color: #ffebee; padding: 20px; border-radius: 5px; border-left: 5px solid #f44336;">
                <h2 style="color: #d32f2f; margin-top: 0;">⚠️ ShortsForge Crash Alert</h2>
                <p><strong>Phase:</strong> {phase}</p>
                <p><strong>Error:</strong> {error_msg}</p>
                <hr style="border: 1px solid #ffcdd2;" />
                <p><strong>Traceback:</strong></p>
                <pre style="background-color: #fff; padding: 10px; border: 1px solid #ccc; overflow-x: auto;">{traceback_str}</pre>
            </div>
        </body>
    </html>
    """

def get_daily_report_template(stats: dict) -> str:
    """
    stats = {
        'scraper_status': 'Success' | 'Failed',
        'scraper_output': '...',
        'ingestion_status': 'Success' | 'Failed',
        'ingestion_output': '...',
        'pipeline_status': 'Success' | 'Failed',
        'pipeline_output': '...',
        'upload_status': 'Success' | 'Failed',
        'upload_output': '...',
        'backup_status': 'Success' | 'Failed',
        'backup_output': '...',
        'drive_status': 'Success' | 'Failed' | 'Skipped',
        'drive_output': '...',
    }
    """
    
    def status_color(status):
        return "#4CAF50" if status == "Success" else "#F44336" if status == "Failed" else "#FF9800"

    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333; max-width: 800px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f5f5f5; padding: 20px; border-radius: 8px;">
                <h1 style="color: #2c3e50; margin-top: 0;">🤖 ShortsForge Daily Report</h1>
                
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                    <tr style="background-color: #e0e0e0;">
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ccc;">Phase</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ccc;">Status</th>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">1. Scraper</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: {status_color(stats.get('scraper_status'))}">{stats.get('scraper_status', 'Skipped')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">2. Zipping & Ingestion</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: {status_color(stats.get('ingestion_status'))}">{stats.get('ingestion_status', 'Skipped')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">3. Video Generation</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: {status_color(stats.get('pipeline_status'))}">{stats.get('pipeline_status', 'Skipped')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">4. YouTube Upload</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: {status_color(stats.get('upload_status'))}">{stats.get('upload_status', 'Skipped')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">5a. Local Backup</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: {status_color(stats.get('backup_status'))}">{stats.get('backup_status', 'Skipped')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">5b. Google Drive Upload</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: {status_color(stats.get('drive_status'))}">{stats.get('drive_status', 'Skipped')}</td>
                    </tr>
                </table>

                <h3 style="color: #2c3e50; margin-top: 30px;">Raw Logs:</h3>
                
                <h4 style="margin-bottom: 5px;">Scraper Output</h4>
                <pre style="background-color: #fff; padding: 10px; border: 1px solid #ccc; font-size: 12px; overflow-y: auto; max-height: 150px;">{stats.get('scraper_output', 'None')}</pre>
                
                <h4 style="margin-bottom: 5px;">Ingestion Output</h4>
                <pre style="background-color: #fff; padding: 10px; border: 1px solid #ccc; font-size: 12px; overflow-y: auto; max-height: 150px;">{stats.get('ingestion_output', 'None')}</pre>
                
                <h4 style="margin-bottom: 5px;">Video Generation Output</h4>
                <pre style="background-color: #fff; padding: 10px; border: 1px solid #ccc; font-size: 12px; overflow-y: auto; max-height: 150px;">{stats.get('pipeline_output', 'None')}</pre>
                
                <h4 style="margin-bottom: 5px;">Upload Output</h4>
                <pre style="background-color: #fff; padding: 10px; border: 1px solid #ccc; font-size: 12px; overflow-y: auto; max-height: 150px;">{stats.get('upload_output', 'None')}</pre>
                
                <h4 style="margin-bottom: 5px;">Backup & Drive Output</h4>
                <pre style="background-color: #fff; padding: 10px; border: 1px solid #ccc; font-size: 12px; overflow-y: auto; max-height: 150px;">{stats.get('backup_output', 'None')}\n{stats.get('drive_output', '')}</pre>
            </div>
        </body>
    </html>
    """
