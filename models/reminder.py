from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class Reminder:
    title: str
    reminder_time: str
    notes: str = ""
    is_completed: bool = False
    id: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
