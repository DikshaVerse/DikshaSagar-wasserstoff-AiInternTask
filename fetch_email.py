import os.path
import pickle
import base64
import sqlite3
from datetime import datetime
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Authentication setup
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    """Handles Gmail API authentication"""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)

# Database functions
def init_db():
    """Initializes SQLite database"""
    conn = sqlite3.connect('emails.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emails (
        id TEXT PRIMARY KEY,
        thread_id TEXT,
        sender TEXT NOT NULL,
        recipients TEXT,
        subject TEXT,
        body TEXT,
        date TEXT,
        labels TEXT
    )
    ''')
    conn.commit()
    conn.close()

def save_email(email_data):
    """Saves email to database"""
    conn = sqlite3.connect('emails.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR IGNORE INTO emails 
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        email_data['id'],
        email_data['thread_id'],
        email_data['sender'],
        ','.join(email_data.get('recipients', [])),
        email_data['subject'],
        email_data['body'],
        email_data['date'],
        ','.join(email_data.get('labels', []))
    ))
    conn.commit()
    conn.close()

# Email processing
def get_email_body(payload):
    """Extracts email body from different email structures"""
    # Simple email with direct body data
    if 'body' in payload and 'data' in payload['body']:
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
    
    # Multipart email (HTML/plaintext/attachments)
    if 'parts' in payload:
        for part in payload['parts']:
            # Check text/plain parts first
            if part['mimeType'] == 'text/plain':
                if 'body' in part and 'data' in part['body']:
                    return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            # Fallback to text/html if plain text not available
            elif part['mimeType'] == 'text/html':
                if 'body' in part and 'data' in part['body']:
                    html_content = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    return html_content  # Or add HTML-to-text conversion here
    
    # If no body found
    return "[Email content not available]"

def fetch_and_store_emails(max_results=10):
    """Main function to fetch and store emails"""
    try:
        service = authenticate_gmail()
        init_db()
        
        results = service.users().messages().list(
            userId='me',
            maxResults=max_results
        ).execute()
        
        for msg in results.get('messages', []):
            try:
                msg_data = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                headers = msg_data['payload']['headers']
                
                email = {
                    'id': msg['id'],
                    'thread_id': msg['threadId'],
                    'sender': next((h['value'] for h in headers if h['name'] == 'From'), "Unknown Sender"),
                    'recipients': [h['value'] for h in headers if h['name'] in ['To', 'Cc', 'Bcc']],
                    'subject': next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject"),
                    'body': get_email_body(msg_data['payload']),
                    'date': next((h['value'] for h in headers if h['name'] == 'Date'), "Unknown Date"),
                    'labels': msg_data.get('labelIds', [])
                }
                
                save_email(email)
                print(f"✅ Saved: {email['subject']} (From: {email['sender']})")
                
            except Exception as e:
                print(f"⚠️ Error processing email {msg['id']}: {str(e)}")
                continue
                
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")

if __name__ == '__main__':
    fetch_and_store_emails()