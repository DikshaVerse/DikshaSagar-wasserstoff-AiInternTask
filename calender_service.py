import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import logging

# If modifying these scopes, delete the token.json file.
SCOPES = ['https://www.googleapis.com/auth/calendar']

class CalendarService:
    def __init__(self, token_path='token.json', credentials_path='credentials.json'):
        self.token_path = token_path
        self.credentials_path = credentials_path
        self.service = self._authenticate()
        
    def _authenticate(self):
        """Authenticate with Google Calendar API"""
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        return build('calendar', 'v3', credentials=creds)
    
    def create_event(self, summary, start_time, end_time, timezone='UTC', attendees=None, location=None, description=None):
        """Create a calendar event"""
        event = {
            'summary': summary,
            'location': location,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': timezone,
            },
            'attendees': [{'email': email} for email in attendees] if attendees else [],
        }
        
        try:
            event = self.service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            logging.info(f"Event created: {event.get('htmlLink')}")
            return event
        except Exception as e:
            logging.error(f"Error creating event: {e}")
            return None