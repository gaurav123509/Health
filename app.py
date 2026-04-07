from __future__ import annotations

import base64
import json
import mimetypes
import os
import random
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from groq import Groq
except ImportError:
    Groq = None

from database.db import (
    add_reminder,
    create_user,
    delete_reminder,
    fetch_reminders,
    get_chat_history,
    get_user_auth_record,
    get_user_by_email,
    get_user_by_id,
    get_user_dashboard_stats,
    init_db,
    save_chat_message,
    update_user_profile,
    update_reminder_status,
)


load_dotenv(Path(__file__).resolve().with_name(".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct").strip()
_groq_client = None
MAX_MEDICINE_IMAGE_BYTES = 3 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


DISCLAIMER = {
    "en": (
        "HealthCare AI Chatbot gives educational guidance only and is not a replacement for "
        "a licensed doctor, emergency service, or hospital evaluation."
    ),
    "hi": (
        "HealthCare AI Chatbot केवल सामान्य जानकारी देता है। यह डॉक्टर, इमरजेंसी सेवा या "
        "अस्पताल की जांच का विकल्प नहीं है।"
    ),
}

UI_TEXT = {
    "message_required": {
        "en": "Please type a health question or symptom first.",
        "hi": "कृपया पहले अपना स्वास्थ्य प्रश्न या लक्षण लिखें।",
    },
    "invalid_bmi": {
        "en": "Please enter valid height and weight values.",
        "hi": "कृपया सही height और weight दर्ज करें।",
    },
    "reminder_saved": {
        "en": "Medicine reminder saved successfully.",
        "hi": "दवा रिमाइंडर सफलतापूर्वक सेव हो गया।",
    },
    "reminder_completed": {
        "en": "Reminder marked as completed.",
        "hi": "रिमाइंडर को पूरा चिह्नित कर दिया गया है।",
    },
    "reminder_deleted": {
        "en": "Reminder deleted.",
        "hi": "रिमाइंडर हटा दिया गया है।",
    },
    "reminder_missing": {
        "en": "Reminder not found.",
        "hi": "रिमाइंडर नहीं मिला।",
    },
    "reminder_name_required": {
        "en": "Medicine name is required.",
        "hi": "दवा का नाम आवश्यक है।",
    },
    "reminder_time_required": {
        "en": "Reminder time is required.",
        "hi": "रिमाइंडर का समय आवश्यक है।",
    },
    "reminder_time_invalid": {
        "en": "Use a valid date and time for the reminder.",
        "hi": "रिमाइंडर के लिए सही तारीख और समय दें।",
    },
    "default_hospital_note": {
        "en": "Choose a city to view curated hospital suggestions.",
        "hi": "क्यूरेटेड अस्पताल सुझाव देखने के लिए शहर चुनें।",
    },
    "medicine_image_missing": {
        "en": "Please upload a tablet or medicine photo first.",
        "hi": "कृपया पहले टैबलेट या दवा की फोटो अपलोड करें।",
    },
    "medicine_image_invalid": {
        "en": "Please upload a JPG, PNG, or WEBP image.",
        "hi": "कृपया JPG, PNG, या WEBP इमेज अपलोड करें।",
    },
    "medicine_image_too_large": {
        "en": "Please upload an image smaller than 3 MB for medicine analysis.",
        "hi": "दवा विश्लेषण के लिए 3 MB से छोटी इमेज अपलोड करें।",
    },
    "medicine_image_unavailable": {
        "en": "I could not analyze the medicine photo right now. Please try again with a clearer strip or box image.",
        "hi": "मैं अभी दवा की फोटो का विश्लेषण नहीं कर सका। कृपया स्ट्रिप या बॉक्स की और साफ फोटो के साथ फिर कोशिश करें।",
    },
}

LANGUAGE_HINTS = {
    "hi": {
        "bukhar",
        "khansi",
        "sar dard",
        "sir dard",
        "pet dard",
        "seene me dard",
        "saans",
        "behosh",
        "dawai",
        "aspatal",
        "thakan",
        "ulti",
        "दर्द",
        "खांसी",
        "बुखार",
        "पेट",
        "सांस",
        "बेहोश",
    }
}

HEALTH_TIPS = [
    {
        "category": "Hydration",
        "en": "Start the day with a glass of water and keep a bottle nearby so hydration stays effortless.",
        "hi": "दिन की शुरुआत एक गिलास पानी से करें और अपने पास पानी की बोतल रखें ताकि हाइड्रेशन आसान बना रहे।",
    },
    {
        "category": "Sleep",
        "en": "A consistent sleep time improves energy, mood, and recovery more than occasional catch-up sleep.",
        "hi": "नियमित सोने का समय ऊर्जा, मूड और रिकवरी को बेहतर करता है, सिर्फ कभी-कभार ज्यादा सोना नहीं।",
    },
    {
        "category": "Movement",
        "en": "Walk for five minutes every hour if you work sitting down for long stretches.",
        "hi": "अगर आप लंबे समय तक बैठकर काम करते हैं तो हर घंटे पाँच मिनट टहलें।",
    },
    {
        "category": "Nutrition",
        "en": "Try to add protein and fiber to breakfast for steadier energy through the morning.",
        "hi": "सुबह के नाश्ते में प्रोटीन और फाइबर जोड़ें ताकि पूरे दिन ऊर्जा स्थिर रहे।",
    },
    {
        "category": "Stress",
        "en": "Slow breathing for one minute can reduce stress and help you notice how your body feels.",
        "hi": "एक मिनट की धीमी गहरी सांसें तनाव कम कर सकती हैं और शरीर की स्थिति समझने में मदद करती हैं।",
    },
    {
        "category": "Prevention",
        "en": "Pair medicines or vitamins with an existing routine like breakfast so you are less likely to miss them.",
        "hi": "दवाओं या विटामिन को नाश्ते जैसी नियमित आदत के साथ जोड़ें ताकि उन्हें भूलने की संभावना कम हो।",
    },
]

HOSPITALS_BY_CITY = {
    "Delhi": [
        {
            "name": "Max Super Speciality Hospital",
            "specialty": "Cardiology, Neurology, General Medicine",
            "area": "Saket, New Delhi",
        },
        {
            "name": "Apollo Hospital",
            "specialty": "Emergency Care, General Medicine, Pulmonology",
            "area": "Sarita Vihar, New Delhi",
        },
        {
            "name": "Fortis Escorts Heart Institute",
            "specialty": "Cardiology, Critical Care",
            "area": "Okhla, New Delhi",
        },
    ],
    "Mumbai": [
        {
            "name": "Kokilaben Dhirubhai Ambani Hospital",
            "specialty": "Multispeciality, Emergency, Neurology",
            "area": "Andheri West, Mumbai",
        },
        {
            "name": "Lilavati Hospital",
            "specialty": "General Medicine, Cardiology, Critical Care",
            "area": "Bandra West, Mumbai",
        },
        {
            "name": "Fortis Hospital",
            "specialty": "Multispeciality, Emergency Care",
            "area": "Mulund, Mumbai",
        },
    ],
    "Bengaluru": [
        {
            "name": "Manipal Hospital",
            "specialty": "General Medicine, Neurology, Emergency",
            "area": "Old Airport Road, Bengaluru",
        },
        {
            "name": "Apollo Hospitals",
            "specialty": "Cardiology, Critical Care, Emergency",
            "area": "Bannerghatta Road, Bengaluru",
        },
        {
            "name": "Aster CMI Hospital",
            "specialty": "Multispeciality, General Medicine",
            "area": "Hebbal, Bengaluru",
        },
    ],
    "Hyderabad": [
        {
            "name": "Yashoda Hospitals",
            "specialty": "Cardiology, Neurology, Emergency",
            "area": "Somajiguda, Hyderabad",
        },
        {
            "name": "CARE Hospitals",
            "specialty": "Critical Care, General Medicine",
            "area": "Banjara Hills, Hyderabad",
        },
        {
            "name": "Apollo Hospitals",
            "specialty": "Multispeciality, Emergency Care",
            "area": "Jubilee Hills, Hyderabad",
        },
    ],
}

DOCTOR_LABELS = {
    "general_physician": {"en": "General Physician", "hi": "जनरल फिजिशियन"},
    "cardiologist": {"en": "Cardiologist", "hi": "कार्डियोलॉजिस्ट"},
    "neurologist": {"en": "Neurologist", "hi": "न्यूरोलॉजिस्ट"},
    "dermatologist": {"en": "Dermatologist", "hi": "डर्मेटोलॉजिस्ट"},
}

SYMPTOM_LIBRARY = {
    "fever": {
        "keywords": ["fever", "high temperature", "temperature", "बुखार", "bukhar", "ज्वर"],
        "label": {"en": "fever", "hi": "बुखार"},
        "doctor": "general_physician",
        "advice": {
            "en": "Rest, drink fluids, and watch for persistent fever, confusion, or breathing trouble.",
            "hi": "आराम करें, पर्याप्त तरल लें और लगातार बुखार, भ्रम या सांस की परेशानी पर ध्यान दें।",
        },
    },
    "cough": {
        "keywords": ["cough", "dry cough", "khansi", "खांसी", "coughing"],
        "label": {"en": "cough", "hi": "खांसी"},
        "doctor": "general_physician",
        "advice": {
            "en": "Warm fluids, rest, and throat soothing measures may help. Seek care if breathing worsens.",
            "hi": "गर्म तरल, आराम और गले को आराम देने वाले उपाय मदद कर सकते हैं। सांस बढ़ने पर डॉक्टर से मिलें।",
        },
    },
    "headache": {
        "keywords": ["headache", "migraine", "sar dard", "sir dard", "सिर दर्द", "head pain"],
        "label": {"en": "headache", "hi": "सिर दर्द"},
        "doctor": "neurologist",
        "advice": {
            "en": "Hydration, sleep, and a quiet room may help. Seek urgent care if headache is sudden or severe.",
            "hi": "पानी, नींद और शांत कमरा मदद कर सकते हैं। अचानक या बहुत तेज सिर दर्द हो तो तुरंत जांच कराएं।",
        },
    },
    "chest_pain": {
        "keywords": ["chest pain", "chest tightness", "सीने में दर्द", "सीने दर्द", "seene me dard", "seene mein dard"],
        "label": {"en": "chest pain", "hi": "सीने में दर्द"},
        "doctor": "cardiologist",
        "advice": {
            "en": "Chest pain should be taken seriously, especially with sweating, nausea, or breathlessness.",
            "hi": "सीने में दर्द को गंभीरता से लें, खासकर अगर पसीना, मितली या सांस फूलना भी हो।",
        },
    },
    "stomach_pain": {
        "keywords": ["stomach pain", "abdominal pain", "pet dard", "पेट दर्द", "पेट में दर्द", "gastric pain"],
        "label": {"en": "stomach pain", "hi": "पेट दर्द"},
        "doctor": "general_physician",
        "advice": {
            "en": "Eat light meals, sip fluids, and monitor vomiting, severe pain, or dehydration.",
            "hi": "हल्का भोजन लें, तरल पिएं और उल्टी, तेज दर्द या डिहाइड्रेशन पर नजर रखें।",
        },
    },
    "rash": {
        "keywords": ["rash", "skin rash", "itching", "allergy", "दाने", "खुजली", "त्वचा पर लालपन"],
        "label": {"en": "skin rash", "hi": "त्वचा पर दाने"},
        "doctor": "dermatologist",
        "advice": {
            "en": "Avoid new creams or irritants and get assessed if the rash spreads or causes swelling.",
            "hi": "नई क्रीम या जलन वाले उत्पादों से बचें। दाने फैलें या सूजन हो तो जांच कराएं।",
        },
    },
    "dizziness": {
        "keywords": ["dizziness", "lightheaded", "chakkar", "चक्कर", "vertigo"],
        "label": {"en": "dizziness", "hi": "चक्कर"},
        "doctor": "neurologist",
        "advice": {
            "en": "Sit down, hydrate, and avoid sudden standing. Seek care if it keeps returning.",
            "hi": "बैठ जाएं, पानी पिएं और अचानक खड़े होने से बचें। बार-बार हो तो जांच कराएं।",
        },
    },
    "difficulty_breathing": {
        "keywords": [
            "difficulty breathing",
            "shortness of breath",
            "trouble breathing",
            "saans lene me dikkat",
            "saans lene mein dikkat",
            "सांस लेने में दिक्कत",
            "सांस फूलना",
        ],
        "label": {"en": "difficulty breathing", "hi": "सांस लेने में दिक्कत"},
        "doctor": "cardiologist",
        "advice": {
            "en": "Breathing difficulty can become urgent quickly and should not be ignored.",
            "hi": "सांस की परेशानी जल्दी गंभीर हो सकती है, इसे नजरअंदाज न करें।",
        },
    },
}

EMERGENCY_RULES = {
    "chest pain": ["chest pain", "सीने में दर्द", "seene me dard", "seene mein dard", "heart attack"],
    "difficulty breathing": [
        "difficulty breathing",
        "trouble breathing",
        "shortness of breath",
        "can't breathe",
        "cannot breathe",
        "सांस लेने में दिक्कत",
        "सांस नहीं आ रही",
        "saans nahi aa rahi",
        "saans lene me dikkat",
    ],
    "unconscious": ["unconscious", "बेहोश", "behosh", "not responding", "fainted", "seizure"],
    "severe bleeding": ["severe bleeding", "heavy bleeding", "बहुत खून", "तेज खून", "khoon bah raha"],
}

GENERAL_KNOWLEDGE = [
    {
        "keywords": ["sleep", "नींद"],
        "en": "Good sleep habits include a regular bedtime, low screen light before sleep, and a cool quiet room.",
        "hi": "अच्छी नींद के लिए रोज एक जैसा सोने का समय रखें, सोने से पहले स्क्रीन कम करें और कमरा शांत रखें।",
    },
    {
        "keywords": ["stress", "anxiety", "तनाव", "घबराहट"],
        "en": "For stress, try slow breathing, a short walk, and limiting caffeine. If anxiety is frequent, speak with a clinician.",
        "hi": "तनाव के लिए धीमी सांसें, छोटी वॉक और कम कैफीन मदद कर सकते हैं। बार-बार घबराहट हो तो डॉक्टर से बात करें।",
    },
    {
        "keywords": ["water", "hydrate", "hydration", "पानी", "हाइड्रेशन"],
        "en": "Steady hydration matters more than drinking large amounts at once. Sip fluids through the day.",
        "hi": "एक बार में बहुत पानी पीने से ज्यादा जरूरी है कि आप पूरे दिन थोड़ा-थोड़ा पानी पीते रहें।",
    },
    {
        "keywords": ["diet", "food", "nutrition", "खाना", "डाइट", "पोषण"],
        "en": "A balanced plate usually includes protein, fiber, healthy fats, and colorful vegetables or fruit.",
        "hi": "संतुलित भोजन में आम तौर पर प्रोटीन, फाइबर, हेल्दी फैट और रंगीन सब्जियां या फल शामिल होते हैं।",
    },
]

BMI_MESSAGE_PATTERNS = ["bmi", "body mass index", "weight", "height", "वजन", "लंबाई", "ऊंचाई"]
TIP_PATTERNS = ["tip", "health tip", "daily tip", "wellness", "स्वास्थ्य टिप", "टिप"]
HOSPITAL_PATTERNS = ["hospital", "nearby hospital", "hospital suggestion", "अस्पताल", "पास का अस्पताल", "hospital near me"]
GREETING_PATTERNS = ["hello", "hi", "hey", "namaste", "नमस्ते", "हैलो"]
DOCTOR_SPECIALTY_FILTER = {
    "general_physician": "General Medicine",
    "cardiologist": "Cardiology",
    "neurologist": "Neurology",
    "dermatologist": "Dermatology",
}

MEDICINE_SUGGESTIONS = {
    "fever": [
        {
            "name": "Paracetamol (Acetaminophen)",
            "en": "a common OTC option for fever or body ache if it is safe for you",
            "hi": "बुखार या शरीर दर्द के लिए एक सामान्य OTC विकल्प, अगर यह आपके लिए सुरक्षित हो",
        }
    ],
    "headache": [
        {
            "name": "Paracetamol (Acetaminophen)",
            "en": "often used for mild headache if you do not have liver disease or a doctor has not told you to avoid it",
            "hi": "हल्के सिर दर्द में इस्तेमाल किया जाता है, अगर आपको लिवर की बीमारी नहीं है और डॉक्टर ने मना नहीं किया है",
        }
    ],
    "cough": [
        {
            "name": "Dextromethorphan cough syrup",
            "en": "sometimes used for dry cough after confirming with a pharmacist or doctor",
            "hi": "सूखी खांसी में कभी-कभी उपयोग किया जाता है, लेकिन पहले फार्मासिस्ट या डॉक्टर से पुष्टि करें",
        },
        {
            "name": "Throat lozenges",
            "en": "can help soothe throat irritation",
            "hi": "गले की खराश में राहत दे सकते हैं",
        },
    ],
    "rash": [
        {
            "name": "Calamine lotion",
            "en": "may soothe mild itching or irritated skin",
            "hi": "हल्की खुजली या जलन वाली त्वचा में आराम दे सकता है",
        },
        {
            "name": "Cetirizine",
            "en": "is sometimes used for allergy-related itching after checking that it suits you",
            "hi": "एलर्जी वाली खुजली में कभी-कभी उपयोग किया जाता है, लेकिन पहले सुनिश्चित करें कि यह आपके लिए ठीक है",
        },
    ],
    "stomach_pain": [
        {
            "name": "ORS",
            "en": "may help if stomach upset is linked with vomiting, loose motions, or dehydration",
            "hi": "अगर पेट की परेशानी उल्टी, दस्त या डिहाइड्रेशन से जुड़ी हो तो मदद कर सकता है",
        },
        {
            "name": "Calcium carbonate antacid",
            "en": "is sometimes used only when discomfort feels like acidity or heartburn",
            "hi": "कभी-कभी तब उपयोग किया जाता है जब परेशानी एसिडिटी या जलन जैसी लगे",
        },
    ],
}

SERIOUS_SYMPTOMS = {"chest_pain", "difficulty_breathing"}


def translate(key: str, language: str) -> str:
    selected = "hi" if language == "hi" else "en"
    return UI_TEXT[key][selected]


def detect_language(message: str, preferred: str | None = None) -> str:
    if preferred in {"en", "hi"}:
        return preferred

    normalized = normalize_text(message)
    if re.search(r"[\u0900-\u097F]", message):
        return "hi"

    if any(token in normalized for token in LANGUAGE_HINTS["hi"]):
        return "hi"

    return "en"


def normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def pick_tip(language: str) -> dict[str, str]:
    item = random.choice(HEALTH_TIPS)
    return {
        "category": item["category"],
        "tip": item["hi"] if language == "hi" else item["en"],
    }


def parse_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_bmi_values_from_text(message: str) -> tuple[float | None, float | None]:
    normalized = normalize_text(message)
    weight_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilogram|kilograms|किलो|किलोग्राम)",
        normalized,
    )
    height_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:cm|cms|centimeter|centimeters|सेमी)",
        normalized,
    )
    weight = float(weight_match.group(1)) if weight_match else None
    height = float(height_match.group(1)) if height_match else None
    return weight, height


