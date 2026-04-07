from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class ChatHistory:
    session_id: str
    role: str
    message: str
    created_at: str | None = None
    id: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
