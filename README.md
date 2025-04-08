# AI-Powered Email Assistant

## Overview

This project is an AI-powered email assistant designed to automate the reading, understanding, classification, and replying of emails. It integrates with Gmail and Google Calendar APIs and uses Hugging Face LLMs to perform NLP tasks such as summarization, sentiment analysis, urgency detection, classification, and auto-reply generation. It is built in a modular way and designed for extensibility, including future Slack integration.

---

## ✨ Features

- Automatically reads and processes emails.
- Classifies emails by sentiment, urgency, and category.
- Schedules calendar events for meeting-related emails.
- Searches web for informational emails and responds.
- Sends AI-generated replies.
- Stores processed email metadata in SQLite.
- Built with transformers pipelines from HuggingFace.

---

## 🔧 Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/ai-email-assistant.git
cd ai-email-assistant
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up API Credentials

- **Gmail & Calendar**
  - Go to [Google Cloud Console](https://console.cloud.google.com/).
  - Create a project and enable Gmail API and Calendar API.
  - Create OAuth2 credentials and download the `credentials.json`.
  - Place it in the root of your project.

- **Environment Variables**

Set the following environment variables (e.g., via `.env` or your shell):

```
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CX=your_custom_search_cx
```

### 4. Authenticate

The script will automatically guide you through the authentication process during the first run and store `token.pickle` and `calendar_token.json`.

---

## ▶️ Running the Assistant

To process emails and send automated replies:

```bash
python main.py
```

---

## 🧠 Architecture

```
Gmail Inbox
    |
    v
[ Email Fetcher ]
    |
    v
[ LLM Processor (HuggingFace Pipelines) ]
    |      |         |         |
    |      |         |         +--> Sentiment Analysis
    |      |         +--> Urgency Detection
    |      +--> Summarization
    +--> Classification
    |
    v
[ Action Router ]
    |
    +--> Calendar Event Creator (for meetings)
    +--> Web Search & Reply (for information)
    +--> Skip / Store (for others)
    |
    v
[ Gmail Reply Sender ]
    |
    v
[ SQLite Email Logger ]
```

---

## 📦 Project Structure

```
.
├── main.py
├── llm_service.py
├── huggingface_service.py
├── gmail_service.py
├── calendar_service.py
├── database.py
├── web_search_service.py
├── utils/
├── token.pickle
├── calendar_token.json
├── credentials.json
├── README.md
└── requirements.txt
```

---

## 💡 Example Usage

```
Subject: Request for Meeting

Summary: "Let's discuss project deliverables this week."

Category: meeting
Urgency: High
Sentiment: Neutral

→ Calendar Event Created
→ Reply Sent: "Sure, I'm available to discuss the project tomorrow. Let me know what time works!"
```

---

## 🧪 Testing

- Unit tests for individual modules are under `tests/`.
- Use `pytest` to run tests.

---

## 🧩 Future Work

- Slack integration
- Email thread memory
- UI dashboard for interactions

---

## 📬 Contact

For questions, reach out at [dikshasagar987@gmail.com]