from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))
sys.path.insert(0, str(ROOT / "lumen-pc"))

from action_intent import ActionPlan, parse_action_plan
from workspace_profiles import detect_workspace_profile, resolve_window_referent
from action_coordinator import ActionCoordinator


def main() -> None:
    context = {
        "active_window": {
            "window_id": "123",
            "pid": 456,
            "title": "GAIA-AI — Visual Studio Code",
            "process": "Code.exe",
            "process_executable": r"C:\\Program Files\\Microsoft VS Code\\Code.exe",
        },
        "displays": [
            {"display_id": "display-2", "primary": False},
            {"display_id": "display-1", "primary": True},
        ],
    }
    plan = detect_workspace_profile("organiza mi espacio para programar", context)
    assert isinstance(plan, ActionPlan)
    assert plan.source == "workspace:programming"
    assert [item.name for item in plan.actions] == ["display_list", "vscode_focus", "vscode_open_project", "windows_move_to_display", "git_status"]
    move = plan.actions[3]
    assert move.args["window_id"] == "123" and move.args["display_id"] == "display-1"
    assert move.args["expected_target"]["pid"] == 456

    close = resolve_window_referent("ciérralo", context)
    assert close and close.name == "windows_close" and close.args["window_id"] == "123"
    context["active_window"]["window_id"] = "999"
    assert close.args["window_id"] == "123", "el referent se debe congelar al crear la acción"
    assert close.args["expected_target"]["pid"] == 456
    assert resolve_window_referent("minimízalo", context).args["window_id"] == "999"
    assert resolve_window_referent("muévelo a la pantalla principal", context).args["display_id"] == "display-1"
    assert resolve_window_referent("muévelo", context) is None

    raw = {"type": "plan", "actions": [{"action": "media_status", "args": {}} for _ in range(5)], "confidence": 0.95}
    parsed = parse_action_plan(raw, max_actions=5, max_risk=2)
    assert isinstance(parsed, ActionPlan) and len(parsed.actions) == 5
    assert ActionCoordinator.MAX_STEPS >= 5
    print("V070 WORKSPACE PLAN TEST OK: bounded programming profile, request-time referents, frozen target identity and five-step coordinator ceiling.")


if __name__ == "__main__":
    main()
