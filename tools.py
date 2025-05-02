import smtplib
import traceback
import sqlite3
from email.mime.text import MIMEText
from email.utils import make_msgid, formataddr
from langchain.tools import tool
import pandas as pd
from tabulate import tabulate

from data_loader import get_investor_dataframe 
from config import (
    MAIL_HOST, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD,
    MAIL_ENCRYPTION, MAIL_FROM_ADDRESS, MAIL_FROM_NAME
)
from database import add_sent_email_record, init_db, DB_NAME
from email_templates import get_initial_outreach_email

@tool
def search_investors(query: str) -> str:
    """
    Searches the investor database (CSV) for relevant investors based on provided criteria...
    (Your corrected search_investors function code here)
    """
    print(f"\n--- DEBUG TOOL: search_investors ---")
    print(f"DEBUG TOOL: Received query: '{query}'")
    if query is None or not isinstance(query, str) or query.strip() == "": return "Error: Please provide a valid search query string."
    df = get_investor_dataframe()
    if df is None: return "Error: Investor data could not be loaded."
    if df.empty: return "Error: Investor data is empty."
    print(f"DEBUG TOOL: DataFrame Columns: {df.columns.tolist()}")
    search_terms = [term for term in query.lower().split() if term]
    if not search_terms: return "Error: Please provide meaningful search terms."
    print(f"DEBUG TOOL: Parsed search terms: {search_terms}")
    searchable_columns = ['name', 'focusarea', 'investmentstage', 'description', 'industry', 'email']
    display_columns = ['name', 'focusarea', 'investmentstage', 'email']
    print(f"DEBUG TOOL: Searching within columns: {searchable_columns}")
    valid_searchable_columns = [col for col in searchable_columns if col in df.columns]
    if not valid_searchable_columns: return f"Error: Internal configuration issue - search columns {searchable_columns} not found in data columns: {df.columns.tolist()}."
    print(f"DEBUG TOOL: Valid searchable columns to use: {valid_searchable_columns}")
    try:
        results = df[df.apply(lambda row: any(term in str(row.get(col, '')).lower() for term in search_terms for col in valid_searchable_columns), axis=1)]
        print(f"DEBUG TOOL: Found {len(results)} rows after filtering.")
        if not results.empty:
             debug_display_cols = [col for col in ['name', 'email'] if col in results.columns]
             if debug_display_cols: print(f"DEBUG TOOL: Filtered Results Head:\n{results[debug_display_cols].head()}")
    except Exception as e:
         print(f"ERROR: Unexpected error during filtering: {e}")
         traceback.print_exc()
         return f"An unexpected error occurred during the search process: {e}"
    if results.empty:
        print("DEBUG TOOL: Results DataFrame is empty.")
        return f"No investors found matching the criteria: '{query}'"
    else:
        valid_display_columns = [col for col in display_columns if col in results.columns]
        print(f"DEBUG TOOL: Valid display columns found: {valid_display_columns}")
        if not valid_display_columns:
             fallback_cols = [col for col in ['name', 'email'] if col in results.columns]
             if fallback_cols:
                  print("DEBUG TOOL: Falling back to displaying Name/Email.")
                  valid_display_columns = fallback_cols
             else: return "Error: Could not find suitable columns (like name or email) to display results."
        try:
            table_output = tabulate(results[valid_display_columns].head(5), headers='keys', tablefmt='grid', stralign='left')
            summary = f"\n\nFound {len(results)} total matches. Showing top {min(5, len(results))}."
            print(f"DEBUG TOOL: Returning formatted results table.")
            print(f"--- END DEBUG TOOL: search_investors ---")
            return table_output + summary
        except Exception as e:
            print(f"ERROR: Error formatting results: {e}")
            traceback.print_exc()
            return f"Found {len(results)} matches, but encountered an error displaying the details."

