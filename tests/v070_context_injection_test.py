from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

from routes.api import _context_is_relevant, _relevant_active_context


def main() -> None:
    context = {
        "active_window": {
            "process": "Code.exe",
            "process_executable": r"C:\\secret\\Code.exe",
            "pid": 4455,
            "title": "GAIA-AI — workspace",
        },
        "system": {"platform": "Windows"},
    }
    assert not _context_is_relevant("¿Cómo estás hoy?")
    assert _relevant_active_context("¿Cómo estás hoy?", context) is None
    assert _context_is_relevant("¿En qué app estoy?")
    active = _relevant_active_context("¿En qué app estoy?", context)
    assert active and active["ephemeral"] is True and active["read_only"] is True
    assert active["active_window"]["app"] == "Code.exe"
    assert "pid" not in active["active_window"] and "process_executable" not in active["active_window"]
    assert _relevant_active_context("minimiza la ventana", context)["active_window"]["title"] == "GAIA-AI — workspace"
    print("V070 CONTEXT INJECTION TEST OK: relevant-only active-app hint, read-only redaction and ephemeral response field.")


if __name__ == "__main__":
    main()
