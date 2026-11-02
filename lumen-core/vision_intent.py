"""Explicit user intent to read a screen; no image processing here."""
import re

_REQUEST = re.compile(
    r"\b(?:mira|observa|analiza|revisa|describe|lee|examina|ve|ver|look at|describe|analy[sz]e|check)\b.{0,75}"
    r"\b(?:mi|la|el|my|the)?\s*(?:pantalla|monitor|escritorio|screen|display|desktop)\b|"
    r"\b(?:qu[eé]\s+(?:hay|ves|aparece)|what(?:'s| is) on)\b.{0,55}\b(?:pantalla|monitor|escritorio|screen)\b",
    re.IGNORECASE,
)

def is_screen_vision_request(message: str) -> bool:
    return bool(_REQUEST.search(message.strip()[:500]))
