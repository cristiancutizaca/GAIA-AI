"""permission_level es metadata; capabilities siguen siendo autoridad."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_permission_level_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "permission-level-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    from main import app
    import memory

    master = {"Authorization": "Bearer permission-level-secret"}
    with TestClient(app) as client:
        assert client.post("/api/devices/register", headers=master, json={"device_id": "high-level", "capabilities": ["chat"], "permission_level": 0}).status_code == 200
        created = client.post("/api/devices/high-level/token", headers=master, json={"ttl_days": 1})
        assert created.status_code == 200, created.text
        with memory.get_db() as conn:
            conn.execute("UPDATE devices SET permission_level=999 WHERE device_id='high-level'")
        token_headers = {"Authorization": f"Bearer {created.json()['token']}"}
        assert client.post("/api/chat", headers=token_headers, json={"message": "hola"}).status_code == 200
        assert client.get("/api/memory/facts", headers=token_headers).status_code == 403
        assert client.get("/api/diagnostics", headers=token_headers).status_code == 403
        assert client.post("/api/backup/brain/restore", headers=token_headers, files={"archive": ("x.zip", b"not-a-backup", "application/zip")}).status_code == 403
        assert client.get("/api/devices", headers=token_headers).status_code == 403

print("PERMISSION LEVEL TEST OK: level 999 no agrega capabilities ni privilegios.")
