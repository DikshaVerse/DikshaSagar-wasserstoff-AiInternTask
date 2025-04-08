import os
import base64
import logging
import pickle
import sqlite3
import warnings
from datetime import datetime
from dateutil import parser
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from transformers import pipeline, logging as transformers_logging
import torch

# Configuration
load_dotenv()
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'
DATABASE_FILE = 'emails.db'
MAX_EMAILS = 10
MAX_TEXT_LENGTH = 1024

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress warnings
transformers_logging.set_verbosity_error()
warnings.filterwarnings("ignore")

class GmailService:
    def __init__(self):
        self.service = self._authenticate()
        logger.info("Gmail service initialized")

    def _authenticate(self) -> Any:
        """Authenticate with Gmail API"""
        creds = None
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
                logger.debug("Loaded existing credentials from token.pickle")
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.debug("Refreshing expired credentials")
                creds.refresh(Request())
            else:
                logger.info("Starting new OAuth flow")
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
                logger.debug("Saved new credentials to token.pickle")
        
        return build('gmail', 'v1', credentials=creds, static_discovery=False)

    def fetch_emails(self) -> List[Dict[str, Any]]:
        """Fetch unread emails from inbox"""
        try:
            logger.info("Fetching unread emails")
            result = self.service.users().messages().list(
                userId='me',
                labelIds=['INBOX', 'UNREAD'],
                maxResults=MAX_EMAILS
            ).execute()
            
            messages = result.get('messages', [])
            logger.info(f"Found {len(messages)} unread emails")
            return [self._parse_email(msg) for msg in messages]
            
        except Exception as e:
            logger.error(f"Gmail API error: {str(e)}")
            return []

    def _parse_email(self, msg: Dict) -> Dict[str, Any]:
        """Parse email data"""
        try:
            msg_data = self.service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='full'
            ).execute()
            
            headers = {h['name'].lower(): h['value'] for h in msg_data['payload']['headers']}
            body = self._extract_body(msg_data)
            
            logger.debug(f"Parsed email: {headers.get('subject', 'No Subject')}")
            
            return {
                'message_id': msg_data['id'],
                'thread_id': msg_data.get('threadId', ''),
                'sender': headers.get('from', ''),
                'recipient': headers.get('to', ''),
                'subject': headers.get('subject', 'No Subject'),
                'date': self._parse_date(headers.get('date', '')),
                'body': body
            }
        except Exception as e:
            logger.error(f"Failed to process message {msg.get('id')}: {str(e)}")
            return {}

    def _extract_body(self, msg_data: Dict) -> str:
        """Extract email body text"""
        try:
            if 'parts' in msg_data['payload']:
                for part in msg_data['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        return self._decode_body(part['body'].get('data', ''))
            return self._decode_body(msg_data['payload']['body'].get('data', ''))
        except Exception as e:
            logger.warning(f"Failed to extract body: {str(e)}")
            return ''

    def _decode_body(self, data: str) -> str:
        """Decode base64 email body"""
        try:
            return base64.urlsafe_b64decode(data.encode('ASCII')).decode('utf-8')
        except:
            return ''

    def _parse_date(self, date_str: str) -> str:
        """Parse email date"""
        try:
            return parser.parse(date_str).isoformat()
        except:
            return datetime.now().isoformat()

class HuggingFaceService:
    _models_initialized = False
    
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing HuggingFace models on {self.device}")
        
        if not HuggingFaceService._models_initialized:
            try:
                self.sentiment_pipe = pipeline(
                    "text-classification",
                    model="distilbert-base-uncased-finetuned-sst-2-english",
                    device=self.device
                )
                
                self.summarizer = pipeline(
                    "summarization",
                    model="facebook/bart-large-cnn",
                    device=self.device
                )
                
                HuggingFaceService._models_initialized = True
                logger.info("HuggingFace models loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load models: {str(e)}")
                raise

    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze email sentiment"""
        if not text:
            return {'POSITIVE': 0.0, 'NEGATIVE': 0.0, 'NEUTRAL': 1.0}
        
        try:
            results = self.sentiment_pipe(text[:MAX_TEXT_LENGTH])[0]
            return {res['label'].upper(): res['score'] for res in results}
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {str(e)}")
            return {'POSITIVE': 0.0, 'NEGATIVE': 0.0, 'NEUTRAL': 1.0}

    def generate_summary(self, text: str) -> str:
        """Generate email summary"""
        if not text:
            return ""
            
        try:
            return self.summarizer(
                text[:MAX_TEXT_LENGTH],
                max_length=150,
                min_length=30,
                do_sample=False
            )[0]['summary_text']
        except Exception as e:
            logger.error(f"Summarization failed: {str(e)}")
            return text[:200] + '...'

    def cleanup(self):
        """Release resources"""
        torch.cuda.empty_cache()
        logger.info("Cleaned up HuggingFace resources")

class EmailDatabase:
    def __init__(self, db_path: str = DATABASE_FILE):
        self.conn = sqlite3.connect(db_path)
        self._init_db()
        logger.info(f"Database initialized at {db_path}")
        
    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                message_id TEXT PRIMARY KEY,
                thread_id TEXT,
                sender TEXT,
                recipient TEXT,
                subject TEXT,
                body TEXT,
                date TIMESTAMP,
                sentiment_pos REAL,
                sentiment_neg REAL,
                sentiment_neu REAL,
                summary TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def save_email(self, email_data: Dict, analysis: Dict) -> bool:
        """Save email with analysis"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO emails (
                    message_id, thread_id, sender, recipient,
                    subject, body, date, sentiment_pos, sentiment_neg,
                    sentiment_neu, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                email_data.get('message_id'),
                email_data.get('thread_id'),
                email_data.get('sender'),
                email_data.get('recipient'),
                email_data.get('subject', 'No Subject'),
                email_data.get('body', ''),
                email_data.get('date'),
                analysis.get('sentiment', {}).get('POSITIVE', 0),
                analysis.get('sentiment', {}).get('NEGATIVE', 0),
                analysis.get('sentiment', {}).get('NEUTRAL', 0),
                analysis.get('summary', '')
            ))
            self.conn.commit()
            logger.debug(f"Saved email: {email_data.get('subject')}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Database save failed: {str(e)}")
            return False

    def close(self):
        """Close database connection"""
        self.conn.close()
        logger.info("Database connection closed")

