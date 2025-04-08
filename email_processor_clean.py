# email_processor_clean.py
import os
import torch
from transformers import pipeline
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HuggingFaceService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing models on {self.device}")
        
        try:
            # Completely clean initialization
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
            logger.info("✅ Models initialized successfully")
        except Exception as e:
            logger.error(f"❌ Model initialization failed: {str(e)}")
            raise

if __name__ == "__main__":
    try:
        hf = HuggingFaceService()
        print("Successfully initialized models!")
    except Exception as e:
        logger.error(f"Application failed: {str(e)}")