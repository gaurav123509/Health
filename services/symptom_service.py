from __future__ import annotations

from collections import Counter


SYMPTOM_GROUPS = {
    "respiratory": {
        "cough",
        "sore throat",
        "fever",
        "runny nose",
        "congestion",
        "shortness of breath",
    },
    "digestive": {
        "stomach pain",
        "nausea",
        "vomiting",
        "diarrhea",
        "constipation",
        "bloating",
    },
    "musculoskeletal": {
        "back pain",
        "joint pain",
        "muscle pain",
        "stiffness",
        "sprain",
    },
    "neurological": {
        "headache",
        "migraine",
        "dizziness",
        "numbness",
        "fainting",
    },
    "general": {
        "fatigue",
        "weakness",
        "body ache",
        "stress",
        "anxiety",
        "tired",
    },
}

SELF_CARE_GUIDANCE = {
    "respiratory": "Rest well, stay hydrated, and monitor fever or breathing changes closely.",
    "digestive": "Use bland foods, sip fluids slowly, and watch for dehydration or persistent pain.",
    "musculoskeletal": "Rest the area, avoid strain, and consider gentle mobility if it is comfortable.",
    "neurological": "Rest in a quiet space and watch for worsening headache, confusion, or repeated dizziness.",
    "general": "Focus on hydration, sleep, balanced meals, and reducing physical or emotional strain.",
}

HIGH_URGENCY_KEYWORDS = {
    "severe",
    "worsening",
    "cannot breathe",
    "can't breathe",
    "fainted",
    "unconscious",
}

MEDIUM_URGENCY_KEYWORDS = {
    "persistent",
    "since yesterday",
    "for two days",
    "painful",
    "repeated",
}


def analyze_symptoms(message: str) -> dict[str, object]:
    normalized = " ".join(message.lower().split())
    matches: list[str] = []
    category_counts: Counter[str] = Counter()

    for category, symptoms in SYMPTOM_GROUPS.items():
        for symptom in symptoms:
            if symptom in normalized:
                matches.append(symptom)
                category_counts[category] += 1

    if any(keyword in normalized for keyword in HIGH_URGENCY_KEYWORDS):
        severity = "high"
    elif any(keyword in normalized for keyword in MEDIUM_URGENCY_KEYWORDS):
        severity = "medium"
    else:
        severity = "low"

    category = category_counts.most_common(1)[0][0] if category_counts else "general"

    return {
        "category": category,
        "matched_symptoms": sorted(set(matches)),
        "severity": severity,
        "self_care": SELF_CARE_GUIDANCE[category],
    }
