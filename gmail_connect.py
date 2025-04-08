import os
import base64
import logging
import pickle
import sqlite3
import warnings
from datetime import datetime
from dateutil import parser
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from transformers import pipeline, logging as transformers_logging
import torch
from typing import Dict, List, Any, Optional

# Configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'
DATABASE_FILE = 'emails.db'
MAX_EMAILS = 10
MAX_TEXT_LENGTH = 1024

# Suppress warnings
transformers_logging.set_verbosity_error()
warnings.filterwarnings("ignore", message="`huggingface_hub` cache-system uses symlinks")
warnings.filterwarnings("ignore", message="Your max_length is set to")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GmailService:
    def __init__(self):
        self.service = self._authenticate()

    def _authenticate(self) -> Any:
        """Authenticate with Gmail API"""
        creds = None
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        return build('gmail', 'v1', credentials=creds, static_discovery=False)

    def fetch_emails(self) -> List[Dict[str, Any]]:
        """Fetch unread emails from inbox"""
        try:
            result = self.service.users().messages().list(
                userId='me',
                labelIds=['INBOX', 'UNREAD'],
                maxResults=MAX_EMAILS
            ).execute()
            
            return [self._parse_email(msg) for msg in result.get('messages', [])]
            
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
            
            return {
                'message_id': msg_data['id'],
                'thread_id': msg_data.get('threadId', ''),
                'sender': headers.get('from', ''),
                'recipient': headers.get('to', ''),
                'subject': headers.get('subject', 'No Subject'),
                'date': self._parse_date(headers.get('date', '')),
                'body': self._extract_body(msg_data)
            }
        except Exception as e:
            logger.error(f"Failed to process message {msg['id']}: {str(e)}")
            return {}

    def _extract_body(self, msg_data: Dict) -> str:
        """Extract email body text"""
        if 'parts' in msg_data['payload']:
            for part in msg_data['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    return self._decode_body(part['body'].get('data', ''))
        return self._decode_body(msg_data['payload']['body'].get('data', ''))

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
        
        if not HuggingFaceService._models_initialized:
            logger.info(f"Initializing HuggingFace models on {self.device}")
            
            self.sentiment_pipe = pipeline(
                "text-classification",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=self.device,
                top_k=None,
                truncation=True,
                max_length=MAX_TEXT_LENGTH
            )
            
            self.summarizer = pipeline(
                "summarization",
                model="facebook/bart-large-cnn",
                device=self.device,
                truncation=True,
                max_length=MAX_TEXT_LENGTH
            )
            
            HuggingFaceService._models_initialized = True

    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Enhanced sentiment analysis with input validation"""
        if not text or len(text.strip()) < 5:
            return {'POSITIVE': 0.0, 'NEGATIVE': 0.0, 'NEUTRAL': 1.0}
        
        try:
            results = self.sentiment_pipe(text[:MAX_TEXT_LENGTH])[0]
            return {res['label'].upper(): res['score'] for res in results}
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {str(e)}")
            return {'POSITIVE': 0.0, 'NEGATIVE': 0.0, 'NEUTRAL': 1.0}

    def generate_summary(self, text: str) -> str:
        """Smart summarization with dynamic length"""
        if not text:
            return ""
            
        try:
            words = text.split()
            if len(words) < 15:
                return ' '.join(words[:20]) + ('...' if len(words) > 20 else '')
            
            max_len = min(150, max(40, len(words)//2))
            summary = self.summarizer(
                text[:MAX_TEXT_LENGTH],
                max_length=max_len,
                min_length=max(20, max_len//3),
                do_sample=False
            )[0]['summary_text']
            
            return summary.strip() + ('...' if summary and summary[-1] not in {'.', '!', '?'} else '')
        except Exception as e:
            logger.error(f"Summarization failed: {str(e)}")
            return ' '.join(text.split()[:25]) + ('...' if len(text.split()) > 25 else '')

    def detect_urgency(self, text: str) -> int:
        """Enhanced urgency detection (0-2 scale)"""
        if not text:
            return 0
            
        text_lower = text.lower()
        urgent_phrases = [
            'last call', 'disappear at', 'closing today',
            'deadline', 'act now', 'limited time', 'final notice'
        ]
        
        important_phrases = [
            'important', 'update', 'alert', 'verify',
            'action required', 'respond', 'attention'
        ]
        
        if any(phrase in text_lower for phrase in urgent_phrases):
            return 2
        elif any(phrase in text_lower for phrase in important_phrases):
            return 1
        return 0

    def classify_category(self, text: str) -> str:
        """Smart email categorization"""
        if not text:
            return 'general'
            
        text_lower = text.lower()
        category_map = {
            'finance': ['upi', 'transaction', 'bank', 'hdfc', 'payment', 'account', 'billing'],
            'jobs': ['job', 'career', 'hiring', 'role', 'apply', 'recruitment', 'position'],
            'promotions': ['sale', 'offer', 'deal', 'discount', 'new!', '💖', 'promo'],
            'opportunities': ['referral', 'earn', 'program', 'income', 'reward'],
            'government': ['ministry', 'bharat', 'defence', 'dynamics', 'govt'],
            'security': ['otp', 'login', 'verification', 'alert', 'security']
        }
        
        for category, keywords in category_map.items():
            if any(kw in text_lower for kw in keywords):
                return category
        return 'general'

    def suggest_action(self, category: str, urgency: int) -> str:
        """Suggest appropriate response action"""
        if urgency == 2:
            return "Respond immediately"
        elif category == "finance":
            return "Review within 24 hours"
        elif category == "jobs":
            return "Follow up if interested"
        elif urgency == 1:
            return "Address soon"
        return "Read when available"

    def cleanup(self):
        """Release resources"""
        if hasattr(self, 'sentiment_pipe'):
            del self.sentiment_pipe
        if hasattr(self, 'summarizer'):
            del self.summarizer
        torch.cuda.empty_cache()

class EmailDatabase:
    def __init__(self, db_path: str = DATABASE_FILE):
        self.conn = sqlite3.connect(db_path)
        self._init_db()
        
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
                category TEXT,
                urgency INTEGER,
                summary TEXT,
                action TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self._create_indexes()
        self.conn.commit()
        logger.info("Database initialized")

    def _create_indexes(self):
        """Create query optimization indexes"""
        cursor = self.conn.cursor()
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON emails(category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_urgency ON emails(urgency)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON emails(date)')

    def save_email(self, email_data: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
        """Save email with analysis"""
        if not email_data or not analysis:
            return False
            
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO emails (
                    message_id, thread_id, sender, recipient,
                    subject, body, date, sentiment_pos, sentiment_neg,
                    sentiment_neu, category, urgency, summary, action
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                email_data.get('message_id'),
                email_data.get('thread_id'),
                email_data.get('sender'),
                email_data.get('recipient'),
                email_data.get('subject', 'No Subject'),
                email_data.get('body', ''),
                email_data.get('date', datetime.now().isoformat()),
                analysis.get('sentiment', {}).get('POSITIVE', 0),
                analysis.get('sentiment', {}).get('NEGATIVE', 0),
                analysis.get('sentiment', {}).get('NEUTRAL', 0),
                analysis.get('category', 'general'),
                analysis.get('urgency', 0),
                analysis.get('summary', ''),
                analysis.get('action', '')
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Database save failed: {str(e)}")
            return False

    def close(self):
        """Close database connection"""
        self.conn.close()

class EmailProcessor:
    def __init__(self):
        self.gmail = GmailService()
        self.hf = HuggingFaceService()
        self.db = EmailDatabase()
        logger.info("All services initialized")

    def process_emails(self) -> None:
        """Process all unread emails"""
        emails = [e for e in self.gmail.fetch_emails() if e]  # Filter empty
        if not emails:
            logger.info("No new emails found")
            return
        
        logger.info(f"Processing {len(emails)} emails...")
        success_count = 0
        
        for email in emails:
            try:
                analysis = self._analyze_email(email)
                if self.db.save_email(email, analysis):
                    success_count += 1
                    self._log_analysis(email, analysis)
            except Exception as e:
                logger.error(f"Error processing email: {str(e)}")
        
        logger.info(f"Completed: {success_count}/{len(emails)} processed")

    def _analyze_email(self, email: Dict) -> Dict:
        """Perform all analyses on an email"""
        body = email.get('body', '')
        sentiment = self.hf.analyze_sentiment(body)
        category = self.hf.classify_category(body)
        urgency = self.hf.detect_urgency(body)
        
        return {
            'sentiment': sentiment,
            'summary': self.hf.generate_summary(body),
            'urgency': urgency,
            'category': category,
            'action': self.hf.suggest_action(category, urgency)
        }

    def _log_analysis(self, email: Dict, analysis: Dict):
        """Log analysis results"""
        logger.debug(
            f"Processed: {email.get('subject', '')[:50]}... | "
            f"Cat: {analysis.get('category')} | "
            f"Urg: {analysis.get('urgency')} | "
            f"Act: {analysis.get('action')}"
        )

    def cleanup(self):
        """Clean up resources"""
        self.hf.cleanup()
        self.db.close()

def display_results(db_path: str = DATABASE_FILE):
    """Display processed emails in a readable format"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n📧 Processed Emails:\n")
    print(f"{'Subject':<50} | {'Category':<12} | {'Urgency':<7} | Action")
    print("-" * 90)
    
    for row in cursor.execute('''
        SELECT subject, category, urgency, action 
        FROM emails 
        ORDER BY urgency DESC, date DESC
    '''):
        urgency_icon = '❗' if row[2] == 2 else '🔸' if row[2] == 1 else '  '
        print(f"{row[0][:48]:<50} | {row[1]:<12} | {urgency_icon:<2} {row[2]} | {row[3]}")
    
    conn.close()

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