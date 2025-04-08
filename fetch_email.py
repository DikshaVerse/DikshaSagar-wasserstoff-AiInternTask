import os
import base64
import logging
import sqlite3
import warnings
import threading
import requests
import pickle
from datetime import datetime, timedelta
from dateutil import parser
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from transformers import pipeline
import torch
from typing import Dict, List, Any
from functools import wraps
from email.mime.text import MIMEText

# Configuration
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]
CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = 'token.pickle'
CALENDAR_TOKEN_FILE = 'calendar_token.json'
CREDENTIALS_FILE = 'credentials.json'
DATABASE_FILE = 'emails.db'
MAX_EMAILS = 10
MAX_TEXT_LENGTH = 1000
PROCESSING_TIMEOUT = 30
GOOGLE_API_KEY = os.environ.get('AIzaSyAhEpT9mSCNsPpDew-FN6gwrv38_gRTOvQ')
GOOGLE_CX = os.environ.get('a504f28a979e04c3d')


# Configure environment
os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore")

def timeout(seconds):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = [None]
            exception = [None]
            event = threading.Event()

            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
                finally:
                    event.set()

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()

            if not event.wait(seconds):
                thread.join(0.1)
                raise TimeoutError(f"Function timed out after {seconds} seconds")

            if exception[0] is not None:
                raise exception[0]

            return result[0]
        return wrapper
    return decorator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HuggingFaceService:
    def __init__(self):
        self.sentiment_analyzer = pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment")
        self.summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
        self.text_classifier = pipeline("zero-shot-classification")
        self.reply_generator = pipeline("text2text-generation", model="google/flan-t5-base")

    def analyze_sentiment(self, text: str) -> str:
        result = self.sentiment_analyzer(text[:MAX_TEXT_LENGTH])[0]
        label_map = {
            'LABEL_0': 'Negative',
            'LABEL_1': 'Neutral',
            'LABEL_2': 'Positive'
        }
        return label_map.get(result['label'], result['label'])  # fallback in case of unexpected label

    def generate_summary(self, text: str) -> str:
        result = self.summarizer(text[:MAX_TEXT_LENGTH], max_length=80, min_length=20, do_sample=False)[0]
        return result['summary_text']

    def detect_urgency(self, text: str) -> str:
        labels = ["High", "Medium", "Low"]
        result = self.text_classifier(text[:MAX_TEXT_LENGTH], candidate_labels=labels)
        return result['labels'][0]

    def classify_category(self, text: str) -> str:
        labels = ["meeting", "information", "other"]
        result = self.text_classifier(text[:MAX_TEXT_LENGTH], candidate_labels=labels)
        return result['labels'][0]

    def generate_reply(self, text: str) -> str:
        prompt = f"Reply to this email: {text[:200]}"
        outputs = self.reply_generator(prompt, max_length=100)
        return outputs[0]['generated_text']

    def cleanup(self):
        torch.cuda.empty_cache()

class GmailService:
    def send_reply(self, to, subject, body):
        logger.info(f"📧 Sending email to {to} with subject '{subject}'")