def calculate_bmi_result(height_cm: float, weight_kg: float, language: str) -> dict[str, object]:
    height_m = height_cm / 100
    bmi_value = weight_kg / (height_m * height_m)

    if bmi_value < 18.5:
        category_key = "underweight"
        category = "Underweight" if language == "en" else "कम वजन"
        advice = (
            "Try balanced meals with enough calories and protein, and consider speaking with a doctor."
            if language == "en"
            else "संतुलित भोजन लें जिसमें पर्याप्त कैलोरी और प्रोटीन हों, और जरूरत हो तो डॉक्टर से सलाह लें।"
        )
    elif bmi_value < 25:
        category_key = "normal"
        category = "Normal" if language == "en" else "सामान्य"
        advice = (
            "Your BMI is in a healthy range. Keep up regular activity, sleep, and balanced nutrition."
            if language == "en"
            else "आपका BMI स्वस्थ रेंज में है। नियमित गतिविधि, नींद और संतुलित भोजन जारी रखें।"
        )
    elif bmi_value < 30:
        category_key = "overweight"
        category = "Overweight" if language == "en" else "अधिक वजन"
        advice = (
            "Small changes in food choices, sleep, and movement can help. A doctor can personalize guidance."
            if language == "en"
            else "खानपान, नींद और गतिविधि में छोटे बदलाव मदद कर सकते हैं। डॉक्टर आपको व्यक्तिगत सलाह दे सकते हैं।"
        )
    else:
        category_key = "obesity"
        category = "Obesity" if language == "en" else "मोटापा"
        advice = (
            "Consider a medical review for a personalized plan that fits your overall health."
            if language == "en"
            else "अपने समग्र स्वास्थ्य के अनुसार व्यक्तिगत योजना के लिए डॉक्टर से सलाह लें।"
        )

    return {
        "bmi": round(bmi_value, 1),
        "category": category,
        "category_key": category_key,
        "advice": advice,
    }


