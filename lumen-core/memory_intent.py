"""Explicit memory intent recognized consistently before desktop shortcuts."""
import re

_MEMORY_PREFIX = r"^(?:gaia\b[\s,:]*|[¿?]\s*)*"
_MEMORY_WRITE = re.compile(_MEMORY_PREFIX + r"(?:recuerda|remember)\s+(?:(?:que|that)\s+)?(.+)", re.I | re.S)
_MEMORY_READ = re.compile(
    _MEMORY_PREFIX + r"(?:(?:qu[eé]\s+)?recuerdas|te acuerdas|what do you remember)"
    r"(?:\s+(?:de|sobre|about))?(?:\s+(.*?))?[?¿.\s]*$", re.I
)
_LEGACY_DATABASE_QUESTION = re.compile(
    _MEMORY_PREFIX + r"(?:qu[eé]\s+base de datos|what database)\b.*\b(?:proyecto|project)\b.*$", re.I
)
_MEMORY_PROJECT = re.compile(r"^proyecto\s+([\w.-]{1,80})\s*(?::\s*|\s+(?:sobre|de)\s+|$)(.*)$", re.I | re.S)


def parse_memory_intent(message: str) -> tuple[bool, str, str] | None:
    text = message.strip()
    write = _MEMORY_WRITE.fullmatch(text) if not text.endswith("?") else None
    read = _MEMORY_READ.fullmatch(text) if not write else None
    if not (write or read):
        return (False, text, "") if _LEGACY_DATABASE_QUESTION.fullmatch(text) else None
    query = ((write or read).group(1) or "").strip(" .:")
    project = _MEMORY_PROJECT.fullmatch(query)
    if project:
        return bool(write), project.group(2).strip(), project.group(1).casefold()
    return bool(write), query, ""
