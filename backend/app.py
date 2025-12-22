import os
import re
import json
import time
import uuid
import logging
from typing import Any, Dict, Optional, Tuple

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv


# -----------------------------
# Config / Logging
# -----------------------------
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
	level=LOG_LEVEL,
	format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ai-python-teacher")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com").strip()
REQUEST_TIMEOUT_S = float(os.getenv("REQUEST_TIMEOUT_S", "20"))

CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "*").strip()
CORS_ORIGINS = "*" if CORS_ORIGINS_RAW == "*" else [o.strip() for o in CORS_ORIGINS_RAW.split(",") if o.strip()]

RETRY_DELAYS_S = [1, 2, 4, 8, 16]


# -----------------------------
# App
# -----------------------------
app = Flask(__name__)
CORS(
	app,
	resources={r"/ask-ai": {"origins": CORS_ORIGINS}},
	supports_credentials=False,
)


@app.get("/health")
def health():
	return jsonify({"status": "ok"}), 200


def _json_error(status: int, message: str, request_id: str, details: Optional[Dict[str, Any]] = None):
	payload = {"error": message, "request_id": request_id}
	if details:
		payload["details"] = details
	return jsonify(payload), status


def _build_tutor_prompt(topic: str, code: str, question: str, level: str) -> str:
	level_norm = (level or "beginner").strip().lower()
	if level_norm not in {"beginner", "intermediate", "advanced"}:
		level_norm = "beginner"

	# Strong, explicit constraints: tutor-only, no full solutions, explain "why", guide with questions.
	return f"""You are an AI Python Tutor embedded in a learning app.

STRICT TUTOR MODE (must follow):
- Do NOT provide a complete, ready-to-run corrected program.
- Do NOT output large code blocks. If you must show code, keep it to <= 5 lines and only as illustrative snippets.
- Prefer: hints, analogies, line-by-line explanations, and guided questions.
- When there is an error/bug, explain the *why* (root cause) before suggesting fixes.
- If the student asks for the answer, refuse politely and provide scaffolding instead.
- If the student code is unsafe or irrelevant, explain what’s wrong and redirect.

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


_CODEBLOCK_RE = re.compile(r"```(?:[\w+-]+)?\n(.*?)```", re.DOTALL)


def _sanitize_tutor_output(text: str) -> str:
	"""
	Best-effort guardrail to prevent the backend from returning full solutions.
	This does not guarantee compliance, but reduces accidental large code dumps.
	"""
	if not text:
		return text

	def _replace_block(match: re.Match) -> str:
		body = match.group(1) or ""
		lines = body.splitlines()
		if len(lines) > 8:
			return (
				"[Code omitted to keep this tutor-focused. "
				"Ask for a hint about a specific line or error message, and I’ll guide you.]"
			)
		return match.group(0)

	text2 = _CODEBLOCK_RE.sub(_replace_block, text)

	# Heuristic: if it looks like a full solution dump without fences, clamp length.
	# (e.g., many lines starting with common Python structure)
	suspicious_line_starts = ("import ", "from ", "def ", "class ", "if __name__")
	lines = text2.splitlines()
	suspicious = sum(1 for ln in lines if ln.lstrip().startswith(suspicious_line_starts))
	if suspicious >= 12:
		text2 = "\n".join(lines[:120]) + "\n\n[Output truncated to avoid full-solution code.]"

	return text2


def _gemini_generate(prompt: str, request_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
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

	for attempt, delay_s in enumerate([0] + RETRY_DELAYS_S, start=1):
		if delay_s:
			time.sleep(delay_s)

		try:
			t0 = time.time()
			resp = requests.post(
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


@app.post("/ask-ai")
def ask_ai():
	request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())

	try:
		if not request.is_json:
			return _json_error(
				400,
				"Content-Type must be application/json.",
				request_id,
			)

		body = request.get_json(silent=True) or {}
		topic = str(body.get("topic") or "").strip()
		code = str(body.get("code") or "")
		question = str(body.get("question") or "").strip()
		level = str(body.get("level") or "beginner").strip()

		if not question:
			return _json_error(400, "Field 'question' is required.", request_id)
		if len(code) > 80_000:
			return _json_error(413, "Field 'code' is too large.", request_id)

		logger.info(
			"ask_ai request_id=%s topic=%s level=%s question_len=%s code_len=%s",
			request_id,
			topic[:80],
			level,
			len(question),
			len(code),
		)

		prompt = _build_tutor_prompt(topic=topic, code=code, question=question, level=level)
		raw_text, err = _gemini_generate(prompt, request_id=request_id)

		if err or not raw_text:
			return _json_error(
				502,
				"AI provider error. Please try again.",
				request_id,
				details=err,
			)

		answer = _sanitize_tutor_output(raw_text)
		return jsonify({"answer": answer, "request_id": request_id}), 200

	except Exception as exc:
		logger.exception("ask_ai_unhandled request_id=%s err=%s", request_id, exc)
		return _json_error(500, "Internal server error.", request_id)


if __name__ == "__main__":
	# Dev-friendly defaults; use a real WSGI server (gunicorn/uvicorn) in production.
	host = os.getenv("HOST", "0.0.0.0")
	port = int(os.getenv("PORT", "5000"))
	debug = os.getenv("FLASK_DEBUG", "0") == "1"
	app.run(host=host, port=port, debug=debug)