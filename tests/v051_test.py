"""Suite agregada de contratos GAIA-AI v0.5.3.

Las pruebas físicas de micrófono, GPU, Ollama, Flutter/APK y LAN real se
reportan por separado como pendientes; aquí solo se comprueban contratos
automatizables o revisión estática.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "lumen-core"
sys.path.insert(0, str(CORE))

with tempfile.TemporaryDirectory(prefix="gaia_v051_contracts_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "v051-contract-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_AUTO_MEMORY_ENABLED": "false",
    })
    import memory
    from action_intent import ActionPlan, parse_action_plan
    from authz import Principal
    from config import VERSION, LAN_ENABLED

    assert VERSION == "0.5.3-pc"
    assert LAN_ENABLED is False
    memory.init_db()
    assert memory.get_admin_audit(10) == []
    memory.record_admin_audit("master", None, "test", "v051", "success", {"safe": True})
    audit = memory.get_admin_audit(10)
    assert audit[0]["principal_type"] == "master" and audit[0]["details"] == {"safe": True}

    valid_plan = parse_action_plan({
        "type": "plan",
        "actions": [
            {"action": "open_vscode", "args": {}},
            {"action": "system_status", "args": {}},
        ],
        "confidence": 0.91,
        "source": "llm",
    }, source="llm")
    assert isinstance(valid_plan, ActionPlan) and len(valid_plan.actions) == 2
    invalid_plan = parse_action_plan({
        "type": "plan",
        "actions": [{"action": "open_vscode", "args": {}}, {"action": "shutdown", "args": {}}],
        "confidence": 0.99,
        "source": "llm",
    }, source="llm")
    assert invalid_plan is None

    android_service = (ROOT / "lumen-mobile/lib/services/lumen_service.dart").read_text(encoding="utf-8")
    pubspec = (ROOT / "lumen-mobile/pubspec.yaml").read_text(encoding="utf-8")
    assert "this.secret = ''," in android_service
    assert "lumen-dev-key" not in android_service
    assert "flutter_secure_storage:" in pubspec
    assert "version: 0.5.3+9" in pubspec

    doctor_before = sorted(str(path.relative_to(ROOT)) for path in ROOT.rglob("*"))
    result = subprocess.run([sys.executable, str(ROOT / "tools/gaia_doctor.py"), "--json"], capture_output=True, text=True, check=True)
    payload = json.loads(result.stdout)
    assert payload["read_only"] is True
    doctor_after = sorted(str(path.relative_to(ROOT)) for path in ROOT.rglob("*"))
    assert doctor_before == doctor_after

print("V052 TEST OK: version, LAN opt-in, audit, plan atomics, Android static y Doctor read-only.")
