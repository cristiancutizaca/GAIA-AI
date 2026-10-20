from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))
with tempfile.TemporaryDirectory(prefix="gaia_natural_routing_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory" / "lumen_memory.db"), "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "natural-routing-secret", "LUMEN_BACKUP_ENABLED": "false", "LUMEN_PROACTIVE_ENABLED": "false"})
    from action_intent import detect_action, detect_contextual_action
    from routes.api import _allowed_intent

    assert detect_action("pon pausa").name == "media_play_pause"
    assert detect_action("siguiente canción").name == "media_next"
    assert detect_action("canción anterior").name == "media_previous"

    context = {
        "active_window": {"window_id": "42", "pid": 7, "process": "Code.exe", "process_executable": "C:/Program Files/Microsoft VS Code/Code.exe", "title": "GAIA"},
        "displays": [{"display_id": "display-1", "primary": True}, {"display_id": "display-2", "primary": False}],
        "controls": [
            {"control_id": "uia:continue", "name": "Continuar", "automation_id": "continueButton", "control_type": "Button"},
            {"control_id": "uia:search", "name": "Búsqueda", "automation_id": "searchBox", "control_type": "Edit"},
        ],
    }
    capture_window = _allowed_intent("captura esta ventana", pc_context=context)
    assert capture_window and capture_window.name == "screen_capture_window"
    assert capture_window.args["window_id"] == "42"
    assert capture_window.args["expected_target"]["pid"] == 7

    capture_display = _allowed_intent("captura el monitor 2", pc_context=context)
    assert capture_display and capture_display.name == "screen_capture_display"
    assert capture_display.args["display_id"] == "display-2"

    inspect = _allowed_intent("qué hay en esta ventana", pc_context=context)
    assert inspect and inspect.name == "uia_inspect_window" and inspect.risk_level == 0

    invoke = _allowed_intent("pulsa continuar", pc_context=context)
    assert invoke and invoke.name == "uia_invoke_control" and invoke.args["control_id"] == "uia:continue"
    assert invoke.args["expected_target"]["window_id"] == "42"

    set_value = _allowed_intent("escribe hola en el campo búsqueda", pc_context=context)
    assert set_value and set_value.name == "uia_set_value" and set_value.args["control_id"] == "uia:search" and set_value.args["value"] == "hola"

    plan = _allowed_intent("organiza mi espacio para programar", pc_context=context)
    assert plan and getattr(plan, "actions", ()) and len(plan.actions) == 5

    assert detect_contextual_action("captura esta ventana", {}) is None
    assert _allowed_intent("captura esta ventana", pc_context={}) is None

print("NATURAL ROUTING V071 TEST OK: media, capture, UIA observation/invoke/set_value, workspace plan and no-context fail-closed routing.")
