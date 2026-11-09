"""Local, full-utterance rules that only propose allowlisted actions."""
from __future__ import annotations

import re
import unicodedata

from action_intent import ActionIntent, _context_window_snapshot


_RULES = {
    "abre el bloc de notas": ("open_notepad", {"app": "notepad"}, 1),
    "abre bloc de notas": ("open_notepad", {"app": "notepad"}, 1),
    "baja el volumen": ("volume_down", {}, 1),
    "baja volumen": ("volume_down", {}, 1),
    "pausa la musica": ("media_pause", {}, 1),
    "muestra el escritorio": ("desktop_show", {}, 1),
    "muestrame el escritorio": ("desktop_show", {}, 1),
    "abre kiroha": ("vscode_open_project", {"project": "kiroha"}, 1),
    "cuanta ram estoy usando": ("system_ram", {}, 1),
    "cuanta ram estoy utilizando": ("system_ram", {}, 1),
}


def _normalize(message: str) -> str:
    normalized = unicodedata.normalize("NFKD", message.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = " ".join(normalized.split()).strip("¿¡!? .")
    return re.sub(r"^gaia\b[\s,:]+", "", normalized).strip("¿¡!? .")


def requires_window_target(message: str) -> bool:
    return _normalize(message) == "cierra esta ventana"


def classify_reflex(message: str, context: dict | None = None) -> ActionIntent | None:
    normalized = _normalize(message)
    if normalized == "cierra esta ventana":
        desktop = (context or {}).get("desktop_snapshot")
        target = _context_window_snapshot(desktop if isinstance(desktop, dict) else context)
        if target and str(target[1].get("pid") or "").isdigit() and int(target[1]["pid"]) > 0:
            return ActionIntent("windows_close", {"window_id": target[0], "expected_target": target[1]},
                                2, confirmation_required=True, source="reflex")
        return None
    rule = _RULES.get(normalized)
    if rule:
        name, args, risk = rule
        return ActionIntent(name, dict(args), risk, source="reflex")
    return None
