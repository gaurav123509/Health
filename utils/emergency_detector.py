EMERGENCY_KEYWORDS = {
    "chest pain",
    "shortness of breath",
    "can't breathe",
    "cannot breathe",
    "severe bleeding",
    "unconscious",
    "not breathing",
    "stroke",
    "seizure",
    "heart attack",
}


def detect_emergency_signals(message: str) -> dict[str, object]:
    normalized = " ".join(message.lower().split())
    triggers = sorted(keyword for keyword in EMERGENCY_KEYWORDS if keyword in normalized)
    is_emergency = bool(triggers)

    if is_emergency:
        recommended_action = (
            "This may be an emergency. Seek urgent in-person help now and call local "
            "emergency services if the person is in immediate danger."
        )
    else:
        recommended_action = (
            "No emergency phrases were detected, but monitor symptoms and contact a medical "
            "professional if the condition worsens or you feel unsure."
        )

    return {
        "is_emergency": is_emergency,
        "triggers": triggers,
        "recommended_action": recommended_action,
        "disclaimer": "Emergency screening here is keyword-based and should not replace clinical judgment.",
    }
