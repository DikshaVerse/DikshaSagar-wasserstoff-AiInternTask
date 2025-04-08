from transformers import pipeline
import torch
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class HuggingFaceService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing HuggingFace models on {self.device}")
        
        # Initialize all models
        self.sentiment_analyzer = pipeline(
            "text-classification",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=self.device
        )
        
        self.summarizer = pipeline(
            "summarization",
            model="facebook/bart-large-cnn",
            device=self.device
        )

    def analyze_sentiment(self, text: str) -> str:
        """Analyze text sentiment"""
        try:
            result = self.sentiment_analyzer(text[:1000])[0]  # Truncate long emails
            return result['label'].lower()
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {str(e)}")
            return "neutral"

    def classify_category(self, text: str) -> str:
        """Categorize email content"""
        try:
            # Simple keyword-based categorization - improve as needed
            text_lower = text.lower()
            if any(word in text_lower for word in ["meeting", "schedule", "calendar"]):
                return "scheduling"
            elif any(word in text_lower for word in ["invoice", "payment", "billing"]):
                return "finance"
            return "general"
        except Exception as e:
            logger.error(f"Category classification failed: {str(e)}")
            return "general"

    def detect_urgency(self, text: str) -> int:
        """Detect email urgency level (0-2)"""
        try:
            text_lower = text.lower()
            if any(word in text_lower for word in ["urgent", "asap", "immediately"]):
                return 2
            elif any(word in text_lower for word in ["important", "priority"]):
                return 1
            return 0
        except Exception as e:
            logger.error(f"Urgency detection failed: {str(e)}")
            return 0

    def generate_summary(self, text: str) -> str:
        """Generate concise summary of email"""
        try:
            return self.summarizer(
                text[:1024],  # Truncate to model's max length
                max_length=130,
                min_length=30,
                do_sample=False
            )[0]['summary_text']
        except Exception as e:
            logger.error(f"Summarization failed: {str(e)}")
            return text[:150] + "..." if len(text) > 150 else text