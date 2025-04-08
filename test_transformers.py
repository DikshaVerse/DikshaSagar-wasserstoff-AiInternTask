# test_transformers.py
from transformers import pipeline
import torch
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pipeline():
    try:
        logger.info("Testing sentiment analysis pipeline...")
        pipe = pipeline("text-classification", device="cuda" if torch.cuda.is_available() else "cpu")
        logger.info("✅ Pipeline created successfully!")
        return True
    except Exception as e:
        logger.error(f"❌ Failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_pipeline()