def detect_symptoms(message: str) -> list[str]:
    normalized = normalize_text(message)
    matches: list[str] = []

    for symptom_key, symptom_data in SYMPTOM_LIBRARY.items():
        if any(keyword in normalized for keyword in symptom_data["keywords"]):
            matches.append(symptom_key)

    return matches


def get_groq_client() -> Groq | None:
    global _groq_client

    if not GROQ_API_KEY or Groq is None:
        return None

    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)

    return _groq_client


def guess_image_mime_type(filename: str, provided_mime_type: str | None = None) -> str:
    normalized_mime = (provided_mime_type or "").strip().lower()
    if normalized_mime in ALLOWED_IMAGE_MIME_TYPES:
        return normalized_mime

    guessed_mime, _ = mimetypes.guess_type(filename)
    if guessed_mime in ALLOWED_IMAGE_MIME_TYPES:
        return guessed_mime

    return "image/jpeg"


def is_allowed_medicine_image(filename: str, mime_type: str | None = None) -> bool:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        return False

    if mime_type:
        return mime_type in ALLOWED_IMAGE_MIME_TYPES

    return True


def build_medicine_image_fallback(language: str) -> dict[str, object]:
    if language == "hi":
        response = (
            "मैं फोटो से दवा की पूरी पहचान अभी पक्का नहीं कर सका। कृपया स्ट्रिप, बॉक्स, या टैबलेट पर लिखा नाम साफ दिखने वाली फोटो अपलोड करें। "
            "जब तक नाम पक्का न हो, कोई अज्ञात टैबलेट न लें। फार्मासिस्ट या डॉक्टर से पुष्टि कर लेना सबसे सुरक्षित रहेगा।"
        )
    else:
        response = (
            "I could not confidently identify the medicine from this image yet. Please upload a clearer photo of the strip, box, or tablet imprint text. "
            "Do not take an unknown tablet until a pharmacist or doctor confirms what it is."
        )

    return {
        "response": response,
        "medicine_analysis": {
            "medicine_name": "",
            "composition": "",
            "possible_uses": [],
            "common_side_effects": [],
            "warnings": [],
            "prescription_status": "",
            "confidence": "low",
            "uncertain": True,
            "doctor_advice": response,
            "visible_text": "",
        },
    }


