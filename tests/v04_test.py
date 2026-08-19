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

with tempfile.TemporaryDirectory(prefix="gaia_v04_test_") as tmp:
    data_dir = Path(tmp) / "data"
    project_dir = Path(tmp) / "project"
    project_dir.mkdir()
    os.environ.update({
        "LUMEN_DATA_DIR": str(data_dir),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-secret-for-gaia-v04",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "LUMEN_AUTO_FACTS_ENABLED": "false",
        "GAIA_LLM_CONTEXT": "4096",
        "GAIA_MODEL_NORMAL": "qwen3.5:9b",
    })

    from fastapi.testclient import TestClient
    from action_engine import ActionEngine
    from action_intent import detect_action, parse_structured_intent
    from brain_backup import create_brain_backup, migrate_database, restore_brain_backup
    from main import app
    import llm
    import memory
    from model_router import profile_options, selection_for
    from project_registry import ProjectRegistry
    from context_providers import collect_context

    headers = {"Authorization": "Bearer test-secret-for-gaia-v04"}
    assert profile_options("fast")["num_predict"] < profile_options("reasoning")["num_predict"]
    assert selection_for("normal").selected_model == "qwen3.5:9b"
    natural = detect_action("Gaia, quiero programar un rato, abre VS Code")
    assert natural and natural.name == "open_vscode" and natural.args["app"] == "vscode"
    structured = parse_structured_intent({"type": "action", "action": "open_vscode", "args": {"app": "vscode"}, "confidence": 0.96})
    assert structured and structured.source == "structured"
    assert parse_structured_intent({"type": "action", "action": "shell", "args": {"command": "rm -rf /"}, "confidence": 1.0}) is None
    assert parse_structured_intent("{not valid json}") is None
    assert llm._visible_text("<think>sin cierre") == ""
    assert llm._visible_text("Texto normal sin thinking") == "Texto normal sin thinking"

    project_json = project_dir / "projects.json"
    project_json.write_text(json.dumps({"projects": [{"name": "demo", "aliases": ["prueba"], "path": str(project_dir), "trusted": True, "commands": {"tests": [sys.executable, "-m", "compileall", "-q", "."]}}]}), encoding="utf-8")
    registry = ProjectRegistry(project_json, project_dir)
    assert registry.resolve("prueba").name == "demo"
    engine = ActionEngine(project_dir=project_dir, projects_file=project_json)
    listed = engine.execute({"name": "list_projects", "args": {}})
    assert listed.success and "demo" in listed.message
    tested = engine.execute({"name": "run_project_command", "args": {"project": "demo", "command": "tests"}})
    assert tested.success
    untrusted_json = project_dir / "untrusted.json"
    untrusted_json.write_text(json.dumps({"projects": [{"name": "unknown", "path": str(project_dir), "trusted": False, "commands": {"tests": [sys.executable, "-m", "compileall", "-q", "."]}}]}), encoding="utf-8")
    untrusted_engine = ActionEngine(project_dir=project_dir, projects_file=untrusted_json)
    assert not untrusted_engine.execute({"name": "run_project_command", "args": {"project": "unknown", "command": "tests"}}).success
    assert not engine.execute({"name": "stop_gaia_process", "args": {"pid": "999999"}}).success
    context = collect_context(project_dir)
    assert context["platform"] and "network" in context

    memory.init_db()
    memory.save_message("session-v04", "user", "hola", "test")
    memory.save_fact("preferencia", "pruebas v0.4", source="manual", confidence=1.0)
    archive = Path(create_brain_backup(Path(tmp) / "archives"))
    assert archive.exists()
    migrated = Path(tmp) / "migrated.db"
    dry = migrate_database(data_dir / "lumen_memory.db", migrated, dry_run=True)
    assert dry["would_copy"] is True and not migrated.exists()
    actual = migrate_database(data_dir / "lumen_memory.db", migrated)
    assert actual["destination_integrity"] == "ok" and migrated.exists()

    with TestClient(app) as client:
        structured_response = client.post("/api/chat", headers=headers, json={"message": "quiero programar", "device": "test", "intent": {"type": "action", "action": "open_vscode", "args": {"app": "vscode"}, "confidence": 0.96}})
        assert structured_response.status_code == 200 and structured_response.json()["kind"] == "action"
        assert structured_response.json()["confirmation_required"] is True
        action_data = structured_response.json()
        completed = client.post("/api/actions/complete", headers=headers, json={"action_id": action_data["action_id"], "session_id": action_data["session_id"], "device": "test", "success": True, "message": "VS Code abierto.", "data": {"path": str(project_dir)}})
        assert completed.status_code == 200 and completed.json()["generated_by_llm"] is True
        history = client.get("/api/actions/history", headers=headers)
        assert history.status_code == 200 and history.json()
        vault = client.get("/api/vault/status", headers=headers)
        assert vault.status_code == 200 and vault.json()["status"] in {"configured", "fallback_local", "missing_fallback"}
        registered = client.post("/api/devices/register", headers=headers, json={"device_id": "android_principal", "capabilities": ["chat", "tts"], "permission_level": 0})
        assert registered.status_code == 200
        devices = client.get("/api/devices", headers=headers)
        assert devices.status_code == 200 and any(item["device_id"] == "android_principal" for item in devices.json())
        revoked = client.post("/api/devices/android_principal/revoke", headers=headers)
        assert revoked.status_code == 200
        cancelled = client.post("/api/assistant/cancel", headers=headers, json={"request_id": "a" * 32})
        assert cancelled.status_code == 404

    restore_result = restore_brain_backup(archive)
    assert restore_result["integrity"] == "ok"

print("V04 TEST OK: routing, structured intents, projects, context, backup, migration, restore, post-action and cancellation.")