@tool
def send_investor_email(
    investor_name: str,
    founder_email: str,
    founder_name: str,
    startup_name: str,
    startup_pitch: str
) -> str:
    """
    Sends an email to a specific investor, using a template.
    Requires: investor_name, founder_email, founder_name, startup_name, startup_pitch
    """

    print(f"\n--- DEBUG TOOL: send_investor_email ---")
    print(f"DEBUG TOOL: Received request to email investor named: '{investor_name}'")

    required_args = {
        "investor_name": investor_name,
        "founder_email": founder_email,
        "founder_name": founder_name,
        "startup_name": startup_name,
        "startup_pitch": startup_pitch
    }
    missing_args = [k for k, v in required_args.items() if not v]
    if missing_args:
        return f"Error: Missing required arguments: {', '.join(missing_args)}."

    df = get_investor_dataframe()
    if df is None:
        return "Error: Investor data could not be loaded to find email."

    investor_email = None
    investor_name_exact = None

    try:
        potential_matches = df[df['name'].str.contains(investor_name, case=False, na=False)]
        if len(potential_matches) == 1:
            matched_row = potential_matches.iloc[0]
            investor_email = matched_row.get('email')
            investor_name_exact = matched_row.get('name')
            investor_focus = matched_row.get('focusarea', "") 
            print(f"DEBUG TOOL: Found unique match for '{investor_name}': Email={investor_email}, Exact Name='{investor_name_exact}'")

        elif len(potential_matches) > 1:
            print(f"ERROR: Found multiple investors matching name '{investor_name}'. Cannot proceed.")
            return f"Error: Ambiguous investor name. Found multiple matches for '{investor_name}'. Please be more specific."
        else:
            print(f"ERROR: Could not find an investor with name '{investor_name}' in the data.")
            return f"Error: Investor named '{investor_name}' not found in the database."

        if not investor_email or not isinstance(investor_email, str) or '@' not in investor_email:
            print(f"ERROR: Found investor '{investor_name}' but email ('{investor_email}') is missing or invalid.")
            return f"Error: Found investor '{investor_name}' but their email address is missing or invalid in the data."

    except KeyError as e:
        print(f"ERROR: Column missing for email lookup (likely 'name' or 'email'): {e}")
        return f"Error: Required column '{e}' missing in data for email lookup."
    except Exception as e:
        print(f"ERROR: Unexpected error during investor email lookup: {e}")
        traceback.print_exc()
        return f"Error looking up investor email: {e}"

    sender_login_email = MAIL_USERNAME
    sender_password = MAIL_PASSWORD
    sender_display_name = MAIL_FROM_NAME
    sender_from_address = MAIL_FROM_ADDRESS
    smtp_host = MAIL_HOST
    try:
        smtp_port = int(MAIL_PORT)
    except (ValueError, TypeError):
        smtp_port = 587
    use_tls = MAIL_ENCRYPTION and MAIL_ENCRYPTION.lower() == 'tls'

    if not all([sender_login_email, sender_password, smtp_host, smtp_port, sender_from_address]):
        return "Error: Email credentials/server info not fully configured."

    try:
        email_content = get_initial_outreach_email(
            investor_name=investor_name_exact, 
            founder_name=founder_name,
            founder_startup_name=startup_name,
            startup_pitch=startup_pitch,
            investor_focus=investor_focus  # Pass the investor's focus area
        )
        subject = email_content["subject"]
        body = email_content["body"]

        message = MIMEText(body, 'plain', 'utf-8')
        message['Subject'] = subject
        message['From'] = formataddr((sender_display_name or sender_from_address, sender_from_address))
        message['To'] = investor_email
        message_id = make_msgid()
        message['Message-ID'] = message_id
    except Exception as e:
        print(f"ERROR: Error generating email content: {e}")
        return f"Error generating email content: {e}"


    server = None
    try:
        print(f"DEBUG: Attempting SMTP connection to {smtp_host}:{smtp_port}")
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.ehlo()
            if use_tls or smtp_port == 587:
                print("DEBUG: Starting TLS...")
                server.starttls()
                server.ehlo()
                print("DEBUG: TLS Handshake successful.")
        print(f"DEBUG: Logging in as {sender_login_email}...")
        server.login(sender_login_email, sender_password)
        print("DEBUG: SMTP Login successful.")
        print(f"DEBUG: Sending email From: {sender_from_address} To: {investor_email}...")
        server.sendmail(sender_from_address, [investor_email], message.as_string())
        print("DEBUG: Email sent successfully via SMTP.")

        print("DEBUG: Attempting to record send in database...")
        record_added = add_sent_email_record(
            investor_email=investor_email,
            investor_name=investor_name_exact,
            founder_email=founder_email,
            founder_name=founder_name,
            startup_name=startup_name,
            message_id=message_id
        )
        db_msg = " (DB record added)" if record_added else " (DB record FAILED)"
        print(f"DEBUG: Database record attempt status: {db_msg}")
        print(f"--- END DEBUG TOOL: send_investor_email (Success) ---")
        return f"Email successfully sent to {investor_name_exact} at {investor_email}." + db_msg

    except smtplib.SMTPAuthenticationError as e:
        print(f"ERROR: SMTP Auth Error: {e}. Code: {e.smtp_code}, Detail: {e.smtp_error}")
        return f"Error: SMTP Authentication failed ({e.smtp_code}). Check credentials. {e.smtp_error}"
    except Exception as e:
        print(f"ERROR: Unexpected error sending email: {e}")
        traceback.print_exc()
        return f"Error: Failed to send email to {investor_name}. Details: {e}"
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass

@tool
def check_investor_outreach_status(investor_email: str) -> str:
    """Checks the database for the latest recorded status..."""
    print(f"\n--- DEBUG TOOL: check_investor_outreach_status ---")
    print(f"DEBUG TOOL: Checking status for: '{investor_email}'")
    if not investor_email or not isinstance(investor_email, str): return "Error: Please provide a valid investor email address string."
    normalized_email = investor_email.lower().strip()
    conn = None
    try:
        init_db()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        print(f"DEBUG TOOL: Querying database for status of {normalized_email}...")
        cursor.execute("SELECT status, sent_timestamp, reply_timestamp FROM outreach WHERE investor_email = ? ORDER BY sent_timestamp DESC LIMIT 1", (normalized_email,))
        row = cursor.fetchone()
        if row:
            status, sent_ts, reply_ts = row
            sent_ts_str = f" (Outreach sent: {pd.to_datetime(sent_ts).strftime('%Y-%m-%d %H:%M')})" if sent_ts else ""
            reply_ts_str = f" (Reply detected: {pd.to_datetime(reply_ts).strftime('%Y-%m-%d %H:%M')})" if reply_ts else ""
            status_msg = f"Status for {normalized_email}: '{status}'.{sent_ts_str}{reply_ts_str}"
            print(f"DEBUG TOOL: Found status: {status} | Sent: {sent_ts} | Replied: {reply_ts}")
            print(f"--- END DEBUG TOOL: check_investor_outreach_status (Found) ---")
            return status_msg
        else:
            print(f"DEBUG TOOL: No outreach record found.")
            print(f"--- END DEBUG TOOL: check_investor_outreach_status (Not Found) ---")
            return f"No outreach record found for investor email: {normalized_email}"
    except sqlite3.Error as e:
        print(f"ERROR: Database error checking status: {e}")
        traceback.print_exc()
        return f"Error checking status due to database issue: {e}"
    except Exception as e:
        print(f"ERROR: Unexpected error checking status: {e}")
        traceback.print_exc()
        return f"An unexpected error occurred while checking status: {e}"
    finally:
         if conn:
             try: conn.close()
             except Exception: pass