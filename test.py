from transformers import pipeline
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pipeline():
    try:
        logger.info("Trying with safe versions...")
        classifier = pipeline(
            "text-classification",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device="cpu"  # Remove if you have GPU
        )
        logger.info("✅ Success! Pipeline created")
        return True
    except Exception as e:
        logger.error(f"❌ Failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_pipeline()