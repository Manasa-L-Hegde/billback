import os, smtplib, time
from pathlib import Path
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
DEMO_VENDOR_EMAIL = os.environ.get("DEMO_VENDOR_EMAIL", "")
DRY_RUN = os.environ.get("DRY_RUN", "1") == "1"

def send_email(to, subject, body):
    """
    Sends an email via Gmail SMTP (SSL 465) if configured and DRY_RUN=0.
    Always records a copy to outbox/ for audit trail.
    """
    outbox_dir = Path("outbox")
    outbox_dir.mkdir(exist_ok=True)
    
    timestamp = int(time.time())
    out_file = outbox_dir / f"sent_{timestamp}_{os.getpid()}.txt"
    
    # Target recipient: prefer DEMO_VENDOR_EMAIL in test environments if available
    recipient = DEMO_VENDOR_EMAIL if DEMO_VENDOR_EMAIL else to

    email_content = f"To: {recipient}\nSubject: {subject}\nDate: {time.ctime()}\n\n{body}"
    out_file.write_text(email_content, encoding="utf-8")

    if not DRY_RUN and GMAIL_USER and GMAIL_APP_PASSWORD:
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = GMAIL_USER
            msg["To"] = recipient

            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
                server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                server.sendmail(GMAIL_USER, [recipient], msg.as_string())

            return {
                "status": "sent via Gmail SMTP",
                "recipient": recipient,
                "file": str(out_file)
            }
        except Exception as e:
            return {
                "status": f"smtp_failed: {str(e)} (fallback to saved dry run)",
                "recipient": recipient,
                "file": str(out_file)
            }

    return {
        "status": "saved (dry run)",
        "recipient": recipient,
        "file": str(out_file)
    }

if __name__ == "__main__":
    res = send_email("vendor@example.com", "Test Dispute", "This is a test dispute email.")
    print(res)

