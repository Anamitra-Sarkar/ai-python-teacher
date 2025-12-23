"""
Flask backend for the AI Python Teacher application.

This module provides the REST API endpoints for the tutoring service.
"""
import os
import uuid
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

from config import CORS_ORIGINS, logger
from gemini_ai import build_tutor_prompt, generate_response, sanitize_tutor_output


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
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


def _json_error(status: int, message: str, request_id: str, details: Optional[Dict[str, Any]] = None):
    """Return a JSON error response with standard format."""
    payload = {"error": message, "request_id": request_id}
    if details:
        payload["details"] = details
    return jsonify(payload), status


@app.post("/ask-ai")
def ask_ai():
    """
    Main endpoint for AI tutoring requests.
    
    Expects JSON body with:
        - topic: Optional topic being studied
        - code: Optional Python code from student
        - question: Required student question
        - level: Optional skill level (beginner/intermediate/advanced)
    
    Returns JSON with:
        - answer: The tutor's response
        - request_id: Unique identifier for the request
    """
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

        prompt = build_tutor_prompt(topic=topic, code=code, question=question, level=level)
        raw_text, err = generate_response(prompt, request_id=request_id)

        if err or not raw_text:
            return _json_error(
                502,
                "AI provider error. Please try again.",
                request_id,
                details=err,
            )

        answer = sanitize_tutor_output(raw_text)
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
