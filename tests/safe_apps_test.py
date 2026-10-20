"""Safe app registry tests; no real desktop application is launched."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))
import action_engine
from action_engine import ActionEngine
from safe_apps import get_safe_app
sys.path.insert(0, str(ROOT / "lumen-core"))
from action_intent import detect_action

with tempfile.TemporaryDirectory(prefix="gaia_safe_apps_") as tmp:
    engine = ActionEngine(Path(tmp))
    launched: list[list[str]] = []
    engine._spawn = lambda command, cwd=None: launched.append(list(command))  # type: ignore[method-assign]
    original_system = action_engine.platform.system
    original_resolver = action_engine.resolve_windows_executable
    action_engine.platform.system = lambda: "Windows"

    def fake_resolver(app):
        if app.canonical_name == "spotify" and getattr(fake_resolver, "missing", False):
            return None
        return {"calculator": r"C:\\Windows\\System32\\calc.exe", "notepad": r"C:\\Windows\\System32\\notepad.exe", "spotify": r"C:\\Spotify\\Spotify.exe", "vscode": r"C:\\VSCode\\Code.exe"}[app.canonical_name]

    action_engine.resolve_windows_executable = fake_resolver
    try:
        assert set(("open_calculator", "open_notepad", "open_spotify", "open_vscode_new_window")) <= set(ActionEngine.SAFE_ACTIONS)
        assert get_safe_app("calculator") and get_safe_app("notepad") and get_safe_app("spotify") and get_safe_app("vscode")
        assert detect_action("Gaia, abre la calculadora").name == "open_calculator"
        assert detect_action("Gaia, abre el bloc de notas").name == "open_notepad"
        assert detect_action("Gaia, abre Spotify").name == "open_spotify"
        assert detect_action("Gaia, abre una nueva ventana de VS Code").name == "open_vscode_new_window"
        assert detect_action("Gaia, abre VS Code").name == "open_vscode"
        calc = engine.execute({"name": "open_calculator", "args": {}})
        note = engine.execute({"name": "open_notepad", "args": {}})
        spotify = engine.execute({"name": "open_spotify", "args": {}})
        new_window = engine.execute({"name": "open_vscode_new_window", "args": {}})
        assert calc.success and note.success and spotify.success and new_window.success
        assert launched[0] == [r"C:\\Windows\\System32\\calc.exe"]
        assert launched[1] == [r"C:\\Windows\\System32\\notepad.exe"]
        assert launched[2] == [r"C:\\Spotify\\Spotify.exe"]
        assert launched[3] == [r"C:\\VSCode\\Code.exe", "--new-window"]

        fake_resolver.missing = True
        unavailable = engine.execute({"name": "open_spotify", "args": {}})
        assert not unavailable.success and unavailable.data["installed"] is False
        assert len(launched) == 4
    finally:
        action_engine.platform.system = original_system
        action_engine.resolve_windows_executable = original_resolver

print("SAFE APPS TEST OK: registry, Windows launch strategies, Spotify missing and VS Code new-window args.")
