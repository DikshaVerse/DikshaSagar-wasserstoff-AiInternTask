import sqlite3
from datetime import datetime

# Initialize database
def init_db():
    conn = sqlite3.connect('emails.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emails (
        id TEXT PRIMARY KEY,
        thread_id TEXT,
        sender TEXT NOT NULL,
        subject TEXT,
        body TEXT,
        date TEXT
    )
    ''')
    conn.commit()
    conn.close()

# Save email to database
def save_email(email_id, thread_id, sender, subject, body, date):
    conn = sqlite3.connect('emails.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR IGNORE INTO emails 
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (email_id, thread_id, sender, subject, body, date))
    conn.commit()
    conn.close()