import sqlite3
import datetime
import os

DB_NAME = "email_tracking.db"

def init_db():
    """Initializes the database and creates the table if it doesn't exist."""
    if os.path.exists(DB_NAME):
         print(f"Database {DB_NAME} already exists.")
    else:
         print(f"Creating database {DB_NAME}...")
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
    conn.close()
    print("Database initialized.")

def add_sent_email_record(investor_email, investor_name, founder_email, founder_name, startup_name, message_id=None):
    """Adds a record for an email that was just sent."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
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
        conn.close()

def update_outreach_status(investor_email, new_status, reply_time=None):
    """Updates the status and optionally the reply timestamp for an outreach attempt."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = datetime.datetime.now()
    try:
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
        conn.close()

def get_details_by_investor_email(investor_email):
    """Retrieves details needed for CC email, looking for status='sent'."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
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
        conn.close()
    

if __name__ != "__main__":
     init_db()