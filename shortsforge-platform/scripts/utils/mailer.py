import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from dotenv import load_dotenv

# Load .env file from root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))

logger = logging.getLogger(__name__)

from email.mime.application import MIMEApplication

def send_email(subject: str, html_body: str, attachments: list = None) -> bool:
    """
    Sends an email using standard SMTP.
    Requires SMTP_EMAIL, SMTP_PASSWORD, and ALERT_EMAIL in the environment or .env file.
    """
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    alert_email = os.environ.get("ALERT_EMAIL")

    if not all([smtp_email, smtp_password, alert_email]):
        logger.warning("Email settings not fully configured (missing SMTP_EMAIL, SMTP_PASSWORD, or ALERT_EMAIL). Email not sent.")
        return False

    msg = MIMEMultipart("alternative")
    msg['Subject'] = subject
    msg['From'] = f"ShortsForge Autopilot <{smtp_email}>"
    msg['To'] = alert_email

    # Attach HTML body
    part = MIMEText(html_body, 'html')
    msg.attach(part)
    
    # Attach files
    if attachments:
        for filepath in attachments:
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'rb') as f:
                        file_part = MIMEApplication(f.read(), Name=os.path.basename(filepath))
                    file_part['Content-Disposition'] = f'attachment; filename="{os.path.basename(filepath)}"'
                    msg.attach(file_part)
                except Exception as e:
                    logger.warning(f"Failed to attach file {filepath}: {e}")

    try:
        # Connect to Gmail SMTP (you can parameterize the host/port if needed later)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, alert_email, msg.as_string())
        server.quit()
        logger.info(f"Successfully sent email: '{subject}' to {alert_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

if __name__ == "__main__":
    # Test script for the user
    print("Testing mailer.py configuration...")
    success = send_email(
        subject="✅ ShortsForge Mailer Test",
        html_body="<h1>It Works!</h1><p>Your ShortsForge email notification system is perfectly configured.</p>"
    )
    if success:
        print("Test email sent successfully! Check your inbox.")
    else:
        print("Failed to send test email. Please check your .env credentials.")
