from __future__ import annotations

import logging
import re
from datetime import datetime

import memory
from config import AUTO_FACTS_ENABLED, AUTO_MEMORY_ENABLED

logger = logging.getLogger("lumen.facts")

# Solo afirmaciones explícitas y cortas. El contenido nunca se ejecuta.
_PATTERNS: list[tuple[str, str, str, re.Pattern[str], float]] = [
    ("identity", "user_name", "USER_EXPLICIT", re.compile(r"(?:me llamo|mi nombre es|llámame)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})", re.IGNORECASE), 0.98),
    ("preference", "likes", "USER_EXPLICIT", re.compile(r"me (?:gusta|encanta)\s+([^.,;!?\n]{3,80})", re.IGNORECASE), 0.92),
    ("technical_setup", "study_or_work", "USER_EXPLICIT", re.compile(r"(?:estudio|estoy estudiando|trabajo en)\s+([^.,;!?\n]{3,100})", re.IGNORECASE), 0.88),
    ("technical_setup", "hardware", "USER_EXPLICIT", re.compile(r"(?:mi|tengo una?)\s+((?:rtx|gtx|gpu|cpu|laptop|portátil)[^.,;!?\n]{0,80})", re.IGNORECASE), 0.86),
    ("routine", "routine", "USER_EXPLICIT", re.compile(r"(?:normalmente|cada día|suelo)\s+([^.,;!?\n]{3,100})", re.IGNORECASE), 0.84),
]
_MOOD_PATTERNS = [
    (re.compile(r"(?:estoy|me siento)\s+(?:muy\s+)?(?:triste|mal|deprimido|bajón)", re.IGNORECASE), "triste"),
    (re.compile(r"(?:estoy|me siento)\s+(?:muy\s+)?(?:estresado|presionado|abrumado)", re.IGNORECASE), "estresado"),
]
_TASK_PATTERN = re.compile(r"(?:luego|después|tenemos que|hay que|pendiente(?:\s+de)?)\s+([^.!?\n]{3,180})", re.IGNORECASE)
_PROJECT_NOTE_PATTERN = re.compile(r"(?:recuerda que|apunta que|para el proyecto)\s+([^.!?\n]{3,220})", re.IGNORECASE)


def _clean(value: str, maximum: int = 400) -> str:
    return re.sub(r"\s+", " ", value.strip().strip(".,;:!?"))[:maximum]


def extract_memory_candidates(text: str) -> list[dict]:
    candidates: list[dict] = []
    for category, key, source, pattern, confidence in _PATTERNS:
        for match in pattern.finditer(text):
            value = _clean(match.group(1))
            if len(value) >= 2:
                candidates.append({"category": category, "key": key, "value": value, "confidence": confidence, "source": source, "policy": "persist"})
    for match in _TASK_PATTERN.finditer(text):
        task = _clean(match.group(1), 500)
        if task and not task.lower().startswith(("que", "si")):
            candidates.append({"category": "temporary", "key": "open_task", "value": task, "confidence": 0.9, "source": "USER_EXPLICIT", "policy": "open_task"})
    for match in _PROJECT_NOTE_PATTERN.finditer(text):
        note = _clean(match.group(1), 500)
        candidates.append({"category": "project", "key": "project_note", "value": note, "confidence": 0.88, "source": "USER_EXPLICIT", "policy": "project_note"})
    return candidates[:12]


def extract_facts(text: str) -> list[dict]:
    return [{"category": item["category"], "fact": f"{item['key']}: {item['value']}", "confidence": item["confidence"], "source": item["source"]} for item in extract_memory_candidates(text) if item["policy"] == "persist"]


def detect_mood(text: str) -> str | None:
    for pattern, mood in _MOOD_PATTERNS:
        if pattern.search(text):
            return mood
    return None


def process_message(text: str, session_id: str = "") -> dict:
    """Extrae candidatos seguros; no persiste temporales y respeta la política explícita."""
    result: dict = {"enabled": AUTO_MEMORY_ENABLED, "facts_found": [], "candidates": [], "mood": None, "facts_saved": 0, "tasks_saved": 0, "notes_saved": 0}
    if not AUTO_MEMORY_ENABLED:
        return result
    candidates = extract_memory_candidates(text)
    result["candidates"] = candidates
    for candidate in candidates:
        if candidate["policy"] == "persist":
            fact_id = memory.save_fact(candidate["category"], f"{candidate['key']}: {candidate['value']}", source=candidate["source"], confidence=candidate["confidence"], key=candidate["key"])
            result["facts_found"].append({**candidate, "id": fact_id})
            result["facts_saved"] += 1
        elif candidate["policy"] == "open_task":
            memory.save_open_task(candidate["value"], session_id)
            result["tasks_saved"] += 1
        elif candidate["policy"] == "project_note":
            active_project = memory.get_active_project()
            if active_project:
                memory.save_project_note(active_project, candidate["value"], note_key="general", source=candidate["source"])
                result["notes_saved"] += 1
    mood = detect_mood(text)
    if mood:
        result["mood"] = mood
        memory.set_state("user_mood", mood)
        memory.set_state("user_mood_time", datetime.now().isoformat())
    # Mantiene el indicador legacy para instalaciones v0.4.x.
    result["legacy_auto_facts"] = AUTO_FACTS_ENABLED
    return result


def get_user_profile() -> dict:
    profile: dict[str, list[str]] = {}
    for fact in memory.get_facts():
        profile.setdefault(fact["category"], []).append(fact["fact"])
    return profile
