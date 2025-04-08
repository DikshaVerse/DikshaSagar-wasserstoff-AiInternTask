import sqlite3
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class EmailDatabase:
    def __init__(self, db_path: str = "emails.db"):
        """Initialize database with proper schema"""
        self.conn = sqlite3.connect(db_path)
        self._init_schema()
        
    def _init_schema(self):
        """Create tables with correct schema"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                message_id TEXT PRIMARY KEY,
                thread_id TEXT,
                sender TEXT,
                recipient TEXT,
                subject TEXT,
                body TEXT,
                sentiment TEXT,
                category TEXT,
                urgency INTEGER,
                summary TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
        logger.info("Database schema initialized")

    def save_email(self, email_data: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
        """Save processed email to database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO emails (
                    message_id, thread_id, sender, recipient,
                    subject, body, sentiment, category,
                    urgency, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                email_data.get('message_id', ''),
                email_data.get('thread_id', ''),
                email_data.get('sender', ''),
                email_data.get('recipient', ''),
                email_data.get('subject', 'No Subject'),
                email_data.get('body', ''),
                analysis.get('sentiment', 'neutral'),
                analysis.get('category', 'general'),
                int(analysis.get('urgency', 0)),
                analysis.get('summary', '')
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Database save failed: {str(e)}")
            return False

    def close(self):
        """Clean up resources"""
        self.conn.close()