def analyze_medicine_image(
    *,
    image_bytes: bytes,
    filename: str,
    mime_type: str,
    language: str,
) -> dict[str, object] | None:
    client = get_groq_client()
    if client is None:
        return None

    encoded_image = base64.b64encode(image_bytes).decode("utf-8")
    language_name = "Hindi" if language == "hi" else "English"
    if language == "hi":
        prompt = (
            "इस दवा या टैबलेट की फोटो को बहुत सावधानी से देखें। "
            "अगर स्ट्रिप, बॉक्स, ब्रांड नाम, कंपोजिशन, या टैबलेट पर कोई इम्प्रिंट साफ दिख रहा हो तो वही निकालें। "
            "सिर्फ रंग या आकार देखकर दवा का नाम कभी तय मत करें। "
            "अगर फोटो से पहचान पक्की नहीं है तो uncertain=true रखें और medicine_name खाली छोड़ दें। "
            "उसी भाषा में JSON लौटाएं। डोज़ मत बताएं। "
            "JSON keys exactly रखें: medicine_name, composition, possible_uses, common_side_effects, warnings, prescription_status, confidence, uncertain, doctor_advice, chat_response, visible_text."
        )
    else:
        prompt = (
            "Analyze this medicine or tablet photo very carefully. "
            "Extract only what is actually visible from the strip, box, label, or pill imprint. "
            "Never identify a medicine from color or shape alone. "
            "If the image is unclear or the medicine cannot be confirmed, set uncertain=true and leave medicine_name empty. "
            "Return JSON in the same language as the user. Do not provide dosage instructions. "
            "Use exactly these keys: medicine_name, composition, possible_uses, common_side_effects, warnings, prescription_status, confidence, uncertain, doctor_advice, chat_response, visible_text."
        )

    try:
        completion = client.chat.completions.create(
            model=GROQ_VISION_MODEL,
            response_format={"type": "json_object"},
            temperature=0.2,
            max_completion_tokens=700,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a cautious healthcare assistant doing OCR and medicine-pack reading from images. "
                        "Prioritize safety and visible text extraction over guessing."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Language: {language_name}. {prompt}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{encoded_image}",
                            },
                        },
                    ],
                },
            ],
        )
        content = completion.choices[0].message.content
        if not content:
            return None

        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return None

        chat_response = str(parsed.get("chat_response", "")).strip()
        medicine_name = str(parsed.get("medicine_name", "")).strip()
        composition = str(parsed.get("composition", "")).strip()
        prescription_status = str(parsed.get("prescription_status", "")).strip()
        doctor_advice = str(parsed.get("doctor_advice", "")).strip()
        visible_text = str(parsed.get("visible_text", "")).strip()
        confidence = str(parsed.get("confidence", "low")).strip().lower() or "low"
        uncertain = bool(parsed.get("uncertain", False))
        possible_uses = [str(item).strip() for item in parsed.get("possible_uses", []) if str(item).strip()]
        side_effects = [str(item).strip() for item in parsed.get("common_side_effects", []) if str(item).strip()]
        warnings = [str(item).strip() for item in parsed.get("warnings", []) if str(item).strip()]

        if not chat_response:
            lines: list[str] = []
            if language == "hi":
                if medicine_name:
                    lines.append(f"फोटो के आधार पर यह दवा {medicine_name} लग रही है।")
                else:
                    lines.append("फोटो से दवा का नाम पक्का नहीं दिख रहा।")
                if visible_text:
                    lines.append(f"फोटो में दिखा टेक्स्ट: {visible_text}")
                if composition:
                    lines.append(f"संभावित कंपोजिशन: {composition}")
                if possible_uses:
                    lines.append(f"संभावित उपयोग: {', '.join(possible_uses)}")
                if warnings:
                    lines.append(f"सावधानियां: {', '.join(warnings[:3])}")
                if doctor_advice:
                    lines.append(doctor_advice)
            else:
                if medicine_name:
                    lines.append(f"From the photo, this appears to be {medicine_name}.")
                else:
                    lines.append("The medicine name is not fully clear from the image.")
                if visible_text:
                    lines.append(f"Visible text: {visible_text}")
                if composition:
                    lines.append(f"Likely composition: {composition}")
                if possible_uses:
                    lines.append(f"Possible uses: {', '.join(possible_uses)}")
                if warnings:
                    lines.append(f"Warnings: {', '.join(warnings[:3])}")
                if doctor_advice:
                    lines.append(doctor_advice)
            chat_response = " ".join(lines).strip()

        return {
            "response": chat_response,
            "medicine_analysis": {
                "medicine_name": medicine_name,
                "composition": composition,
                "possible_uses": possible_uses,
                "common_side_effects": side_effects,
                "warnings": warnings,
                "prescription_status": prescription_status,
                "confidence": confidence,
                "uncertain": uncertain,
                "doctor_advice": doctor_advice,
                "visible_text": visible_text,
            },
        }
    except Exception:
        return None


def build_medicine_guidance(
    symptoms: list[str],
    language: str,
    severity: str,
    emergency: bool,
) -> dict[str, object]:
    symptom_set = set(symptoms)

    if emergency or symptom_set & SERIOUS_SYMPTOMS or severity in {"high", "critical"}:
        summary = (
            "Because these symptoms may be serious, I would not suggest self-medicating. Please see a doctor as soon as possible."
            if language == "en"
            else "क्योंकि ये लक्षण गंभीर हो सकते हैं, मैं बिना डॉक्टर के दवा लेने की सलाह नहीं दूंगा। कृपया जल्द डॉक्टर से मिलें।"
        )
        return {"items": [], "summary": summary}

    items: list[dict[str, str]] = []
    seen: set[str] = set()

    for symptom in symptoms:
        for suggestion in MEDICINE_SUGGESTIONS.get(symptom, []):
            if suggestion["name"] in seen:
                continue
            seen.add(suggestion["name"])
            items.append(
                {
                    "name": suggestion["name"],
                    "note": suggestion["hi"] if language == "hi" else suggestion["en"],
                }
            )

    if not items:
        summary = (
            "I do not have a safe medicine-name suggestion for this symptom pattern. If it continues, please speak with a doctor."
            if language == "en"
            else "इस तरह के लक्षणों के लिए मैं सुरक्षित दवा-नाम सुझाव नहीं दे सकता। अगर समस्या बनी रहे तो डॉक्टर से बात करें।"
        )
        return {"items": [], "summary": summary}

    prefix = (
        "Common OTC medicine names to discuss with a pharmacist or doctor"
        if language == "en"
        else "फार्मासिस्ट या डॉक्टर से पूछने लायक सामान्य OTC दवाओं के नाम"
    )
    item_text = "; ".join(f"{item['name']} - {item['note']}" for item in items[:3])
    return {"items": items[:3], "summary": f"{prefix}: {item_text}."}


def build_structured_response(
    *,
    language: str,
    symptoms: list[str],
    possible_causes: str,
    medicine_guidance: dict[str, object],
    self_care: str,
    doctor_label: str,
    follow_up: str,
    hospitals: list[dict[str, str]],
    mention_doctor: bool = True,
    mention_hospitals: bool = False,
) -> str:
    medicine_items = medicine_guidance.get("items", [])
    hospital_names = ", ".join(item["name"] for item in hospitals[:2])

    if language == "hi":
        symptom_text = ", ".join(SYMPTOM_LIBRARY[item]["label"]["hi"] for item in symptoms) if symptoms else ""
        parts: list[str] = []
        if symptom_text:
            parts.append(f"आपके बताए लक्षण {symptom_text} हैं, और यह {possible_causes}")
        else:
            parts.append(possible_causes)

        if medicine_items:
            names = ", ".join(item["name"] for item in medicine_items)
            parts.append(f"अगर यह आपके लिए सुरक्षित हो, तो {names} जैसे OTC विकल्पों के बारे में फार्मासिस्ट या डॉक्टर से पूछ सकते हैं।")
        elif symptoms:
            parts.append(medicine_guidance["summary"])

        if self_care:
            parts.append(f"अभी के लिए {self_care}")

        if mention_doctor:
            doctor_line = f"{doctor_label} से मिलना बेहतर रहेगा। {follow_up}"
            if mention_hospitals and hospital_names:
                doctor_line += f" जरूरत पड़े तो {hospital_names} जैसे अस्पताल भी विकल्प हो सकते हैं।"
            parts.append(doctor_line)

        return " ".join(parts)

    symptom_text = ", ".join(SYMPTOM_LIBRARY[item]["label"]["en"] for item in symptoms) if symptoms else ""
    parts = []
    if symptom_text:
        parts.append(f"It sounds like you're dealing with {symptom_text}, and {possible_causes}")
    else:
        parts.append(possible_causes)

    if medicine_items:
        names = ", ".join(item["name"] for item in medicine_items)
        parts.append(f"If these are safe for you, you could ask a pharmacist or doctor about common OTC options such as {names}.")
    elif symptoms:
        parts.append(medicine_guidance["summary"])

    if self_care:
        parts.append(f"For now, {self_care}")

    if mention_doctor:
        doctor_line = f"It would be reasonable to speak with a {doctor_label}. {follow_up}"
        if mention_hospitals and hospital_names:
            doctor_line += f" If needed, options nearby include {hospital_names}."
        parts.append(doctor_line)

    return " ".join(parts)


