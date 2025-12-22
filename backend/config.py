import os
import logging
from typing import List, Union

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ai-python-teacher")

# Gemini API configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com").strip()

# Request configuration
REQUEST_TIMEOUT_S = float(os.getenv("REQUEST_TIMEOUT_S", "20"))
RETRY_DELAYS_S: List[int] = [1, 2, 4, 8, 16]

# CORS configuration
CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "*").strip()
CORS_ORIGINS: Union[str, List[str]] = (
    "*" if CORS_ORIGINS_RAW == "*"
    else [o.strip() for o in CORS_ORIGINS_RAW.split(",") if o.strip()]
)