class CalendarService:
    def __init__(self):
        creds = None
        if os.path.exists(CALENDAR_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(CALENDAR_TOKEN_FILE, CALENDAR_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, CALENDAR_SCOPES)
                creds = flow.run_local_server(port=0)
            with open(CALENDAR_TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        self.service = build('calendar', 'v3', credentials=creds)

    def create_event(self, email):
        now = datetime.utcnow()
        event = {
            'summary': email['subject'],
            'description': email['body'],
            'start': {
                'dateTime': (now + timedelta(days=1, hours=1)).isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': (now + timedelta(days=1, hours=2)).isoformat() + 'Z',
                'timeZone': 'UTC',
            },
        }
        event = self.service.events().insert(calendarId='primary', body=event).execute()
        logger.info(f"📅 Calendar event created: {event.get('htmlLink')}")

class EmailDatabase:
    def save_email(self, email):
        logger.info(f"💾 Saving email with subject: {email['subject']}")
    def close(self):
        logger.info("🗃️ Closing database connection.")

class WebSearchService:
    def __init__(self, api_key, cx):
        self.api_key = api_key
        self.cx = cx

    def search(self, query):
        if not self.api_key or not self.cx:
            return []
        url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={self.api_key}&cx={self.cx}"
        response = requests.get(url)
        if response.status_code == 200:
            results = response.json().get('items', [])
            return [{"title": item['title'], "snippet": item['snippet'], "link": item['link']} for item in results]
        return []

class EmailProcessor:
    def __init__(self):
        self.model = HuggingFaceService()
        self.database = EmailDatabase()
        self.calendar = CalendarService()
        self.gmail = GmailService()
        self.web_search = WebSearchService(GOOGLE_API_KEY, GOOGLE_CX)

    def process_emails(self, emails):
        for email in emails:
            print("\n" + "=" * 60)
            print(f"📨 Subject: {email['subject']}")
            print(f"👤 From: {email['sender']}")
            print(f"📅 Date: {email['date']}")
            try:
                email['sentiment'] = self.model.analyze_sentiment(email['body'])
                email['summary'] = self.model.generate_summary(email['body'])
                email['urgency'] = self.model.detect_urgency(email['body'])
                email['category'] = self.model.classify_category(email['body'])

                print(f"📝 Summary: {email['summary']}")
                print(f"💬 Sentiment: {email['sentiment']} | 🚨 Urgency: {email['urgency']} | 🗂️ Category: {email['category']}")

                email['automated_reply'] = None

                if email['category'] == 'meeting':
                    self.calendar.create_event(email)
                    reply = self.model.generate_reply(email['body'])
                    if reply:
                        self.gmail.send_reply(email['sender'], f"Re: {email['subject']}", reply)
                        email['automated_reply'] = reply
                        print(f"🤖 Reply Sent: {reply}")
                elif email['category'] == 'information':
                    results = self.web_search.search(email['body'])
                    if results:
                        reply = "Hello,\n\nThanks for your question. Here are some search results I found:\n"
                        for res in results:
                            reply += f"- {res['title']}: {res['snippet']} ({res['link']})\n"
                        reply += "\nBest regards."
                        self.gmail.send_reply(email['sender'], f"Re: {email['subject']}", reply)
                        email['automated_reply'] = reply
                        print(f"🤖 Reply Sent: {reply}")
                else:
                    print("ℹ️ No automated reply sent.")

                self.database.save_email(email)

            except Exception as e:
                logger.error(f"❌ Error processing email {email.get('id', 'unknown')}: {str(e)}")

        print("\n✅ Processed Emails:\n")
        for email in emails:
            print("=" * 60)
            print(f"📨 Subject: {email['subject']}")
            print(f"👤 Sender: {email['sender']}")
            print(f"📅 Date: {email['date']}")
            print(f"📝 Summary: {email.get('summary', 'N/A')}")
            print(f"💬 Sentiment: {email.get('sentiment', 'N/A')}")
            print(f"🚨 Urgency: {email.get('urgency', 'N/A')}")
            print(f"🗂️ Category: {email.get('category', 'N/A')}")
            if email.get('automated_reply'):
                print("🤖 Automated Reply Sent:")
                print(email['automated_reply'])
            else:
                print("📭 No reply sent.")

    def cleanup(self):
        self.model.cleanup()
        self.database.close()


def display_results(emails):
    print("\nProcessed Emails:")
    for email in emails:
        print(f"\nSubject: {email['subject']}")
        print(f"Sender: {email['sender']}")
        print(f"Date: {email['date']}")
        print(f"Summary: {email['summary']}")
        print(f"Sentiment: {email['sentiment']}")
        print(f"Urgency: {email['urgency']}")
        print(f"Category: {email['category']}")
        if email.get('automated_reply'):
            print("Automated Reply Sent:")
            print(email['automated_reply'])

if __name__ == '__main__':
    try:
        logger.info("Starting email processing script...")

        # 🔐 Force OAuth at the start
        logger.info("🔐 Authenticating with Google Calendar...")
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, CALENDAR_SCOPES)
        creds = flow.run_local_server(port=0)

        # Optionally, save the token
        with open(CALENDAR_TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

        # ✅ Continue to initialize and process emails
        emails = [
            {
                'id': '001',
                'subject': 'Meeting Request',
                'sender': 'alice@example.com',
                'date': str(datetime.now()),
                'body': 'Hi, can we schedule a meeting to discuss the project status? Let me know your availability.'
            },
            {
                'id': '002',
                'subject': 'Question about services',
                'sender': 'bob@example.com',
                'date': str(datetime.now()),
                'body': 'Could you provide more information about your consulting services and pricing?'
            }
        ]

        processor = EmailProcessor()
        processor.process_emails(emails)

        display_results(emails)
        processor.cleanup()

    except Exception as e:
        logger.error(f"Application error: {str(e)}")
    finally:
        logger.info("Script execution completed")
