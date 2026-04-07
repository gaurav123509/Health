from flask import Blueprint, request

from services.reminder_service import complete_reminder, create_reminder, list_reminders


reminder_bp = Blueprint("reminders", __name__, url_prefix="/api/reminders")


@reminder_bp.get("")
def reminders() -> dict[str, list[dict[str, object]]]:
    return {"reminders": list_reminders()}


@reminder_bp.post("")
def add_reminder() -> tuple[dict[str, str], int] | tuple[dict[str, object], int]:
    payload = request.get_json(silent=True) or {}

    try:
        reminder = create_reminder(payload)
    except ValueError as exc:
        return {"error": str(exc)}, 400

    return {"message": "Reminder created successfully.", "reminder": reminder}, 201


@reminder_bp.post("/<int:reminder_id>/complete")
def mark_complete(reminder_id: int) -> tuple[dict[str, str], int] | dict[str, object]:
    reminder = complete_reminder(reminder_id)

    if reminder is None:
        return {"error": "Reminder not found."}, 404

    return {"message": "Reminder marked as completed.", "reminder": reminder}
