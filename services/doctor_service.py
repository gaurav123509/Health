DOCTOR_BY_CATEGORY = {
    "respiratory": {
        "specialist": "general physician or pulmonologist",
        "reason": "useful for ongoing cough, fever, wheezing, or breathing concerns",
    },
    "digestive": {
        "specialist": "general physician or gastroenterologist",
        "reason": "helpful for persistent stomach pain, vomiting, or bowel changes",
    },
    "musculoskeletal": {
        "specialist": "orthopedic specialist or physiotherapist",
        "reason": "appropriate for pain after strain, stiffness, or mobility trouble",
    },
    "neurological": {
        "specialist": "general physician or neurologist",
        "reason": "important when headache, dizziness, or numbness keeps returning",
    },
    "general": {
        "specialist": "general physician",
        "reason": "a good first step for broad symptoms or unclear health concerns",
    },
}


def suggest_doctor(category: str) -> dict[str, str]:
    return DOCTOR_BY_CATEGORY.get(category, DOCTOR_BY_CATEGORY["general"])