class EmailProcessor:
    def __init__(self):
        logger.info("Initializing EmailProcessor")
        self.gmail = GmailService()
        self.hf = HuggingFaceService()
        self.db = EmailDatabase()
        logger.info("All services initialized")

    def process_emails(self) -> None:
        """Process all unread emails"""
        logger.info("Starting email processing")
        emails = [e for e in self.gmail.fetch_emails() if e]  # Filter empty
        if not emails:
            logger.info("No new emails found")
            return
        
        logger.info(f"Processing {len(emails)} emails...")
        success_count = 0
        
        for email in emails:
            try:
                logger.debug(f"Processing email: {email.get('subject')}")
                analysis = self._analyze_email(email)
                if self.db.save_email(email, analysis):
                    success_count += 1
                    self._log_analysis(email, analysis)
            except Exception as e:
                logger.error(f"Error processing email: {str(e)}")
        
        logger.info(f"Completed: {success_count}/{len(emails)} emails processed")

    def _analyze_email(self, email: Dict) -> Dict:
        """Perform all analyses on an email"""
        body = email.get('body', '')
        logger.debug(f"Analyzing email: {email.get('subject')}")
        
        return {
            'sentiment': self.hf.analyze_sentiment(body),
            'summary': self.hf.generate_summary(body)
        }

    def _log_analysis(self, email: Dict, analysis: Dict):
        """Log analysis results"""
        logger.info(
            f"Processed: {email.get('subject', '')[:50]}... | "
            f"Sentiment: POS={analysis['sentiment']['POSITIVE']:.2f} "
            f"NEG={analysis['sentiment']['NEGATIVE']:.2f} | "
            f"Summary: {analysis['summary'][:50]}..."
        )

    def cleanup(self):
        """Clean up resources"""
        self.hf.cleanup()
        self.db.close()
        logger.info("Processor cleanup complete")

def display_results(db_path: str = DATABASE_FILE):
    """Display processed emails in a readable format"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("\n📧 Processed Emails:\n")
        print(f"{'Subject':<50} | {'Sender':<30} | {'Date'}")
        print("-" * 90)
        
        for row in cursor.execute('''
            SELECT subject, sender, date FROM emails ORDER BY date DESC LIMIT 10
        '''):
            print(f"{row[0][:48]:<50} | {row[1][:28]:<30} | {row[2][:19]}")
        
        conn.close()
    except Exception as e:
        print(f"Error displaying results: {str(e)}")

if __name__ == "__main__":
    processor = None
    try:
        # Initialize and process emails
        processor = EmailProcessor()
        processor.process_emails()
        
        # Display results
        display_results()
        
    except Exception as e:
        logger.error(f"Application failed: {str(e)}")
    finally:
        if processor:
            processor.cleanup()