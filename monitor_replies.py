import imaplib
import email
from email.header import decode_header
import time
import datetime
from config import MAIL_HOST, MAIL_USERNAME, MAIL_PASSWORD 
from database import update_outreach_status, get_details_by_investor_email, init_db

CHECK_INTERVAL_SECONDS = 300 

POSITIVE_KEYWORDS = [
    "interested", "yes", "connect", "schedule", "call", "meet",
    "learn more", "love to", "happy to", "would like to", "open to"
]
NEGATIVE_KEYWORDS = [
    "not interested", "no thanks", "not a fit", "pass", "decline",
    "unfortunately", "unable to", "not right now", "no capacity"
]

def decode_mime_words(s):
    if not s:
        return ""
    decoded_bytes_list = decode_header(s)
    decoded_string = ""
    for decoded_bytes, charset in decoded_bytes_list:
        if isinstance(decoded_bytes, bytes):
            try:
                decoded_string += decoded_bytes.decode(charset or 'utf-8', errors='replace')
            except LookupError:
                decoded_string += decoded_bytes.decode('utf-8', errors='replace')
            except UnicodeDecodeError as e:
                print(f"UnicodeDecodeError: {e}")
                decoded_string += decoded_bytes.decode('latin-1', errors='replace') 
        elif isinstance(decoded_bytes, str):
            decoded_string += decoded_bytes
    return decoded_string

def get_plain_text_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    charset = part.get_content_charset() or 'utf-8'
                    body = part.get_payload(decode=True).decode(charset, errors='replace')
                    return body
                except Exception as e:
                    print(f"Error decoding part: {e}")
                    try:
                        return part.get_payload(decode=True).decode('utf-8', errors='replace')
                    except:
                        return None
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            try:
                charset = msg.get_content_charset() or 'utf-8'
                body = msg.get_payload(decode=True).decode(charset, errors='replace')
                return body
            except Exception as e:
                print(f"Error decoding non-multipart: {e}")
                try:
                    return msg.get_payload(decode=True).decode('utf-8', errors='replace')
                except:
                    return None
    return None


def check_for_replies():
    print(f"\n[{datetime.datetime.now()}] Checking for replies...")
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(MAIL_HOST)
        mail.login(MAIL_USERNAME, MAIL_PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            print("Error searching for emails:", messages)
            if mail:
                mail.logout() 
            return

        if not messages[0]:
            print("No unseen emails found.")
            if mail:
                mail.logout()
            return

        message_ids = messages[0].split()
        print(f"Found {len(message_ids)} unseen email(s).")

        for msg_id in message_ids:
            current_msg_id_str = msg_id.decode()
            print(f"Processing message ID: {current_msg_id_str}")
            processed = False  # Flag to track if we should mark as Seen
            try:
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    print(f"Error fetching email {current_msg_id_str}: {msg_data}")
                    continue

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = decode_mime_words(msg["subject"])
                        from_header = decode_mime_words(msg["from"])
                        sender_email = email.utils.parseaddr(from_header)[1].lower()

                        print(f"  From: {sender_email} | Subject: {subject}")

                        outreach_details = get_details_by_investor_email(sender_email)

                        if outreach_details:
                            print(f"  Match found for tracked investor: {sender_email}. Analyzing reply...")
                            body = get_plain_text_body(msg)

                            if body:
                                body_lower = body.lower()
                                is_positive = any(keyword in body_lower for keyword in POSITIVE_KEYWORDS)
                                is_negative = any(keyword in body_lower for keyword in NEGATIVE_KEYWORDS)

                                status_to_set = "replied_other"  # Default if neither positive nor negative
                                if is_positive and not is_negative:  # Simple logic: prioritize positive if no negative detected
                                    status_to_set = "replied_positive"
                                    print(f"  POSITIVE intent detected for {sender_email}.")
                                elif is_negative:
                                    status_to_set = "replied_negative"
                                    print(f"  NEGATIVE intent detected for {sender_email}.")
                                else:
                                    print(f"  Neutral or unclear intent detected for {sender_email}.")

                                status_updated = update_outreach_status(sender_email, status_to_set,
                                                                        datetime.datetime.now())
                                if status_updated:
                                    processed = True  # Successfully updated DB status, mark email as seen

                                else:
                                    print(
                                        f"  DB status update failed for {sender_email} (maybe already updated?).")
                                    processed = False


                            else:  # Could not get body
                                print(
                                    f"  Could not extract plain text body for {sender_email}. Cannot determine intent.")
                                status_updated = update_outreach_status(sender_email, "error_parsing_reply",
                                                                        datetime.datetime.now())
                                processed = status_updated  # Mark seen only if DB update worked

                        else:  # Sender not found in DB with status 'sent'
                            print(f"  Sender {sender_email} not found in tracked 'sent' outreach. Ignoring reply.")

            except Exception as e:
                print(f"Error processing message {current_msg_id_str}: {e}")
                import traceback
                traceback.print_exc()
                processed = False  # Don't mark as seen on error

            finally:
                if processed:
                    try:
                        status, _ = mail.store(msg_id, '+FLAGS', '\\Seen')
                        if status == 'OK':
                            print(f"  Marked message {current_msg_id_str} as Seen.")
                        else:
                            print(f"  Failed to mark message {current_msg_id_str} as Seen.")
                    except Exception as e_flag:
                        print(f"Error setting Seen flag for {current_msg_id_str}: {e_flag}")

    except imaplib.IMAP4.error as e:
        print(f"IMAP Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in check_for_replies: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if mail and mail.state == 'SELECTED':
            try:
                mail.close()  # Close mailbox before logout
            except:
                pass  # Ignore errors on close
        if mail and mail.state != 'LOGOUT':
            try:
                mail.logout()
                print("IMAP logout successful in finally block.")
            except:
                pass  # Ignore errors on logout

if __name__ == "__main__":
    print("Starting reply monitor...")
    init_db()
    while True:
        check_for_replies()
        print(f"Sleeping for {CHECK_INTERVAL_SECONDS} seconds...")
        time.sleep(CHECK_INTERVAL_SECONDS)