from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_rc2_memory_security_") as tmp:
    tmp_path = Path(tmp)
    os.environ.update({
        "LUMEN_DATA_DIR": str(tmp_path),
        "GAIA_MEMORY_DB": str(tmp_path / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-rc2-memory-security-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_SAFE_MODE": "false",
    })
    import advanced_memory
    import memory

    ctx_a = memory.MemoryAccessContext(principal_id="token-a", device_id="device-a", capabilities=frozenset({"memory_read", "memory_write"}), source_channel="test")
    ctx_b = memory.MemoryAccessContext(principal_id="token-b", device_id="device-b", capabilities=frozenset({"memory_read", "memory_write"}), source_channel="test")
    assert memory.claim_session("session-a", device_id="device-a", principal_id="token-a")
    item_a = advanced_memory.save_item(memory_key="private.note", kind="semantic", category="note", content="Device A private context", source_type="USER_EXPLICIT", source_ref="user", device_id="device-a", access_context=ctx_a)
    item_b = advanced_memory.save_item(memory_key="private.note", kind="semantic", category="note", content="Device B private context", source_type="USER_EXPLICIT", source_ref="user", device_id="device-b", access_context=ctx_b)
    session_item = advanced_memory.save_item(memory_key="session.note", kind="session", category="note", content="Session A only", source_type="USER_EXPLICIT", source_ref="user", session_id="session-a", device_id="device-a", access_context=ctx_a)

    try:
        advanced_memory.get_item(item_a["id"], access_context=ctx_b)
    except PermissionError:
        pass
    else:
        raise AssertionError("cross-device get leaked memory")
    assert advanced_memory.get_item(item_a["id"], access_context=ctx_a)["id"] == item_a["id"]
    assert item_a["id"] not in {item["id"] for item in advanced_memory.list_items(access_context=ctx_b)}
    assert item_a["id"] not in {item["id"] for item in advanced_memory.retrieve("private context", device_id="device-b", access_context=ctx_b)["items"]}
    assert item_a["id"] not in {entry.get("memory_id") for entry in advanced_memory.audit(access_context=ctx_b)}
    try:
        advanced_memory.update_item(item_a["id"], access_context=ctx_b, content="attempted overwrite")
    except PermissionError:
        pass
    else:
        raise AssertionError("cross-device update leaked memory")
    try:
        advanced_memory.delete_item(item_a["id"], access_context=ctx_b)
    except PermissionError:
        pass
    else:
        raise AssertionError("cross-device delete leaked memory")
    try:
        advanced_memory.save_item(memory_key="blank.device", kind="semantic", category="note", content="legacy blank", source_type="USER_EXPLICIT", source_ref="user", device_id="", access_context=ctx_b)
    except PermissionError:
        pass
    else:
        raise AssertionError("device principal could write a blank namespace")
    assert session_item["id"] in {item["id"] for item in advanced_memory.list_items(session_id="session-a", access_context=ctx_a)}
    try:
        advanced_memory.list_items(session_id="session-a", access_context=ctx_b)
    except PermissionError:
        pass
    else:
        raise AssertionError("cross-device session listing was not denied")

    blocked_types = ("EVENT", "EVENT_RUN", "UIA_EVENT", "SCREENSHOT_OBSERVATION", "AUTOMATION_RULE", "CLIPBOARD_CAPTURE", "TEMPORARY_CONTEXT")
    for index, provenance_type in enumerate(blocked_types):
        try:
            advanced_memory.save_item(memory_key=f"blocked.type.{index}", kind="semantic", category="security", content="operational payload", source_type="SYSTEM", source_ref="safe-user-ref", provenance_type=provenance_type, access_context=ctx_a)
        except ValueError:
            pass
        else:
            raise AssertionError(f"operational provenance accepted: {provenance_type}")

    blocked_refs = ("event/run", "EVENT.RUN", "event-run", "uia.event", "screen_capture|1", "temporary context:1", "clipboard\\copy")
    for index, source_ref in enumerate(blocked_refs):
        try:
            advanced_memory.save_item(memory_key=f"blocked.ref.{index}", kind="semantic", category="security", content="operational payload", source_type="SYSTEM", source_ref=source_ref, device_id="device-a", access_context=ctx_a)
        except ValueError:
            pass
        else:
            raise AssertionError(f"operational source_ref accepted: {source_ref}")

print("RC2 MEMORY SECURITY TEST OK: namespace-aware CRUD/search/audit, blank-device fail-closed and canonical provenance blocks.")
