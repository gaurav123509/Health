from flask import Blueprint, request

from utils.emergency_detector import detect_emergency_signals


emergency_bp = Blueprint("emergency", __name__, url_prefix="/api/emergency-check")


@emergency_bp.post("")
def emergency_check() -> tuple[dict[str, str], int] | dict[str, object]:
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()

    if not message:
        return {"error": "Message is required."}, 400

    return detect_emergency_signals(message)
