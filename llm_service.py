# Updated llm_service.py with local fallback
from transformers import pipeline
import warnings
warnings.filterwarnings("ignore")

# Local LLM fallback
local_llm = pipeline("text-generation", model="gpt2")

def analyze_email(email):
    try:
        # Try OpenAI first if you fix billing
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[...],
            temperature=0.3
        )
        return response.choices[0].message.content
    except:
        # Fallback to local model
        result = local_llm(
            f"Analyze this email: {email['subject']}\n{email['body'][:500]}",
            max_length=100,
            do_sample=False
        )
        return result[0]['generated_text']