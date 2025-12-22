import google.generativeai as genai
from config import GEMINI_API_KEY

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Load Gemini model
model = genai.GenerativeModel("gemini-pro")

# System prompt: controls AI behavior (AI Teacher)
SYSTEM_PROMPT = """
You are an AI Teaching Assistant inside a Python learning application.

Your role is to help students understand Python programming from absolute scratch.

Rules you must follow:
1. Explain concepts step by step using simple language.
2. Explain Python code line by line when code is provided.
3. Never assume prior programming knowledge.
4. Give hints first before providing full solutions.
5. Use small, real-life examples when possible.
6. Be calm, friendly, and supportive.
7. Do not answer questions outside Python learning.
8. Focus on understanding, not memorization.
"""

def ask_ai(topic, code, question, level="Beginner"):
    """
    Sends context-aware prompt to Gemini and returns the response.
    """

    user_prompt = f"""
Student Level: {level}
Current Topic: {topic}

Student Code:
{code}

Student Question:
{question}

Explain clearly and in a beginner-friendly way.
"""

    response = model.generate_content(
        SYSTEM_PROMPT + user_prompt
    )

    return response.text
