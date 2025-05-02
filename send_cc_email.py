import smtplib
import traceback
from email.mime.text import MIMEText
from email.utils import formataddr
import argparse
from config import (
    MAIL_HOST, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD,
    MAIL_ENCRYPTION, MAIL_FROM_ADDRESS, MAIL_FROM_NAME
)
from email_templates import get_follow_up_cc_email

def send_cc(founder_email: str, investor_email: str, investor_name: str, founder_name: str, startup_name: str) -> bool:
    """
    Sends the CC connection email using SMTP configuration from the .env file.
    Returns True on success, False on failure.
    """
    sender_login_email = MAIL_USERNAME
    print("MAIL_USERNAME", MAIL_USERNAME)
    sender_password = MAIL_PASSWORD
    sender_display_name = MAIL_FROM_NAME
    sender_from_address = MAIL_FROM_ADDRESS
    smtp_host = MAIL_HOST
    try:
        smtp_port = int(MAIL_PORT)
    except (ValueError, TypeError):
        print(f"Warning: Invalid MAIL_PORT '{MAIL_PORT}' in .env. Defaulting to 587.")
        smtp_port = 587
    use_tls = MAIL_ENCRYPTION and MAIL_ENCRYPTION.lower() == 'tls'

    if not all([sender_login_email, sender_password, smtp_host, smtp_port, sender_from_address]):
        print("ERROR: Email SMTP configuration missing in .env (MAIL_USERNAME, MAIL_PASSWORD, MAIL_HOST, MAIL_PORT, MAIL_FROM_ADDRESS)")
        return False

    try:
        template_content = get_follow_up_cc_email(investor_name, founder_name, startup_name)
        subject = template_content["subject"]
        body = template_content["body"]
    except Exception as e:
        print(f"Error generating email content from template: {e}")
        return False

    message = MIMEText(body, 'plain', 'utf-8')
    message['Subject'] = subject
    message['From'] = formataddr((sender_display_name or sender_from_address, sender_from_address))
    message['To'] = founder_email
    message['Cc'] = investor_email
    recipients = [founder_email, investor_email]

    server = None
    try:
        print(f"DEBUG: Attempting SMTP connection to {smtp_host}:{smtp_port}")
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
            server.ehlo()
            print("DEBUG: Connected via SMTP_SSL.")
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.ehlo()
            if use_tls or smtp_port == 587:
                print("DEBUG: Starting TLS...")
                server.starttls()
                server.ehlo()
                print("DEBUG: TLS Handshake successful.")
        print(f"DEBUG: Logging in as {sender_login_email}...")
        server.login(sender_login_email, sender_password)
        print("DEBUG: SMTP Login successful.")

        print(f"DEBUG: Sending CC email From: {sender_from_address} To: {recipients}...")
        server.sendmail(
            sender_from_address,
            recipients,
            message.as_string()
        )
        print("DEBUG: CC Email sent successfully via SMTP.")

        print(
            f"Successfully sent connection email to {founder_name} ({founder_email}) and CC'd {investor_name} ({investor_email}).")
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"ERROR: SMTP Authentication Error: {e}. Code: {e.smtp_code}, Detail: {e.smtp_error}")
        print("       Check MAIL_USERNAME and MAIL_PASSWORD (ensure it's an App Password for Gmail with 2FA).")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"ERROR: SMTP Connection Error: {e}. Check MAIL_HOST and MAIL_PORT.")
        return False
    except smtplib.SMTPServerDisconnected as e:
        print(f"ERROR: SMTP Server Disconnected Error: {e}.")
        return False
    except TimeoutError as e:
        print(f"ERROR: SMTP Timeout Error: {e}. Server may be slow or unreachable.")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error sending CC email: {e}")
        traceback.print_exc()
        return False
    finally:
        if server:
            try:
                print("DEBUG: Closing SMTP connection.")
                server.quit()
            except Exception as e_quit:
                print(f"Warning: Error closing SMTP connection: {e_quit}")