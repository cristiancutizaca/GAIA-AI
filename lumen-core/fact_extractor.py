"""Extracción básica de facts. En v0.2 está desactivada por defecto."""
from __future__ import annotations
import re
import logging
from datetime import datetime
import memory
from config import AUTO_FACTS_ENABLED

logger = logging.getLogger("lumen.facts")
PATTERNS: list[tuple[str, str, re.Pattern]] = []


def _p(category: str, label: str, pattern: str) -> None:
    PATTERNS.append((category, label, re.compile(pattern, re.IGNORECASE)))

# Solo afirmaciones relativamente explícitas. La memoria manual desde GUI es la opción estable.
_p("nombre", "{0}", r"(?:me llamo|mi nombre es|llámame)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})")
_p("edad", "Tiene {0} años", r"tengo\s+(\d{1,2})\s+años")
_p("estudio", "Estudia {0}", r"(?:estudio|estoy estudiando)\s+([\wáéíóúñ\s]{3,40}?)(?:\.|,|$)")
_p("gustos", "Le gusta {0}", r"me (?:gusta|encanta)\s+([\wáéíóúñ\s]{3,40}?)(?:\.|,|$)")

MOOD_PATTERNS = [
    (re.compile(r"(?:estoy|me siento)\s+(?:muy\s+)?(?:triste|mal|deprimido|bajón)", re.IGNORECASE), "triste"),
    (re.compile(r"(?:estoy|me siento)\s+(?:muy\s+)?(?:estresado|presionado|abrumado)", re.IGNORECASE), "estresado"),
]


def extract_facts(text: str) -> list[dict]:
    extracted: list[dict] = []
    for category, template, pattern in PATTERNS:
        for match in pattern.findall(text):
            clean = match.strip().rstrip(".,;:!?")
            if len(clean) >= 2:
                extracted.append({"category": category, "fact": template.format(clean)})
    return extracted


def detect_mood(text: str) -> str | None:
    for pattern, mood in MOOD_PATTERNS:
        if pattern.search(text):
            return mood
    return None


def process_message(text: str) -> dict:
    """Extrae solo cuando el usuario activa LUMEN_AUTO_FACTS_ENABLED=true."""
    result: dict = {"enabled": AUTO_FACTS_ENABLED, "facts_found": [], "mood": None, "facts_saved": 0}
    if not AUTO_FACTS_ENABLED:
        return result
    facts = extract_facts(text)
    for fact in facts:
        memory.save_fact(fact["category"], fact["fact"], source="auto_extract", confidence=0.6)
        result["facts_saved"] += 1
    result["facts_found"] = facts
    mood = detect_mood(text)
    if mood:
        result["mood"] = mood
        memory.set_state("user_mood", mood)
        memory.set_state("user_mood_time", datetime.now().isoformat())
    return result


def get_user_profile() -> dict:
    profile: dict[str, list[str]] = {}
    for fact in memory.get_facts():
        profile.setdefault(fact["category"], []).append(fact["fact"])
    return profile
