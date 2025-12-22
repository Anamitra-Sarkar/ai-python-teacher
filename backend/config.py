import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Get Gemini API key safely
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Optional safety check
if GEMINI_API_KEY is None:
    raise ValueError("GEMINI_API_KEY not found. Please set it in the .env file.")
