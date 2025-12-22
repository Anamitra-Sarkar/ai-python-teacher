import os

# Note: load_dotenv() is called in app.py, so no need to duplicate here
# Get Gemini API key safely
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Optional safety check
if GEMINI_API_KEY is None:
    raise ValueError("GEMINI_API_KEY not found. Please set it in the .env file.")
