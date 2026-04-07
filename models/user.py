from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class User:
    user_id: str
    name: str = "Guest"
    age: int | None = None
    medical_conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
