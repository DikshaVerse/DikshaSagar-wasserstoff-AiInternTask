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
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
load_dotenv()

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
SLACK_BOT_TOKEN = os.environ.get('xoxe.xoxp-1Mi0yLTg3MTQxMzY3MjM2MzQtODcxNDEzNjcyMzY4Mi04NzIwODU0NzQ0NjU5LTg3MjA4NTQ5Mzk4NTktOTk5MjYzODljNzRhNzViZjAyMjE1YWFjM2QzNjMzYzA4ZDhkOGYwYTAxYmM2MTg3MGVkODQ5ZmUyOTU4ODE4Nw')
SLACK_CHANNEL_ID = os.environ.get('A08LZN0PXKM')

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

class SlackService:
    def __init__(self, token: str, channel_id: str):
        self.client = WebClient(token=token)
        self.channel_id = channel_id

    def send_message(self, text: str):
        try:
            response = self.client.chat_postMessage(
                channel=self.channel_id,
                text=text
            )
            logger.info(f"Slack message sent: {response['ts']}")
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")

class HuggingFaceService:
    def __init__(self):
        self.sentiment_analyzer = pipeline("sentiment-analysis")
        self.summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
        self.text_classifier = pipeline("zero-shot-classification")
        self.reply_generator = pipeline("text-generation", model="gpt2")

    def analyze_sentiment(self, text: str) -> str:
        result = self.sentiment_analyzer(text[:MAX_TEXT_LENGTH])[0]
        return result['label']

    def generate_summary(self, text: str) -> str:
        result = self.summarizer(text[:MAX_TEXT_LENGTH])[0]
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
        prompt = f"Reply to: {text[:200]}\n\nResponse:"
        outputs = self.reply_generator(prompt, max_length=100, num_return_sequences=1)
        return outputs[0]['generated_text']

    def cleanup(self):
        torch.cuda.empty_cache()

# Dummy service class definitions
class GmailService:
    def send_reply(self, to, subject, body):
        logger.info(f"Sending email to {to} with subject '{subject}'")

class CalendarService:
    def create_event(self, email):
        logger.info(f"Creating calendar event for: {email['subject']}")

class EmailDatabase:
    def save_email(self, email):
        logger.info(f"Saving email with subject: {email['subject']}")
    def close(self):
        logger.info("Closing database connection.")

class WebSearchService:
    def __init__(self, api_key, cx):
        pass
    def search(self, query):
        return [
            {"title": "Example result", "snippet": "Example snippet", "link": "http://example.com"}
        ]

class EmailProcessor:
    def __init__(self):
        self.model = HuggingFaceService()
        self.database = EmailDatabase()
        self.calendar = CalendarService()
        self.gmail = GmailService()
        self.web_search = WebSearchService(GOOGLE_API_KEY, GOOGLE_CX)
        self.slack = SlackService(SLACK_BOT_TOKEN, SLACK_CHANNEL_ID)

    def process_emails(self, emails):
        for email in emails:
            try:
                email['sentiment'] = self.model.analyze_sentiment(email['body'])
                email['summary'] = self.model.generate_summary(email['body'])
                email['urgency'] = self.model.detect_urgency(email['body'])
                email['category'] = self.model.classify_category(email['body'])

                if email['urgency'] == 'High' or email['sentiment'].upper() == 'NEGATIVE' or email['category'] == 'meeting':
                    slack_msg = (
                        f"*📬 Important Email Received!*\n"
                        f"*Subject:* {email['subject']}\n"
                        f"*From:* {email['sender']}\n"
                        f"*Urgency:* {email['urgency']}\n"
                        f"*Sentiment:* {email['sentiment']}\n"
                        f"*Summary:* {email['summary']}"
                    )
                    self.slack.send_message(slack_msg)

                if email['category'] == 'meeting':
                    self.calendar.create_event(email)
                    reply = self.model.generate_reply(email['body'])
                    if reply:
                        self.gmail.send_reply(email['sender'], f"Re: {email['subject']}", reply)
                        email['automated_reply'] = reply
                    else:
                        email['automated_reply'] = None

                elif email['category'] == 'information':
                    results = self.web_search.search(email['body'])
                    if results:
                        reply = "Hello,\n\nThanks for your question. Here are some search results I found:\n"
                        for res in results:
                            reply += f"- {res['title']}: {res['snippet']} ({res['link']})\n"
                        reply += "\nBest regards."
                        self.gmail.send_reply(email['sender'], f"Re: {email['subject']}", reply)
                        email['automated_reply'] = reply
                    else:
                        email['automated_reply'] = None
                else:
                    email['automated_reply'] = None

                self.database.save_email(email)

            except Exception as e:
                logger.error(f"Error processing email {email['id']}: {str(e)}")

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

        # Simulate fetching emails
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

        # Display processed results
        display_results(emails)

        # Cleanup
        processor.cleanup()

    except Exception as e:
        logger.error(f"Application error: {str(e)}")
    finally:
        logger.info("Script execution completed")
