import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import Optional, Dict

class SlackMessenger:
    def __init__(self, token: Optional[str] = None):
        """
        Initialize with Slack bot token.
        If no token provided, tries to read from SLACK_TOKEN env var.
        """
        self.client = WebClient(token or os.getenv("SLACK_TOKEN"))
        self._validate_token()

    def _validate_token(self):
        """Verify token works"""
        try:
            self.client.auth_test()
        except SlackApiError as e:
            raise ValueError(f"Invalid Slack token: {e.response['error']}")

    def send_message(
        self,
        text: str,
        channel: str,
        attachments: Optional[List[Dict]] = None,
        thread_ts: Optional[str] = None
    ) -> bool:
        """
        Send message to Slack channel.
        
        Args:
            text: Main message text
            channel: Channel ID (e.g. "#general") or user ID
            attachments: Rich formatting (see Slack API docs)
            thread_ts: Timestamp to reply in thread
            
        Returns:
            bool: True if successful
        """
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=text,
                attachments=attachments,
                thread_ts=thread_ts,
                unfurl_links=True  # Auto-expand links
            )
            return response["ok"]
        except SlackApiError as e:
            print(f"⚠️ Slack error: {e.response['error']}")
            return False

    def format_email_alert(self, email: Dict) -> Dict:
        """Create Slack attachment for emails"""
        return {
            "color": "#FF0000" if email.get('urgency', 0) >= 2 else "#FFA500",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*New email from {email['sender']}*"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Subject:*\n{email['subject']}"},
                        {"type": "mrkdwn", "text": f"*Urgency:*\n{'❗' * email.get('urgency', 0)}"}
                    ]
                }
            ]
        }

# Usage Example:
if __name__ == "__main__":
    # Initialize with token from .env
    messenger = SlackMessenger()
    
    # Send test message
    messenger.send_message(
        text="Email assistant is online!",
        channel="#email-alerts"
    )