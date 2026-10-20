from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
desktop_api = (ROOT / "lumen-pc" / "desktop_api.py").read_text(encoding="utf-8")
gui = (ROOT / "lumen-pc" / "gui.py").read_text(encoding="utf-8")

assert "ACTION_TO_CAPABILITY" not in desktop_api
assert "permission_entries" in desktop_api
assert "El Core no entregó permission_entries autoritativas" in desktop_api
permission_dialog = gui.split("def _permission_dialog", 1)[1].split("def _cancel_generation", 1)[0]
assert "permission_entries" in permission_dialog
assert "human_scope_description" in permission_dialog
assert "args.get(\"source\")" not in permission_dialog
assert "args.get(\"destination\")" not in permission_dialog
assert "args.get(\"app\")" not in permission_dialog
assert "args.get(\"path\")" not in permission_dialog
assert "args.get(\"project\")" not in permission_dialog

print("CLIENT SCOPE DISPLAY V071 TEST OK: PC client consumes Core-owned permission_entries and GUI displays authoritative scope without local reconstruction.")