def generate_groq_medical_response(
    *,
    message: str,
    language: str,
    session_id: str,
    symptoms: list[str],
    doctor_label: str,
    severity: str,
    possible_causes: str,
    medicine_guidance: dict[str, object],
    emergency: bool,
    city: str,
    hospitals: list[dict[str, str]],
    base_reply: str,
    mention_medicines: bool,
    mention_doctor: bool,
    mention_hospitals: bool,
    ask_follow_up: bool,
) -> str | None:
    client = get_groq_client()
    if client is None:
        return None

    recent_history = get_chat_history(session_id=session_id, limit=6)
    history_messages = []

    for item in recent_history[-4:]:
        role = "assistant" if item["role"] == "assistant" else "user"
        history_messages.append(
            {
                "role": role,
                "content": str(item["message"])[:800],
            }
        )

    medicine_items = medicine_guidance.get("items", [])
    if medicine_items:
        medicine_text = "\n".join(f"- {item['name']}: {item['note']}" for item in medicine_items)
    else:
        medicine_text = "- None. Tell the user to see a doctor instead of self-medicating."

    hospital_text = "\n".join(
        f"- {hospital['name']} ({hospital['area']})"
        for hospital in hospitals[:3]
    ) or "- No curated hospital list available."

    system_prompt = (
        "You are a careful, empathetic healthcare assistant in a web app. "
        "Your style should feel natural and polished, similar to a strong general-purpose conversational AI. "
        "You provide educational guidance only, not diagnosis. "
        "Reply in the same language as the user. "
        "Use uncertainty honestly: say 'could be', 'may be', or 'one possibility is' when appropriate. "
        "Only mention medicine names from the allowed list provided in the prompt, and only as common OTC examples. "
        "Never mention doses. Never invent medicine names. "
        "Do not recommend antibiotics, steroids, sleeping pills, opioids, or prescription medicines. "
        "Do not sound robotic, database-like, or overly repetitive. "
        "Keep the answer concise, useful, and human."
    )

    user_prompt = f"""
Language: {"Hindi" if language == "hi" else "English"}
Patient city: {city}
Patient message: {message}
Detected symptoms: {", ".join(symptoms) if symptoms else "none"}
Severity: {severity}
Suggested doctor: {doctor_label}
Possible causes: {possible_causes or "not specific"}
Emergency: {"yes" if emergency else "no"}
Allowed medicine examples:
{medicine_text}
Nearby hospitals:
{hospital_text}
Safe fallback guidance:
{base_reply}

Write a natural chatbot reply in the same language using this flow:
1. Briefly acknowledge the user's problem.
2. Explain the likely issue in simple language.
3. Mention safe medicine names only if they are in the allowed list.
4. Give simple home-care advice.
5. End with doctor or hospital advice when symptoms are serious or persistent.

Output controls:
- Mention medicines: {"yes" if mention_medicines else "no"}
- Mention doctor follow-up: {"yes" if mention_doctor else "no"}
- Mention nearby hospitals: {"yes" if mention_hospitals else "no"}
- Ask one short follow-up question at the end if helpful: {"yes" if ask_follow_up else "no"}

Rules:
- Mention only medicine names from the allowed list.
- Never invent medicine names.
- Never mention doses.
- If symptoms are serious, tell the user not to self-medicate.
- Only mention nearby hospitals if the output controls say yes.
- Only mention medicines if the output controls say yes.
- If the output controls say doctor follow-up is no, do not push a doctor visit unless the case clearly sounds risky.
- If the user has not shared any symptoms yet, simply greet them, say you can help, and ask one short follow-up question.
- Do not use headings, numbered points, or rigid labels.
"""

    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.45,
            max_completion_tokens=320,
            messages=[
                {"role": "system", "content": system_prompt},
                *history_messages,
                {"role": "user", "content": user_prompt},
            ],
        )
        content = completion.choices[0].message.content
        if not content:
            return None
        return content.strip()
    except Exception:
        return None


def detect_emergency(message: str, language: str) -> dict[str, object]:
    normalized = normalize_text(message)
    triggers = [label for label, keywords in EMERGENCY_RULES.items() if any(keyword in normalized for keyword in keywords)]
    is_emergency = bool(triggers)

    if language == "hi":
        trigger_labels = [
            {
                "chest pain": "सीने में दर्द",
                "difficulty breathing": "सांस लेने में दिक्कत",
                "unconscious": "बेहोशी",
                "severe bleeding": "गंभीर रक्तस्राव",
            }[trigger]
            for trigger in triggers
        ]
        message_text = "कृपया तुरंत नजदीकी अस्पताल या इमरजेंसी सेवा से संपर्क करें।"
    else:
        trigger_labels = triggers
        message_text = "Please contact the nearest hospital immediately."

    return {
        "is_emergency": is_emergency,
        "triggers": trigger_labels,
        "alert": message_text,
    }


def determine_doctor(symptoms: list[str]) -> str:
    if not symptoms:
        return "general_physician"

    symptom_set = set(symptoms)

    if "chest_pain" in symptom_set or "difficulty_breathing" in symptom_set:
        return "cardiologist"

    if "rash" in symptom_set:
        return "dermatologist"

    if symptom_set <= {"headache", "dizziness"}:
        return "neurologist"

    return "general_physician"


def determine_severity(message: str, symptoms: list[str], emergency: bool) -> str:
    normalized = normalize_text(message)

    if emergency:
        return "critical"
    if any(word in normalized for word in ["severe", "persistent", "worsening", "बहुत", "लगातार", "तेज"]):
        return "high"
    if len(symptoms) >= 2:
        return "moderate"
    return "mild"


def get_possible_causes(symptoms: list[str], language: str) -> str:
    symptom_set = set(symptoms)
    if {"fever", "cough"} <= symptom_set:
        return (
            "These symptoms may happen with a viral infection, flu-like illness, or throat irritation."
            if language == "en"
            else "ये लक्षण वायरल इन्फेक्शन, फ्लू जैसे संक्रमण या गले की जलन में हो सकते हैं।"
        )
    if {"fever", "headache"} <= symptom_set:
        return (
            "This pattern may be seen with viral fever, dehydration, or inadequate rest."
            if language == "en"
            else "यह पैटर्न वायरल बुखार, डिहाइड्रेशन या पर्याप्त आराम न मिलने पर देखा जा सकता है।"
        )
    if {"stomach_pain"} <= symptom_set:
        return (
            "Common possibilities include acidity, indigestion, constipation, or an infection."
            if language == "en"
            else "आम कारणों में एसिडिटी, अपच, कब्ज या संक्रमण शामिल हो सकते हैं।"
        )
    if {"headache"} <= symptom_set:
        return (
            "Headache can happen with stress, dehydration, poor sleep, or migraine."
            if language == "en"
            else "सिर दर्द तनाव, डिहाइड्रेशन, कम नींद या माइग्रेन में हो सकता है।"
        )
    if {"rash"} <= symptom_set:
        return (
            "Skin rash may happen with allergy, dermatitis, heat irritation, or infection."
            if language == "en"
            else "त्वचा पर दाने एलर्जी, डर्मेटाइटिस, गर्मी की जलन या संक्रमण में हो सकते हैं।"
        )
    if {"chest_pain"} <= symptom_set or {"difficulty_breathing"} <= symptom_set:
        return (
            "Chest discomfort or breathing problems need prompt medical assessment because several serious causes are possible."
            if language == "en"
            else "सीने की परेशानी या सांस की दिक्कत में जल्दी चिकित्सा जांच जरूरी है क्योंकि इसके कई गंभीर कारण हो सकते हैं।"
        )
    if {"cough"} <= symptom_set:
        return (
            "Cough may happen with viral infection, allergy, throat irritation, or acid reflux."
            if language == "en"
            else "खांसी वायरल संक्रमण, एलर्जी, गले की जलन या एसिड रिफ्लक्स में हो सकती है।"
        )
    return (
        "Your symptoms need proper context and examination for a precise diagnosis."
        if language == "en"
        else "सटीक निदान के लिए लक्षणों के साथ सही संदर्भ और जांच की जरूरत होती है।"
    )


