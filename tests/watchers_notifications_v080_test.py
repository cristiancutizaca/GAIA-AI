"""v0.8 watcher registry and notification privacy contract."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_watchers_v080_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-watchers-v080-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_AUTOMATION_MODE": "NOTIFY_ONLY",
    })
    import automation_store
    import memory
    from event_engine import Event, EventEngine
    from notification_service import NotificationService
    from watchers import FileWatcher, WatcherRegistry

    memory.init_db()
    root = Path(tmp) / "trusted"
    root.mkdir()
    file_path = root / "note.txt"
    file_path.write_text("SECRETO-QUE-NUNCA-DEBE-APARECER", encoding="utf-8")

    async def scenario() -> None:
        engine = EventEngine(queue_max=32)
        watcher = FileWatcher(engine, [root])
        assert await watcher.poll() == []
        file_path.write_text("nuevo", encoding="utf-8")
        changes = await watcher.poll()
        assert changes and changes[0].event_type == "file.changed"
        payload_text = str(changes[0].payload)
        assert "SECRETO-QUE-NUNCA-DEBE-APARECER" not in payload_text
        assert "path_name" in changes[0].payload
        service = NotificationService()
        service.set_mode("NOTIFY_ONLY")
        await service.on_event(Event.create("ollama.offline", source="health", payload={"secret": "redact-me"}, severity="warning", dedup_key="offline"))
        notes = automation_store.list_notifications()
        assert notes and "redact-me" not in str(notes[0]) and "no responde" in notes[0]["message"]
        registry = WatcherRegistry(engine, trusted_roots=[])
        assert registry.active() == []
        await registry.ensure({"file", "does-not-exist"})
        assert registry.active() == ["file"]
        await registry.stop()
        assert registry.active() == []

    asyncio.run(scenario())

print("WATCHERS NOTIFICATIONS V080 TEST OK: lazy registry, file metadata-only, deterministic redaction and clean stop.")
