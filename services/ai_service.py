from __future__ import annotations

from database.db import save_chat_message
from services.doctor_service import suggest_doctor
from services.symptom_service import analyze_symptoms
from utils.bmi_calculator import calculate_bmi, extract_bmi_inputs
from utils.emergency_detector import detect_emergency_signals
from utils.health_tips import get_tip


DISCLAIMER = (
    "I can share general wellness information, but I cannot diagnose conditions or "
    "replace advice from a licensed medical professional."
)


def _format_bmi_response(message: str) -> str:
    weight_kg, height_cm = extract_bmi_inputs(message)

    if weight_kg is None or height_cm is None:
        return (
            "I can estimate BMI if you share both values in one message, for example: "
            "'My weight is 68 kg and my height is 170 cm.'"
        )

    result = calculate_bmi(weight_kg, height_cm)
    return (
        f"Your estimated BMI is {result['bmi']:.1f}, which falls in the "
        f"'{result['category']}' range. {result['advice']}"
    )


def generate_response(message: str, session_id: str = "guest") -> dict[str, object]:
    normalized = message.lower()
    save_chat_message(session_id, "user", message)

    emergency = detect_emergency_signals(message)

    if emergency["is_emergency"]:
        response = (
            "Your message includes warning phrases that may need urgent attention. "
            f"Detected triggers: {', '.join(emergency['triggers'])}. "
            f"{emergency['recommended_action']}"
        )
        suggestions = [
            "Call local emergency services",
            "Go to the nearest emergency department",
            "Ask a nearby person for immediate help",
        ]
    elif any(keyword in normalized for keyword in ["bmi", "body mass index", "weight", "height"]):
        response = _format_bmi_response(message)
        suggestions = [
            "Share weight in kg",
            "Share height in cm",
            "Ask for a healthy routine tip",
        ]
    elif any(keyword in normalized for keyword in ["tip", "wellness", "sleep", "hydrate", "hydration"]):
        response = f"Here is one practical health tip for today: {get_tip()}"
        suggestions = [
            "Ask about symptoms",
            "Check BMI",
            "Create a reminder",
        ]
    else:
        symptom_summary = analyze_symptoms(message)
        doctor = suggest_doctor(symptom_summary["category"])

        if symptom_summary["matched_symptoms"]:
            matched = ", ".join(symptom_summary["matched_symptoms"])
            category_label = symptom_summary["category"].replace("_", " ")
            response = (
                f"I noticed these symptoms in your message: {matched}. "
                f"They look most related to {category_label} concerns, and the urgency sounds "
                f"{symptom_summary['severity']}. "
                f"General self-care: {symptom_summary['self_care']}. "
                f"If symptoms continue, worsen, or feel unusual, consider seeing a "
                f"{doctor['specialist']}. {DISCLAIMER}"
            )
            suggestions = [
                f"Suggested clinician: {doctor['specialist']}",
                "Ask for a wellness tip",
                "Run an emergency keyword check",
            ]
        else:
            response = (
                "I can help with general symptom check-ins, BMI estimates, wellness tips, "
                "reminders, and emergency keyword screening. Tell me what symptoms you have "
                f"or ask a specific health question. {DISCLAIMER}"
            )
            suggestions = [
                "Describe your symptoms",
                "Ask for BMI help",
                "Get a health tip",
            ]

    save_chat_message(session_id, "assistant", response)

    return {
        "response": response,
        "emergency": emergency["is_emergency"],
        "triggers": emergency["triggers"],
        "suggestions": suggestions,
        "disclaimer": DISCLAIMER,
    }