def get_hospital_suggestions(city: str, specialty: str | None = None) -> list[dict[str, str]]:
    hospitals = HOSPITALS_BY_CITY.get(city, [])
    if not specialty:
        return hospitals

    specialty_lower = specialty.lower()
    filtered = [item for item in hospitals if specialty_lower in item["specialty"].lower()]
    return filtered or hospitals


def format_hospital_note(city: str, language: str) -> str:
    if city not in HOSPITALS_BY_CITY:
        return translate("default_hospital_note", language)

    if language == "hi":
        return f"{city} के लिए क्यूरेटेड अस्पताल सुझाव दिखाए जा रहे हैं।"

    return f"Showing curated hospital suggestions for {city}."


def build_general_response(message: str, language: str) -> str | None:
    normalized = normalize_text(message)

    for item in GENERAL_KNOWLEDGE:
        if any(keyword in normalized for keyword in item["keywords"]):
            return item["hi"] if language == "hi" else item["en"]

    if any(keyword in normalized for keyword in GREETING_PATTERNS if len(keyword) > 2):
        return (
            "Hello, I can help with symptoms, BMI, reminders, health tips, nearby hospitals, and emergency guidance. Tell me how you are feeling."
            if language == "en"
            else "नमस्ते, मैं लक्षण, BMI, रिमाइंडर, हेल्थ टिप्स, अस्पताल सुझाव और इमरजेंसी गाइडेंस में मदद कर सकता हूँ। बताइए आप कैसा महसूस कर रहे हैं।"
        )

    return None


def build_chat_response(message: str, language: str, city: str, session_id: str) -> dict[str, object]:
    emergency = detect_emergency(message, language)
    symptoms = detect_symptoms(message)
    doctor_key = determine_doctor(symptoms)
    doctor_label = DOCTOR_LABELS[doctor_key][language]
    severity = determine_severity(message, symptoms, emergency["is_emergency"])
    hospitals = get_hospital_suggestions(city, DOCTOR_SPECIALTY_FILTER[doctor_key])
    medicine_guidance = build_medicine_guidance(symptoms, language, severity, emergency["is_emergency"])

    if emergency["is_emergency"]:
        if language == "hi":
            reply = (
                f"आपके संदेश में आपातकालीन संकेत मिले: {', '.join(emergency['triggers'])}. "
                "कृपया तुरंत नजदीकी अस्पताल या इमरजेंसी सेवा से संपर्क करें। अकेले न रहें और तुरंत सहायता लें।"
            )
        else:
            reply = (
                f"I detected emergency warning signs: {', '.join(emergency['triggers'])}. "
                "Please contact the nearest hospital immediately and seek urgent in-person care."
            )
        return {
            "response": reply,
            "language": language,
            "emergency": True,
            "triggers": emergency["triggers"],
            "response_source": "rules",
            "doctor": doctor_label,
            "severity": severity,
            "possible_causes": get_possible_causes(symptoms, language),
            "hospitals": hospitals,
            "medicine_summary": medicine_guidance["summary"],
            "disclaimer": DISCLAIMER[language],
            "follow_up": emergency["alert"],
        }

    normalized = normalize_text(message)
    if any(token in normalized for token in BMI_MESSAGE_PATTERNS):
        weight, height = extract_bmi_values_from_text(message)
        if weight is not None and height is not None and height > 0:
            bmi = calculate_bmi_result(height, weight, language)
            if language == "hi":
                reply = (
                    f"आपका अनुमानित BMI {bmi['bmi']} है, जो '{bmi['category']}' श्रेणी में आता है। {bmi['advice']}"
                )
            else:
                reply = (
                    f"Your estimated BMI is {bmi['bmi']}, which falls in the '{bmi['category']}' category. {bmi['advice']}"
                )
            return {
                "response": reply,
                "language": language,
                "emergency": False,
                "triggers": [],
                "response_source": "rules",
                "doctor": doctor_label,
                "severity": "info",
                "possible_causes": "",
                "hospitals": hospitals,
                "bmi": bmi,
                "disclaimer": DISCLAIMER[language],
                "follow_up": "",
            }

    if any(token in normalized for token in TIP_PATTERNS):
        tip = pick_tip(language)
        reply = (
            f"Today's health tip: {tip['tip']}"
            if language == "en"
            else f"आज की हेल्थ टिप: {tip['tip']}"
        )
        return {
            "response": reply,
            "language": language,
            "emergency": False,
            "triggers": [],
            "response_source": "rules",
            "doctor": doctor_label,
            "severity": "info",
            "possible_causes": "",
            "hospitals": hospitals,
            "tip": tip,
            "disclaimer": DISCLAIMER[language],
            "follow_up": "",
        }

    if any(token in normalized for token in HOSPITAL_PATTERNS):
        reply = (
            format_hospital_note(city, language)
            if city in HOSPITALS_BY_CITY
            else (
                "Please choose a city and I will suggest nearby hospital options."
                if language == "en"
                else "कृपया एक शहर चुनें, फिर मैं नजदीकी अस्पताल सुझाव दूँगा।"
            )
        )
        return {
            "response": reply,
            "language": language,
            "emergency": False,
            "triggers": [],
            "response_source": "rules",
            "doctor": doctor_label,
            "severity": "info",
            "possible_causes": "",
            "hospitals": hospitals,
            "disclaimer": DISCLAIMER[language],
            "follow_up": "",
        }

    general_response = build_general_response(message, language)
    if general_response and not symptoms:
        general_follow_up = (
            "If the problem continues or feels unusual, please speak with a doctor."
            if language == "en"
            else "अगर परेशानी बनी रहती है या असामान्य लगती है, तो डॉक्टर से बात करें।"
        )
        ai_reply = generate_groq_medical_response(
            message=message,
            language=language,
            session_id=session_id,
            symptoms=symptoms,
            doctor_label=doctor_label,
            severity="info",
            possible_causes=general_response,
            medicine_guidance=medicine_guidance,
            emergency=False,
            city=city,
            hospitals=hospitals,
            base_reply=general_response,
            mention_medicines=False,
            mention_doctor=False,
            mention_hospitals=False,
            ask_follow_up=True,
        )
        return {
            "response": ai_reply or general_response,
            "language": language,
            "emergency": False,
            "triggers": [],
            "response_source": "groq" if ai_reply else "rules",
            "doctor": doctor_label,
            "severity": "info",
            "possible_causes": "",
            "hospitals": hospitals,
            "disclaimer": DISCLAIMER[language],
            "follow_up": general_follow_up,
        }

    if symptoms:
        self_care = " ".join(SYMPTOM_LIBRARY[item]["advice"][language] for item in symptoms[:2])
        possible_causes = get_possible_causes(symptoms, language)

        if language == "hi":
            follow_up = (
                "अगर लक्षण बढ़ रहे हैं, लगातार बने हुए हैं, या नए गंभीर संकेत जुड़ते हैं, तो डॉक्टर से जल्दी मिलें।"
            )
        else:
            follow_up = (
                "If symptoms are worsening, persistent, or new red-flag signs appear, book an in-person medical review soon."
            )
        base_reply = build_structured_response(
            language=language,
            symptoms=symptoms,
            possible_causes=possible_causes,
            medicine_guidance=medicine_guidance,
            self_care=self_care,
            doctor_label=doctor_label,
            follow_up=follow_up,
            hospitals=hospitals,
            mention_doctor=True,
            mention_hospitals=severity in {"high", "critical"} or doctor_key == "cardiologist",
        )

        ai_reply = generate_groq_medical_response(
            message=message,
            language=language,
            session_id=session_id,
            symptoms=symptoms,
            doctor_label=doctor_label,
            severity=severity,
            possible_causes=possible_causes,
            medicine_guidance=medicine_guidance,
            emergency=False,
            city=city,
            hospitals=hospitals,
            base_reply=base_reply,
            mention_medicines=bool(medicine_guidance.get("items")),
            mention_doctor=True,
            mention_hospitals=severity in {"high", "critical"} or doctor_key == "cardiologist",
            ask_follow_up=severity in {"mild", "moderate"},
        )
        reply = ai_reply or base_reply

        return {
            "response": reply,
            "language": language,
            "emergency": False,
            "triggers": [],
            "response_source": "groq" if ai_reply else "rules",
            "doctor": doctor_label,
            "severity": severity,
            "possible_causes": possible_causes,
            "hospitals": hospitals,
            "medicine_summary": medicine_guidance["summary"],
            "disclaimer": DISCLAIMER[language],
            "follow_up": follow_up,
        }

    general_follow_up = (
        "If symptoms become stronger or start affecting breathing, chest comfort, or alertness, please see a doctor."
        if language == "en"
        else "अगर लक्षण बढ़ने लगें या सांस, सीने या होश पर असर पड़े, तो डॉक्टर से मिलें।"
    )
    fallback = build_structured_response(
        language=language,
        symptoms=[],
        possible_causes=(
            "Your message does not match a known symptom pattern yet."
            if language == "en"
            else "आपके संदेश से अभी कोई स्पष्ट लक्षण पैटर्न नहीं मिला।"
        ),
        medicine_guidance=medicine_guidance,
        self_care=(
            "Share your exact symptoms, duration, and severity for a better suggestion."
            if language == "en"
            else "बेहतर सुझाव के लिए अपने सटीक लक्षण, कितने समय से हैं, और कितने गंभीर हैं यह बताएं।"
        ),
        doctor_label=doctor_label,
        follow_up=general_follow_up,
        hospitals=hospitals,
        mention_doctor=False,
        mention_hospitals=False,
    )
    ai_reply = generate_groq_medical_response(
        message=message,
        language=language,
        session_id=session_id,
        symptoms=symptoms,
        doctor_label=doctor_label,
        severity="info",
        possible_causes="",
        medicine_guidance=medicine_guidance,
        emergency=False,
        city=city,
        hospitals=hospitals,
        base_reply=fallback,
        mention_medicines=False,
        mention_doctor=False,
        mention_hospitals=False,
        ask_follow_up=True,
    )
    reply = ai_reply or fallback
    return {
        "response": reply,
        "language": language,
        "emergency": False,
        "triggers": [],
        "response_source": "groq" if ai_reply else "rules",
        "doctor": doctor_label,
        "severity": "info",
        "possible_causes": "",
        "hospitals": hospitals,
        "medicine_summary": medicine_guidance["summary"],
        "disclaimer": DISCLAIMER[language],
        "follow_up": general_follow_up,
    }


