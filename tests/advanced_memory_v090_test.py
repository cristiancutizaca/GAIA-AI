"""v0.9.0: advanced memory is relevant, traceable, editable, deletable and bounded."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_memory_v090_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "advanced-memory-v090-test-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    import memory
    import advanced_memory

    assert memory.schema_version() == 9
    advanced_memory.init_db()
    with memory.get_db() as conn:
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"memory_items", "memory_item_history"} <= tables

    explicit = advanced_memory.save_item(
        memory_key="user.name", kind="semantic", category="nombre", content="Cris",
        source_type="USER_EXPLICIT", source_ref="chat:s1", provenance_type="USER_EXPLICIT",
        confidence=1.0, importance=0.9, scope="personal", session_id="s1", device_id="pc-main",
        user_confirmed=True, pinned=True,
    )
    duplicate = advanced_memory.save_item(
        memory_key="user.name", kind="semantic", category="nombre", content="Cris",
        source_type="USER_EXPLICIT", source_ref="chat:s1", confidence=0.8,
        scope="personal", session_id="s1", device_id="pc-main", user_confirmed=True,
    )
    assert duplicate["id"] == explicit["id"]

    replacement = advanced_memory.save_item(
        memory_key="user.name", kind="semantic", category="nombre", content="Alex",
        source_type="USER_EXPLICIT", source_ref="chat:s2", confidence=1.0,
        scope="personal", session_id="s2", device_id="pc-main", user_confirmed=True,
    )
    assert replacement["id"] != explicit["id"]
    assert replacement["status"] == "active"
    assert any(row["content"] == "Cris" and row["status"] == "superseded" for row in advanced_memory.get_history(replacement["id"]))
    assert advanced_memory.get_item(explicit["id"])["status"] == "superseded"

    project = advanced_memory.save_item(
        memory_key="gaia.architecture", kind="project", category="proyecto",
        content="GAIA usa un Event Engine y memoria con retrieval FTS bounded.",
        source_type="PROJECT", source_ref="project:GAIA-AI", provenance_type="PROJECT",
        confidence=0.95, importance=0.85, scope="project", project="GAIA-AI",
        device_id="pc-main", user_confirmed=True,
    )
    old_irrelevant = advanced_memory.save_item(
        memory_key="old.note", kind="episodic", category="nota",
        content="Una nota vieja sin relación sobre jardinería.", source_type="IMPORT",
        source_ref="import:notes", confidence=0.5, importance=0.2, scope="personal", device_id="pc-main",
        user_confirmed=False,
    )
    result = advanced_memory.retrieve("memoria retrieval GAIA", project="GAIA-AI", device_id="pc-main", limit=5, max_chars=1000)
    assert result["items"] and result["items"][0]["id"] == project["id"]
    assert len(result["context_text"]) <= 1000
    assert all(item["id"] != old_irrelevant["id"] for item in result["items"])
    assert all("retrieval_score" in item for item in result["items"])

    private = advanced_memory.save_item(
        memory_key="device.host", kind="device_system", category="host",
        content="Android host local metadata.", source_type="SYSTEM", source_ref="doctor",
        scope="device", device_id="android-a", user_confirmed=False,
    )
    assert private["id"] not in {item["id"] for item in advanced_memory.retrieve("host metadata", device_id="android-b")["items"]}
    assert private["id"] in {item["id"] for item in advanced_memory.retrieve("host metadata", device_id="android-a")["items"]}

    edited = advanced_memory.update_item(project["id"], content="GAIA conserva memoria avanzada con provenance y retrieval bounded.", importance=0.99)
    assert edited and edited["content"].startswith("GAIA conserva")
    assert advanced_memory.set_flags(project["id"], pinned=True)["pinned"] is True
    assert advanced_memory.delete_item(old_irrelevant["id"]) is True
    assert advanced_memory.get_item(old_irrelevant["id"], include_history=True)["status"] == "deleted"

    for index in range(30):
        advanced_memory.save_item(memory_key=f"project.note.{index}", kind="project", category="nota", content=f"GAIA bounded context item {index}", source_type="PROJECT", source_ref="project:GAIA-AI", project="GAIA-AI", scope="project", device_id="pc-main", user_confirmed=True)
    bounded = advanced_memory.retrieve("GAIA bounded context item", project="GAIA-AI", device_id="pc-main", limit=50, max_chars=800)
    assert len(bounded["context_text"]) <= 800 and len(bounded["items"]) <= 50

    memory.save_message("s-summary", "user", "Decidimos conservar memoria editable del proyecto GAIA.")
    memory.save_message("s-summary", "assistant", "Luego revisaremos el retrieval y la trazabilidad.")
    consolidated = advanced_memory.consolidate_session("s-summary")
    assert consolidated["llm_used"] is False and consolidated["created_memory_items"] == 0 and consolidated["summary"]

    try:
        advanced_memory.save_item(memory_key="bad", kind="semantic", category="x", content="token=abcdefghijklmnopqrstuvwxyz123456", source_type="USER_EXPLICIT")
    except ValueError:
        pass
    else:
        raise AssertionError("advanced memory accepted a secret-like value")

print("ADVANCED MEMORY V090 TEST OK: schema 8, provenance, dedup, contradiction history, scope, retrieval score/budget, edit/delete/pin and no-LLM consolidation.")
