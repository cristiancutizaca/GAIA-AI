from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

from uia import dynamic_control_risk
import action_engine as action_engine_module
from action_engine import ActionEngine


def check(name: str, control_type: str = "Button", sensitive: bool = False) -> dict:
    return dynamic_control_risk({"control_type": control_type, "name": name, "automation_id": "", "sensitive": sensitive}, "invoke")


def main() -> None:
    normal = check("Continuar")
    assert normal["risk_level"] == 2 and normal["requires_explicit_confirmation"] is False

    destructive = check("Delete account")
    assert destructive["risk_level"] == 3
    assert destructive["requires_explicit_confirmation"] is True
    assert destructive["reason"] == "destructive_label"

    critical = check("Pay now")
    assert critical["risk_level"] == 4
    assert critical["requires_explicit_confirmation"] is True
    assert critical["reason"] == "critical_label"

    sensitive = check("Password", control_type="Edit", sensitive=True)
    assert sensitive["risk_level"] == 4
    assert sensitive["sensitive"] is True
    assert sensitive["reason"] == "sensitive_control"

    assert dynamic_control_risk({"control_type": "Button", "name": "Enfocar", "sensitive": False}, "focus")["risk_level"] == 1
    assert dynamic_control_risk({"control_type": "Edit", "name": "Título", "sensitive": False}, "set_value")["risk_level"] == 2

    engine = ActionEngine(ROOT)
    engine._uia_interaction_target = lambda _args: ("42", {"window_id": "42", "process_executable": "Code.exe"})
    action_engine_module.resolve_control_risk = lambda _window, _control, _operation: {"risk_level": 3, "requires_explicit_confirmation": True, "sensitive": False, "reason": "destructive_label"}
    action_engine_module.invoke_control = lambda *_args: (_ for _ in ()).throw(AssertionError("no debe invocarse un control destructivo subdeclarado"))
    rejected = engine._uia_invoke_control({"control_id": "uia:delete", "_declared_risk": 2})
    assert rejected.status == "DENIED" and rejected.success is False and rejected.execution_verified is False
    print("DYNAMIC UIA RISK V071 TEST OK: normal/destructive/critical/sensitive labels receive bounded dynamic risk and explicit-confirmation metadata.")


if __name__ == "__main__":
    main()
