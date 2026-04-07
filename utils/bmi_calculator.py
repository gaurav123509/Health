from __future__ import annotations

import re


def extract_bmi_inputs(message: str) -> tuple[float | None, float | None]:
    normalized = message.lower()
    weight_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)", normalized)
    height_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:cm|centimeters?)", normalized)

    weight_kg = float(weight_match.group(1)) if weight_match else None
    height_cm = float(height_match.group(1)) if height_match else None
    return weight_kg, height_cm


def calculate_bmi(weight_kg: float, height_cm: float) -> dict[str, object]:
    if height_cm <= 0:
        raise ValueError("Height must be greater than zero.")

    height_m = height_cm / 100
    bmi = weight_kg / (height_m * height_m)

    if bmi < 18.5:
        category = "underweight"
        advice = "A clinician or dietitian can help you assess nutrition and energy needs."
    elif bmi < 25:
        category = "healthy weight"
        advice = "Keep supporting your routine with balanced meals, sleep, hydration, and movement."
    elif bmi < 30:
        category = "overweight"
        advice = "Steady lifestyle changes can help, and a clinician can guide you based on overall health."
    else:
        category = "obesity"
        advice = "Consider speaking with a clinician for a fuller assessment and a personalized care plan."

    return {
        "bmi": bmi,
        "category": category,
        "advice": advice,
    }
