"""Reject recognizable credentials before automatic or conversational extraction."""
import re

_CREDENTIAL = re.compile(
    r"\bbearer\s+\S{8,}|\b(?:sk-[\w-]{16,}|gh[pousr]_[\w]{16,}|github_pat_[\w_]{16,})"
    r"|\b(?:contrase[ñn]a|password|passwd|pwd|api[_ -]?key|clave(?:\s+sol)?|token|secreto?|pin)"
    r"\s*(?:(?:\s+\w+){0,2}\s+es\s+|[:=]\s*)\S+",
    re.IGNORECASE,
)


def contains_credentials(text: str) -> bool:
    return bool(_CREDENTIAL.search(text))
