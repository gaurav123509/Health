from __future__ import annotations

import random


HEALTH_TIPS = [
    "Drink water before you feel thirsty so hydration stays ahead of your day.",
    "A short walk after meals can support digestion, energy, and blood sugar balance.",
    "Try to keep a steady sleep window, even on weekends, to support recovery and mood.",
    "Build meals around protein, fiber, and colorful produce for steadier energy.",
    "If you sit for long stretches, stand up and move for a minute every hour.",
    "A simple health habit is pairing medicines or vitamins with the same daily routine cue.",
]


def get_tip() -> str:
    return random.choice(HEALTH_TIPS)
