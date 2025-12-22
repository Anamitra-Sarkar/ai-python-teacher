"""
Gemini AI API module for the AI Python Teacher backend.

This module handles all interactions with the Google Gemini API,
including request building, error handling, and response parsing.
"""
import re
import time
from typing import Any, Dict, Optional, Tuple

import requests

from config import (
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
    REQUEST_TIMEOUT_S,
    RETRY_DELAYS_S,
    logger,
)

# Pre-compiled regex for code block detection
_CODEBLOCK_RE = re.compile(r"```(?:[\w+-]+)?\n(.*?)```", re.DOTALL)

# HTTP session for connection pooling
_http_session: Optional[requests.Session] = None


def _get_http_session() -> requests.Session:
    """Get or create a reusable HTTP session for connection pooling."""
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
    return _http_session


def build_tutor_prompt(topic: str, code: str, question: str, level: str) -> str:
    """
    Build a structured prompt for the AI tutor.
    
    Args:
        topic: The Python topic being studied
        code: The student's Python code
        question: The student's question
        level: The student's skill level (beginner/intermediate/advanced)
    
    Returns:
        A formatted prompt string for the Gemini API
    """
    level_norm = (level or "beginner").strip().lower()
    if level_norm not in {"beginner", "intermediate", "advanced"}:
        level_norm = "beginner"

    return f"""You are an AI Python Tutor embedded in a learning app.

STRICT TUTOR MODE (must follow):
- Do NOT provide a complete, ready-to-run corrected program.
- Do NOT output large code blocks. If you must show code, keep it to <= 5 lines and only as illustrative snippets.
- Prefer: hints, analogies, line-by-line explanations, and guided questions.
- When there is an error/bug, explain the *why* (root cause) before suggesting fixes.
- If the student asks for the answer, refuse politely and provide scaffolding instead.
- If the student code is unsafe or irrelevant, explain what's wrong and redirect.

Student context:
- Topic: {topic or "(unspecified)"}
- Level: {level_norm}

Student code:
```python
{code or ""}
```

Student question:
{question}

Required response format (use these headings):
1) Diagnosis (1-3 sentences)
2) Why it happens (conceptual explanation)
3) Hints (3-7 bullets, ordered from easiest to hardest)
4) Check yourself (2-4 quick questions the student should answer)
5) Next small step (one actionable step the student can do now)
"""


def sanitize_tutor_output(text: str) -> str:
    """
    Best-effort guardrail to prevent the backend from returning full solutions.
    This does not guarantee compliance, but reduces accidental large code dumps.
    
    Args:
        text: The raw response text from the AI
    
    Returns:
        Sanitized text with large code blocks removed or truncated
    """
    if not text:
        return text

    def _replace_block(match: re.Match) -> str:
        body = match.group(1) or ""
        body_lines = body.splitlines()
        if len(body_lines) > 8:
            return (
                "[Code omitted to keep this tutor-focused. "
                "Ask for a hint about a specific line or error message, and I'll guide you.]"
            )
        return match.group(0)

    text2 = _CODEBLOCK_RE.sub(_replace_block, text)

    # Heuristic: if it looks like a full solution dump without fences, clamp length.
    suspicious_line_starts = ("import ", "from ", "def ", "class ", "if __name__")
    lines = text2.splitlines()
    suspicious = sum(1 for ln in lines if ln.lstrip().startswith(suspicious_line_starts))
    if suspicious >= 12:
        text2 = "\n".join(lines[:120]) + "\n\n[Output truncated to avoid full-solution code.]"

    return text2


def generate_response(prompt: str, request_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Generate a response from the Gemini API with retry logic.
    
    Args:
        prompt: The formatted prompt to send to Gemini
        request_id: A unique identifier for logging/tracking
    
    Returns:
        A tuple of (response_text, error_dict). On success, error_dict is None.
        On failure, response_text is None and error_dict contains error details.
    """
    if not GEMINI_API_KEY:
        return None, {"message": "Missing GEMINI_API_KEY in environment."}

    url = f"{GEMINI_BASE_URL}/v1beta/models/{GEMINI_MODEL}:generateContent"
    params = {"key": GEMINI_API_KEY}

    payload: Dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "topP": 0.9,
            "maxOutputTokens": 900,
        },
    }

    last_err: Optional[Dict[str, Any]] = None
    session = _get_http_session()

    for attempt, delay_s in enumerate([0] + RETRY_DELAYS_S, start=1):
        if delay_s:
            time.sleep(delay_s)

        try:
            t0 = time.time()
            resp = session.post(
                url,
                params=params,
                json=payload,
                timeout=REQUEST_TIMEOUT_S,
            )
            dt_ms = int((time.time() - t0) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                # Typical structure: candidates[0].content.parts[0].text
                try:
                    cand0 = (data.get("candidates") or [])[0]
                    content = (cand0.get("content") or {})
                    parts = content.get("parts") or []
                    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
                    if not text:
                        last_err = {"message": "Empty response from Gemini.", "raw": data}
                        logger.error("gemini_empty request_id=%s dt_ms=%s", request_id, dt_ms)
                    else:
                        logger.info("gemini_ok request_id=%s dt_ms=%s", request_id, dt_ms)
                        return text, None
                except Exception as parse_exc:
                    last_err = {"message": "Failed to parse Gemini response.", "exception": str(parse_exc)}
                    logger.exception("gemini_parse_error request_id=%s dt_ms=%s", request_id, dt_ms)
            else:
                # Retry on rate limits / transient server errors
                should_retry = resp.status_code in (429, 500, 502, 503, 504)
                try:
                    body = resp.json()
                except Exception:
                    body = {"text": resp.text[:2000]}

                last_err = {
                    "message": "Gemini HTTP error",
                    "status": resp.status_code,
                    "body": body,
                }
                logger.warning(
                    "gemini_http_error request_id=%s attempt=%s status=%s retry=%s",
                    request_id,
                    attempt,
                    resp.status_code,
                    should_retry,
                )
                if not should_retry:
                    break

        except requests.Timeout:
            last_err = {"message": "Gemini request timed out."}
            logger.warning("gemini_timeout request_id=%s attempt=%s", request_id, attempt)
        except requests.RequestException as req_exc:
            last_err = {"message": "Gemini request failed.", "exception": str(req_exc)}
            logger.warning("gemini_request_exception request_id=%s attempt=%s err=%s", request_id, attempt, req_exc)

    return None, last_err or {"message": "Unknown Gemini failure."}
