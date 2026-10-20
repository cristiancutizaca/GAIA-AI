from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

from capabilities import default_capability_registry
from platform_capabilities import _normalize_display_rows

raw = [
    {"display_id": "display-1", "name": "Primary", "primary": True, "rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080}},
    {"display_id": "display-2", "name": "Left", "primary": False, "rect": {"left": -1280, "top": 0, "right": 0, "bottom": 1024}},
    {"display_id": "display-3", "name": "Above", "primary": False, "rect": {"left": 0, "top": -1200, "right": 1920, "bottom": 0}},
]
rows = _normalize_display_rows(raw)
assert len(rows) == 3 and {row["display_id"] for row in rows} == {"display-1", "display-2", "display-3"}, rows
assert rows[1]["x"] == -1280 and rows[2]["y"] == -1200, rows
registry = default_capability_registry()
move = registry.get("windows.move_to_display")
assert move is not None and move.implemented and move.executor.endswith("_windows_move_to_display")
request = registry.request("windows.move_to_display", {"window_id": "123", "display_id": "display-2"})
assert request.capability == "windows.move_to_display"
try:
    registry.request("windows.move_to_display", {"window_id": "123"})
except ValueError:
    pass
else:
    raise AssertionError("display_id missing must fail closed")
print("DISPLAY CAPABILITY TEST OK: three-monitor normalization, negative coordinates, registry mapping and strict parameters.")
