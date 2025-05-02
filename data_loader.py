import pandas as pd
import sqlite3
import datetime
import os

INVESTOR_CSV_PATH = "investors.csv"
INVESTOR_DF = None

def load_investors():
    """Loads the investor DataFrame."""
    global INVESTOR_DF
    try:
        INVESTOR_DF = pd.read_csv(INVESTOR_CSV_PATH)
        INVESTOR_DF.columns = [col.strip().lower().replace(' ', '_') for col in INVESTOR_DF.columns]
        INVESTOR_DF = INVESTOR_DF.fillna('')
        print(f"Successfully loaded {len(INVESTOR_DF)} investors from {INVESTOR_CSV_PATH}")
        return INVESTOR_DF
    except FileNotFoundError:
        print(f"Error: Investor CSV file not found at {INVESTOR_CSV_PATH}")
        return None
    except Exception as e:
        print(f"Error loading or processing investor CSV: {e}")
        return None

def get_investor_dataframe():
    """Returns the loaded DataFrame, loading it if necessary."""
    if INVESTOR_DF is None:
        load_investors()
    return INVESTOR_DF

load_investors()

DB_NAME = "email_tracking.db"

def init_db():
    """Initializes the database and creates the table if it doesn't exist."""
    if os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} already exists.")
    else:
        print(f"Creating database {DB_NAME}...")
    conn = None 
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS outreach (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investor_email TEXT NOT NULL,
                investor_name TEXT,
                founder_email TEXT NOT NULL,
                founder_name TEXT,
                startup_name TEXT,
                sent_message_id TEXT UNIQUE, -- If you can reliably get this
                status TEXT NOT NULL DEFAULT 'unknown', -- e.g., 'sent', 'replied_positive', 'connected', 'replied_negative', 'error'
                sent_timestamp DATETIME NOT NULL,
                reply_timestamp DATETIME,
                last_checked_timestamp DATETIME
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_investor_email ON outreach (investor_email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON outreach (status)')
        conn.commit()
        print("Database initialized.")
    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")
    finally:
        if conn:
            conn.close()

def add_sent_email_record(investor_email, investor_name, founder_email, founder_name, startup_name, message_id=None):
    """Adds a record for an email that was just sent."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO outreach (investor_email, investor_name, founder_email, founder_name, startup_name, sent_message_id, status, sent_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (investor_email, investor_name, founder_email, founder_name, startup_name, message_id, 'sent', datetime.datetime.now()))
        conn.commit()
        print(f"DB: Recorded outreach to {investor_email}")
        return True
    except sqlite3.Error as e:
        print(f"DB Error adding record for {investor_email}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def update_outreach_status(investor_email, new_status, reply_time=None):
    """Updates the status and optionally the reply timestamp for an outreach attempt."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        now = datetime.datetime.now()
        if reply_time:
            cursor.execute('''
                UPDATE outreach
                SET status = ?, reply_timestamp = ?, last_checked_timestamp = ?
                WHERE investor_email = ? AND status = 'sent'
            ''', (new_status, reply_time, now, investor_email))
        else:
            cursor.execute('''
                UPDATE outreach
                SET status = ?, last_checked_timestamp = ?
                WHERE investor_email = ? AND status = 'sent'
            ''', (new_status, now, investor_email))

        updated_rows = cursor.rowcount
        conn.commit()
        if updated_rows > 0:
            print(f"DB: Updated status for {investor_email} to {new_status}")
            return True
        else:
            print(f"DB: No 'sent' record found or already updated for {investor_email} when trying to set status to {new_status}")
            return False
    except sqlite3.Error as e:
        print(f"DB Error updating status for {investor_email}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_details_by_investor_email(investor_email):
    """Retrieves details needed for CC email, looking for status='sent'."""
    conn = None 
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT founder_email, founder_name, investor_name, startup_name
            FROM outreach
            WHERE investor_email = ? AND status = 'sent'
            ORDER BY sent_timestamp DESC LIMIT 1
        ''', (investor_email,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"DB Error fetching details for {investor_email}: {e}")
        return None
    finally:
        if conn:
            conn.close()

if __name__ != "__main__":
    init_db()
