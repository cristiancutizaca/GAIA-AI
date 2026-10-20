"""Reproduce the six independent audit findings against the v0.9.0 baseline.

This is an evidence tool, not a regression test: it records the vulnerable
behavior observed before the v0.9.1 fixes. It uses only temporary data and
synthetic test markers.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_v091_repro_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-independent-v091-master-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_DEVICE_TOKENS_ENABLED": "true",
    })

    import advanced_memory
    import automation_engine
    import memory
    from authz import Principal, CAP_MEMORY_READ, CAP_MEMORY_WRITE
    from event_engine import Event
    from fastapi.testclient import TestClient
    from main import app
    from routes.api import _prepare_context

    memory.init_db()
    advanced_memory.init_db()
    results: dict[str, dict] = {}

    # Bug A: chat context calls retrieve without the current device_id.
    advanced_memory.save_item(
        memory_key="device.private.marker", kind="device_system", category="device",
        content="ANDROID-A-PRIVATE-METADATA dispositivo privado", source_type="SYSTEM",
        source_ref="device-system", device_id="android-a", user_confirmed=False,
    )
    prompt, _history = _prepare_context("session-b", "¿Qué recuerdas de mi dispositivo?", "android-b")
    results["A_device_prompt_leak"] = {
        "status": "CONFIRMED" if "ANDROID-A-PRIVATE-METADATA" in prompt else "NOT_REPRODUCED",
        "private_marker_in_prompt": "ANDROID-A-PRIVATE-METADATA" in prompt,
    }

    # Bug B: existence of a session is treated as ownership.
    memory.save_message("session-a", "user", "SESIÓN-A-CONTENIDO-PRIVADO", "android-a")
    with TestClient(app) as client:
        master = {"Authorization": "Bearer test-independent-v091-master-secret"}
        client.post("/api/devices/register", headers=master, json={"device_id": "android-b", "capabilities": ["memory_read", "memory_write"], "permission_level": 0})
        token_response = client.post("/api/devices/android-b/token", headers=master, json={"ttl_days": 2})
        token = token_response.json().get("token", "")
        response = client.post("/api/memory/advanced/consolidate", headers={"Authorization": "Bearer " + token}, json={"session_id": "session-a", "max_messages": 8})
    results["B_consolidation_ownership"] = {
        "status": "CONFIRMED" if response.status_code == 200 else "NOT_REPRODUCED",
        "http_status": response.status_code,
        "foreign_summary_returned": response.status_code == 200 and "SESIÓN-A-CONTENIDO-PRIVADO" in response.text,
    }

    # Bug C: contradiction selection ignores device/session namespace.
    first = advanced_memory.save_item(
        memory_key="device.host", kind="device_system", category="host",
        content="HOST-A", source_type="SYSTEM", source_ref="device-system",
        device_id="android-a", user_confirmed=True,
    )
    second = advanced_memory.save_item(
        memory_key="device.host", kind="device_system", category="host",
        content="HOST-B", source_type="SYSTEM", source_ref="device-system",
        device_id="android-b", user_confirmed=True,
    )
    history = advanced_memory.get_history(first["id"])
    results["C_device_namespace_collision"] = {
        "status": "CONFIRMED" if any(item.get("status") == "superseded" for item in history) else "NOT_REPRODUCED",
        "first_status": advanced_memory.get_item(first["id"], include_history=True).get("status"),
        "second_device": second.get("device_id"),
        "history_rows": len(history),
    }

    # Bug D: the baseline pattern contains backspace characters, not boundaries.
    blocked_event = bool(advanced_memory._BLOCKED_SOURCE_RE.search("event"))
    blocked_event_ref = bool(advanced_memory._BLOCKED_SOURCE_RE.search("event:123"))
    results["D_source_filter_regex"] = {
        "status": "CONFIRMED" if not blocked_event and not blocked_event_ref else "NOT_REPRODUCED",
        "event_blocked": blocked_event,
        "event_ref_blocked": blocked_event_ref,
    }

    # Bug E: items is truncated, but context_text is derived from all selected rows.
    for index in range(10):
        advanced_memory.save_item(
            memory_key=f"context.marker.{index}", kind="project", category="context",
            content=f"LAPTOP-PROJECT-CONTEXT-MARKER-{index}", source_type="PROJECT",
            source_ref="project:repro", project="repro", scope="project", user_confirmed=True,
        )
    retrieved = advanced_memory.retrieve("LAPTOP PROJECT CONTEXT", project="repro", limit=2, max_chars=12000)
    context_markers = [line for line in retrieved["context_text"].splitlines() if "LAPTOP-PROJECT-CONTEXT" in line]
    results["E_retrieval_context_limit"] = {
        "status": "CONFIRMED" if len(retrieved["items"]) == 2 and len(context_markers) > 2 else "NOT_REPRODUCED",
        "items_length": len(retrieved["items"]),
        "context_marker_lines": len(context_markers),
        "retrieval_ms": retrieved["retrieval_ms"],
    }

    # Bug F: default last_run=0 makes an early-uptime first event look cooled down.
    engine = automation_engine.AutomationEngine(mode="NOTIFY_ONLY")
    original_monotonic = automation_engine.time.monotonic
    automation_engine.time.monotonic = lambda: 10.0
    try:
        event = Event.create("ollama.offline", source="repro", device="pc-main")
        asyncio.run(engine._handle_match({"rule_id": "cold-boot-rule", "name": "Cold boot", "cooldown_seconds": 300, "owner_device": "pc-main"}, event))
    finally:
        automation_engine.time.monotonic = original_monotonic
    results["F_cold_boot_cooldown"] = {
        "status": "CONFIRMED" if "cold-boot-rule" not in engine._last_run else "NOT_REPRODUCED",
        "last_run_recorded": "cold-boot-rule" in engine._last_run,
        "metrics": engine.status(),
    }

    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
