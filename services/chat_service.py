import os
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Global session for shared connection pool
_chat_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20)
_chat_session.mount("https://", adapter)

def get_chat_response(user_message, conversation_history, user_context=""):
    """
    Chat response using Groq via a persistent HTTP session.
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    if not GROQ_API_KEY:
        return "⚠️ AI service unavailable. API Key missing."

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = f"""
You are a helpful AI assistant for a task management system.

Context about user:
{user_context}

Help users with:
- Task management
- Time management
- Delay analysis
- Work-related guidance

Be concise, helpful, and professional.
""".strip()

    # Prepare messages
    messages = [{"role": "system", "content": system_prompt}] + conversation_history + [{"role": "user", "content": user_message}]

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "temperature": 0.7
    }

    try:
        response = _chat_session.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[Groq HTTP Error] {e}")
        return "⚠️ AI service unavailable. Please try again later."