def get_current_user() -> dict[str, object] | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(int(user_id))


def get_or_create_chat_session_id(user_id: int) -> str:
    existing = session.get("chat_session_id")
    if existing:
        return str(existing)

    session_id = f"user-{user_id}"
    session["chat_session_id"] = session_id
    return session_id


def auth_error_response() -> tuple[object, int]:
    return jsonify({"error": "Please log in to continue."}), 401


def serialize_profile_user(user: dict[str, object]) -> dict[str, object]:
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "age": user.get("age"),
        "gender": user.get("gender", ""),
        "city": user.get("city", "Delhi"),
        "phone": user.get("phone", ""),
        "medical_conditions": user.get("medical_conditions", ""),
        "bio": user.get("bio", ""),
    }


def parse_optional_int(value: object) -> int | None:
    if value in {None, ""}:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "healthcare-ai-secret")

    init_db()

    @app.get("/")
    def index() -> object:
        if get_current_user():
            return redirect(url_for("dashboard_page"))
        return render_template("index.html")

    @app.get("/dashboard")
    def dashboard_page() -> object:
        user = get_current_user()
        if not user:
            return redirect(url_for("index"))
        return render_template("dashboard.html", user=user)

    @app.get("/logout")
    def logout_page() -> object:
        session.clear()
        return redirect(url_for("index"))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}

    @app.get("/api/auth/session")
    def auth_session() -> object:
        user = get_current_user()
        return jsonify({"authenticated": bool(user), "user": serialize_profile_user(user) if user else None})

    @app.post("/api/auth/register")
    def register() -> object:
        payload = request.get_json(silent=True) or {}
        full_name = str(payload.get("full_name", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", "")).strip()
        city = str(payload.get("city", "Delhi")).strip() or "Delhi"

        if not full_name:
            return jsonify({"error": "Full name is required."}), 400
        if not email or "@" not in email:
            return jsonify({"error": "A valid email is required."}), 400
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters."}), 400
        if get_user_by_email(email):
            return jsonify({"error": "An account with this email already exists."}), 409

        user = create_user(
            full_name=full_name,
            email=email,
            password_hash=generate_password_hash(password),
            city=city,
        )
        session.clear()
        session["user_id"] = user["id"]
        session["chat_session_id"] = f"user-{user['id']}"
        return jsonify({"message": "Account created successfully.", "user": serialize_profile_user(user)}), 201

    @app.post("/api/auth/login")
    def login() -> object:
        payload = request.get_json(silent=True) or {}
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", "")).strip()

        if not email or not password:
            return jsonify({"error": "Email and password are required."}), 400

        auth_record = get_user_auth_record(email)
        if auth_record is None or not check_password_hash(auth_record["password_hash"], password):
            return jsonify({"error": "Invalid email or password."}), 401

        user = get_user_by_id(int(auth_record["id"]))
        if user is None:
            return jsonify({"error": "User account could not be loaded."}), 404

        session.clear()
        session["user_id"] = user["id"]
        session["chat_session_id"] = f"user-{user['id']}"
        return jsonify({"message": "Login successful.", "user": serialize_profile_user(user)})

    @app.post("/api/auth/logout")
    def logout() -> object:
        session.clear()
        return jsonify({"message": "Logged out successfully."})

    @app.get("/api/profile")
    def profile() -> object:
        user = get_current_user()
        if not user:
            return auth_error_response()
        return jsonify({"user": serialize_profile_user(user)})

    @app.put("/api/profile")
    def update_profile() -> object:
        user = get_current_user()
        if not user:
            return auth_error_response()

        payload = request.get_json(silent=True) or {}
        full_name = str(payload.get("full_name", "")).strip()
        city = str(payload.get("city", "")).strip() or str(user.get("city", "Delhi"))

        if not full_name:
            return jsonify({"error": "Full name is required."}), 400

        updated = update_user_profile(
            int(user["id"]),
            full_name=full_name,
            age=parse_optional_int(payload.get("age")),
            gender=str(payload.get("gender", "")).strip(),
            city=city,
            phone=str(payload.get("phone", "")).strip(),
            medical_conditions=str(payload.get("medical_conditions", "")).strip(),
            bio=str(payload.get("bio", "")).strip(),
        )

        if updated is None:
            return jsonify({"error": "Profile could not be updated."}), 404

        return jsonify({"message": "Profile updated successfully.", "user": serialize_profile_user(updated)})

    @app.get("/api/dashboard")
    def dashboard() -> object:
        user = get_current_user()
        if not user:
            return auth_error_response()

        language = detect_language("", request.args.get("language"))
        city = request.args.get("city", str(user.get("city", "Delhi")) or "Delhi")
        return jsonify(
            {
                "user": serialize_profile_user(user),
                "tip": pick_tip(language),
                "hospitals": get_hospital_suggestions(city),
                "hospital_note": format_hospital_note(city, language),
                "reminders": fetch_reminders(int(user["id"])),
                "stats": get_user_dashboard_stats(int(user["id"])),
                "supported_cities": list(HOSPITALS_BY_CITY.keys()),
            }
        )

    @app.get("/api/chat/history")
    def chat_history() -> object:
        user = get_current_user()
        if not user:
            return auth_error_response()

        session_id = get_or_create_chat_session_id(int(user["id"]))
        history = get_chat_history(user_id=int(user["id"]), session_id=session_id)
        return jsonify({"session_id": session_id, "messages": history})

    @app.post("/api/chat")
    def chat() -> object:
        user = get_current_user()
        if not user:
            return auth_error_response()

        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        session_id = get_or_create_chat_session_id(int(user["id"]))
        city = str(payload.get("city", user.get("city", "Delhi"))).strip() or str(user.get("city", "Delhi"))
        language = detect_language(message, str(payload.get("language", "")).strip() or None)

        if not message:
            return jsonify({"error": translate("message_required", language)}), 400

        save_chat_message(int(user["id"]), session_id, "user", message)
        response_payload = build_chat_response(message, language, city, session_id)
        save_chat_message(int(user["id"]), session_id, "assistant", str(response_payload["response"]))
        return jsonify(response_payload)

    @app.post("/api/chat/medicine-image")
    def analyze_medicine_photo() -> object:
        user = get_current_user()
        if not user:
            return auth_error_response()

        image_file = request.files.get("image")
        language = detect_language("", str(request.form.get("language", "")).strip() or None)
        city = str(request.form.get("city", user.get("city", "Delhi"))).strip() or str(user.get("city", "Delhi"))

        if image_file is None or not image_file.filename:
            return jsonify({"error": translate("medicine_image_missing", language)}), 400

        mime_type = guess_image_mime_type(image_file.filename, image_file.mimetype)
        if not is_allowed_medicine_image(image_file.filename, mime_type):
            return jsonify({"error": translate("medicine_image_invalid", language)}), 400

        image_bytes = image_file.read()
        if not image_bytes:
            return jsonify({"error": translate("medicine_image_missing", language)}), 400
        if len(image_bytes) > MAX_MEDICINE_IMAGE_BYTES:
            return jsonify({"error": translate("medicine_image_too_large", language)}), 400

        session_id = get_or_create_chat_session_id(int(user["id"]))
        fallback = build_medicine_image_fallback(language)
        analysis = analyze_medicine_image(
            image_bytes=image_bytes,
            filename=image_file.filename,
            mime_type=mime_type,
            language=language,
        ) or fallback

        save_chat_message(
            int(user["id"]),
            session_id,
            "user",
            f"[Medicine photo uploaded: {image_file.filename}]",
        )
        save_chat_message(int(user["id"]), session_id, "assistant", str(analysis["response"]))

        hospitals = get_hospital_suggestions(city)
        return jsonify(
            {
                "response": analysis["response"],
                "language": language,
                "emergency": False,
                "triggers": [],
                "response_source": "groq_vision" if analysis is not fallback else "local_unavailable",
                "doctor": DOCTOR_LABELS["general_physician"][language],
                "severity": "info",
                "possible_causes": "",
                "hospitals": hospitals,
                "medicine_analysis": analysis["medicine_analysis"],
                "disclaimer": DISCLAIMER[language],
                "follow_up": analysis["medicine_analysis"].get("doctor_advice", ""),
                "filename": image_file.filename,
            }
        )

    @app.post("/api/emergency-check")
    def emergency_check() -> object:
        if not get_current_user():
            return auth_error_response()

        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        language = detect_language(message, str(payload.get("language", "")).strip() or None)

        if not message:
            return jsonify({"error": translate("message_required", language)}), 400

        return jsonify(detect_emergency(message, language))

    @app.post("/api/bmi")
    def bmi() -> object:
        if not get_current_user():
            return auth_error_response()

        payload = request.get_json(silent=True) or {}
        language = detect_language("", str(payload.get("language", "")).strip() or None)
        height_cm = parse_float(payload.get("height"))
        weight_kg = parse_float(payload.get("weight"))

        if not height_cm or not weight_kg or height_cm <= 0 or weight_kg <= 0:
            return jsonify({"error": translate("invalid_bmi", language)}), 400

        return jsonify(calculate_bmi_result(height_cm, weight_kg, language))

    @app.get("/api/tips")
    def tips() -> object:
        if not get_current_user():
            return auth_error_response()

        language = detect_language("", request.args.get("language"))
        return jsonify(pick_tip(language))

    @app.get("/api/hospitals")
    def hospitals() -> object:
        user = get_current_user()
        if not user:
            return auth_error_response()

        city = str(request.args.get("city", "Delhi")).strip() or "Delhi"
        specialty = str(request.args.get("specialty", "")).strip() or None
        language = detect_language("", request.args.get("language"))
        return jsonify(
            {
                "city": city,
                "hospitals": get_hospital_suggestions(city, specialty),
                "note": format_hospital_note(city, language),
            }
        )

    @app.get("/api/reminders")
    def reminders() -> object:
        user = get_current_user()
        if not user:
            return auth_error_response()
        return jsonify({"reminders": fetch_reminders(int(user["id"]))})

    @app.post("/api/reminders")
    def create_reminder() -> object:
        user = get_current_user()
        if not user:
            return auth_error_response()

        payload = request.get_json(silent=True) or {}
        language = detect_language("", str(payload.get("language", "")).strip() or None)
        medicine_name = str(payload.get("medicine_name", "")).strip()
        reminder_time = str(payload.get("time", "")).strip()
        notes = str(payload.get("notes", "")).strip()

        if not medicine_name:
            return jsonify({"error": translate("reminder_name_required", language)}), 400
        if not reminder_time:
            return jsonify({"error": translate("reminder_time_required", language)}), 400

        try:
            normalized_time = datetime.fromisoformat(reminder_time).isoformat(timespec="minutes")
        except ValueError:
            return jsonify({"error": translate("reminder_time_invalid", language)}), 400

        reminder_id = add_reminder(int(user["id"]), medicine_name, normalized_time, notes)
        reminder = {
            "id": reminder_id,
            "medicine_name": medicine_name,
            "time": normalized_time,
            "notes": notes,
            "is_completed": False,
        }
        return jsonify({"message": translate("reminder_saved", language), "reminder": reminder}), 201

    @app.post("/api/reminders/<int:reminder_id>/complete")
    def complete_reminder(reminder_id: int) -> object:
        user = get_current_user()
        if not user:
            return auth_error_response()

        language = detect_language("", request.args.get("language"))
        reminder = update_reminder_status(int(user["id"]), reminder_id, True)

        if reminder is None:
            return jsonify({"error": translate("reminder_missing", language)}), 404

        reminder["medicine_name"] = reminder["title"]
        reminder["time"] = reminder["reminder_time"]
        return jsonify({"message": translate("reminder_completed", language), "reminder": reminder})

    @app.delete("/api/reminders/<int:reminder_id>")
    def remove_reminder(reminder_id: int) -> object:
        user = get_current_user()
        if not user:
            return auth_error_response()

        language = detect_language("", request.args.get("language"))
        deleted = delete_reminder(int(user["id"]), reminder_id)

        if not deleted:
            return jsonify({"error": translate("reminder_missing", language)}), 404

        return jsonify({"message": translate("reminder_deleted", language)})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5001")),
        debug=os.getenv("FLASK_DEBUG", "true").lower() == "true",
    )
