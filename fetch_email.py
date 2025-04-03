import os
import pickle
import sqlite3
import base64
import argparse
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from huggingface_service import analyze_email 

def init_db():
    """Initialize database with proper schema"""
    conn = sqlite3.connect('emails.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            recipient TEXT DEFAULT '',
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            analysis TEXT,
            is_processed BOOLEAN DEFAULT 0,
            error_count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    return conn

def authenticate_gmail():
    """Gmail API authentication with token refresh"""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json',
                ['https://www.googleapis.com/auth/gmail.readonly']
            )
            creds = flow.run_local_server(port=0)
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)

def process_email(service, db_conn, message_id):
    """Process single email with error handling"""
    try:
        msg = service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()
        
        headers = {h['name']: h['value'] for h in msg['payload']['headers']}
        
        # Extract email body
        body = ""
        if 'parts' in msg['payload']:
            for part in msg['payload']['parts']:
                if part['mimeType'] in ['text/plain', 'text/html']:
                    body += base64.urlsafe_b64decode(part['body'].get('data', '')).decode('utf-8')
        elif 'data' in msg['payload']['body']:
            body = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')
        
        email_data = {
            'sender': headers.get('From', ''),
            'recipient': headers.get('To', ''),
            'subject': headers.get('Subject', ''),
            'body': body[:5000],  # Truncate long emails
            'timestamp': datetime.fromtimestamp(int(msg['internalDate'])/1000)
        }
        
        # Store in database
        cursor = db_conn.cursor()
        cursor.execute('''
            INSERT INTO emails 
            (sender, recipient, subject, body, timestamp, analysis, is_processed) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            email_data['sender'],
            email_data['recipient'],
            email_data['subject'],
            email_data['body'],
            email_data['timestamp'],
            analyze_email(email_data),
            1
        ))
        db_conn.commit()
        
        print(f"✅ Processed: {email_data['subject'][:50]}...")
        
    except Exception as e:
        print(f"❌ Error processing email: {str(e)}")
        db_conn.rollback()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-emails', type=int, default=10, help='Max emails to process')
    args = parser.parse_args()
    
    db_conn = init_db()
    service = authenticate_gmail()
    
    try:
        print("📩 Fetching emails...")
        results = service.users().messages().list(
            userId='me',
            labelIds=['INBOX'],
            q="is:unread",
            maxResults=args.max_emails
        ).execute()
        
        messages = results.get('messages', [])
        print(f"🔍 Found {len(messages)} new emails")
        
        for i, message in enumerate(messages):
            print(f"🔄 Processing {i+1}/{len(messages)}")
            process_email(service, db_conn, message['id'])
            
    except Exception as e:
        print(f"🔥 Main error: {str(e)}")
    finally:
        db_conn.close()
        print("🏁 Processing complete")

if __name__ == '__main__':
    main()