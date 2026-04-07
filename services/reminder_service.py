from __future__ import annotations

from datetime import datetime

from database.db import add_reminder, fetch_reminders, update_reminder_status


def create_reminder(payload: dict[str, object]) -> dict[str, object]:
    title = str(payload.get("title", "")).strip()
    reminder_time = str(payload.get("reminder_time", "")).strip()
    notes = str(payload.get("notes", "")).strip()

    if not title:
        raise ValueError("Reminder title is required.")

    if not reminder_time:
        raise ValueError("Reminder time is required.")

    try:
        parsed_time = datetime.fromisoformat(reminder_time)
    except ValueError as exc:
        raise ValueError(
            "Reminder time must use ISO format, for example 2026-04-08T09:30."
        ) from exc

    reminder_id = add_reminder(
        title=title,
        reminder_time=parsed_time.isoformat(timespec="minutes"),
        notes=notes,
    )

    return {
        "id": reminder_id,
        "title": title,
        "reminder_time": parsed_time.isoformat(timespec="minutes"),
        "notes": notes,
        "is_completed": False,
    }


def list_reminders() -> list[dict[str, object]]:
    return fetch_reminders()


def complete_reminder(reminder_id: int) -> dict[str, object] | None:
    return update_reminder_status(reminder_id, True)
