"""Bounded desktop diagnostics intent. No program execution in this module."""
from __future__ import annotations
import re

_ACTION = re.compile(r"\b(?:diagnostic(?:a|ar|o|os)?|revis(?:a|ar|emos|ion)|comprueba|verifica|monitorea|inspecciona|analiza|check)\b", re.I)
_TARGET = re.compile(r"\b(?:pc|equipo|hardware|cpu|gpu|vram|ram|procesos|sistema|comfyui|rocm|amdhip|pytorch|red|network|internet|conexi[oó]n)\b", re.I)


def is_local_diagnostic_request(message: str) -> bool:
    """Only read-only diagnostics; reject requests to fix, delete or install."""
    clean = str(message).strip()[:500]
    if len(clean) < 8:
        return False
    if re.search(r"\b(?:borra|elimina|instala|desinstala|descarga|corrige|repara|modifica|formatea|apaga|reinicia|haz clic)\b", clean, re.I):
        return False
    return bool(_ACTION.search(clean) and _TARGET.search(clean))
