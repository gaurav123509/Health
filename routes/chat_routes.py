from flask import Blueprint, jsonify, request

from database.db import get_chat_history
from services.ai_service import generate_response


chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@chat_bp.post("")
def chat() -> tuple[dict[str, str], int] | dict[str, object]:
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    session_id = (payload.get("session_id") or "guest").strip() or "guest"

    if not message:
        return {"error": "Message is required."}, 400

    return generate_response(message=message, session_id=session_id)


@chat_bp.get("/history")
def history() -> dict[str, object]:
    session_id = (request.args.get("session_id") or "guest").strip() or "guest"
    return {"session_id": session_id, "messages": get_chat_history(session_id)}
