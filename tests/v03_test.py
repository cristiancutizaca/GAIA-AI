from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "lumen-core"
PC = ROOT / "lumen-pc"
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(PC))

with tempfile.TemporaryDirectory(prefix="gaia_v03_test_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-secret-for-gaia-v03",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "LUMEN_AUTO_FACTS_ENABLED": "false",
        "LUMEN_LLM_STREAM_ENABLED": "true",
        "LUMEN_LLM_HIDE_REASONING": "true",
    })

    from fastapi.testclient import TestClient
    from action_engine import ActionEngine
    from action_intent import detect_action
    from main import app
    import llm

    headers = {"Authorization": "Bearer test-secret-for-gaia-v03"}

    vscode = detect_action("Gaia, abre VS Code")
    assert vscode and vscode.name == "open_vscode" and vscode.risk_level == 1
    status = detect_action("Gaia, dime cómo está mi PC")
    assert status and status.name == "system_status"
    assert detect_action("cómo está mi PC") and detect_action("cómo está mi PC").name == "system_status"
    assert detect_action("abre https://example.com").name == "open_url"
    assert detect_action("borra todos mis archivos") is None

    assert llm._visible_text("<think>secreto interno</think>Respuesta visible") == "Respuesta visible"
    filterer = llm._ReasoningFilter()
    split_visible = filterer.feed("<thi") + filterer.feed("nk>secreto") + filterer.feed("</thi") + filterer.feed("nk>Visible") + filterer.finish()
    assert split_visible == "Visible"
    engine = ActionEngine(project_dir=Path(tmp))
    assert not engine.execute({"name": "shell", "args": {}}).success
    pc_status = engine.execute({"name": "system_status", "args": {}})
    assert pc_status.success and "CPU" in pc_status.message

    with TestClient(app) as client:
        stream = client.post("/api/assistant/stream", headers=headers, json={"message": "hola GAIA", "device": "test"})
        assert stream.status_code == 200, stream.text
        assert "event: token" in stream.text and "event: done" in stream.text
        done_line = next(line for line in stream.text.splitlines() if line.startswith("data: ") and '"kind": "chat"' in line)
        done = json.loads(done_line[6:])
        assert done["session_id"]

        action = client.post("/api/chat", headers=headers, json={"message": "abre VS Code", "device": "test"})
        assert action.status_code == 200, action.text
        action_data = action.json()
        assert action_data["kind"] == "action" and action_data["action"]["name"] == "open_vscode"
        assert action_data["confirmation_required"] is True
        completed = client.post("/api/actions/complete", headers=headers, json={
            "action_id": action_data["action_id"], "session_id": action_data["session_id"], "device": "test",
            "success": False, "message": "No encuentro VS Code en PATH.", "data": {},
        })
        assert completed.status_code == 200, completed.text
        history = client.get(f"/api/memory/history/{action_data['session_id']}", headers=headers)
        assert history.status_code == 200 and len(history.json()) == 2

print("V03 TEST OK: SSE, razonamiento oculto, router seguro, acciones y memoria.")
