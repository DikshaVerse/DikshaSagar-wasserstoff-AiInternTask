from transformers import pipeline

# No API keys needed
analyzer = pipeline("text-classification", 
                   model="distilbert-base-uncased")

def analyze_email(email):
    results = analyzer(f"{email['subject']}: {email['body'][:512]}")
    return str(results[0])  # Return top prediction