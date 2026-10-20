from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

from action_engine import ActionEngine, ExecutionResult
from action_host import ActionHost


def main() -> None:
    unavailable = ExecutionResult(True, "screen_capture_display", "backend ausente", {"available": False})
    assert unavailable.status == "UNAVAILABLE"
    assert unavailable.success is False
    assert unavailable.capability_available is False
    assert unavailable.execution_verified is False
    assert unavailable.effect_verified is False

    observation = ExecutionResult(True, "system_status", "estado observado", {"available": True})
    assert observation.status == "SUCCESS"
    assert observation.success is True
    assert observation.observation_completed is True
    assert observation.execution_verified is True
    assert observation.effect_verified is False
    assert observation.side_effect_performed is False

    mutation = ExecutionResult(True, "open_notepad", "efecto confirmado", {"verified": True})
    assert mutation.status == "SUCCESS"
    assert mutation.side_effect_performed is True
    assert mutation.effect_verified is True
    assert mutation.execution_verified is True

    dry_run = ExecutionResult(True, "open_notepad", "validada sin ejecutar", {"dry_run": True}, status="SUCCESS", execution_attempted=False)
    assert dry_run.success is True
    assert dry_run.execution_verified is False
    assert dry_run.side_effect_performed is False
    assert dry_run.effect_verified is False

    with tempfile.TemporaryDirectory(prefix="gaia_result_semantics_") as tmp:
        engine = ActionEngine(project_dir=Path(tmp), projects_file=Path(tmp) / "projects.json")
        context = engine.execute_capability(__import__("capabilities").CapabilityRequest("desktop.context", {"force_refresh": True}))
        if context.data.get("available") is False:
            assert context.status == "UNAVAILABLE"
            assert context.execution_verified is False
        host = ActionHost(Path(tmp), policy="CONFIRM_EXECUTION")
        response = {
            "kind": "action",
            "type": "action",
            "action_id": "semantics-action",
            "session_id": "semantics-session",
            "action": {"name": "screen_capture_display", "args": {"display_id": "primary"}, "risk_level": 1},
            "confirmation_required": False,
        }
        result = host.execute(response, confirmed=True)
        if result.status == "UNAVAILABLE":
            assert result.success is False
            assert result.execution_verified is False
            assert result.capability_available is False

    core = ROOT / "lumen-core"
    sys.path.insert(0, str(core))
    with tempfile.TemporaryDirectory(prefix="gaia_result_core_") as tmp:
        os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory" / "lumen_memory.db"), "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "result-core-secret", "LUMEN_BACKUP_ENABLED": "false", "LUMEN_PROACTIVE_ENABLED": "false"})
        from routes.api import VerifiedActionResult, _fact_locked_base
        blocked = VerifiedActionResult({}, False, "Acción denegada por permisos.", {}, execution_verified=False, status="DENIED", capability_available=True)
        unavailable_core = VerifiedActionResult({}, False, "No hay backend.", {"capability_available": False}, execution_verified=False, status="UNAVAILABLE", capability_available=False)
        partial = VerifiedActionResult({}, False, "Plan detenido al primer fallo.", {}, execution_verified=False, status="PARTIAL")
        assert "denegada" in _fact_locked_base(blocked).casefold()
        assert "backend" in _fact_locked_base(unavailable_core).casefold()
        assert "detenido" in _fact_locked_base(partial).casefold()

    print("RESULT SEMANTICS V071 TEST OK: explicit statuses, unavailable is never success/verified, observations have no effect, and grounding is fact-locked.")


if __name__ == "__main__":
    main()
