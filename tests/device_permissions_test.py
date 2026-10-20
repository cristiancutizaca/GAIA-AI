"""Matriz mínima de autorización por token de dispositivo para v0.5.4."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_permissions_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "master-permissions-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_AUTO_MEMORY_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    from main import app
    import memory

    master = {"Authorization": "Bearer master-permissions-secret"}
    with TestClient(app) as client:
        assert client.post("/api/devices/register", headers=master, json={
            "device_id": "android-chat", "capabilities": ["chat"], "permission_level": 0,
        }).status_code == 200
        created = client.post("/api/devices/android-chat/token", headers=master, json={"ttl_days": 2})
        assert created.status_code == 200, created.text
        device = {"Authorization": f"Bearer {created.json()['token']}"}

        assert client.post("/api/chat", headers=device, json={"message": "hola", "device": "spoofed"}).status_code == 200
        assert client.get("/api/memory/facts", headers=device).status_code == 403
        assert client.post("/api/memory/fact", headers=device, json={"category": "x", "fact": "y"}).status_code == 403
        assert client.post("/api/proactive/toggle", headers=device).status_code == 403
        assert client.post("/api/devices/register", headers=device, json={"device_id": "evil"}).status_code == 403
        assert client.post("/api/devices/android-chat/token", headers=device, json={"ttl_days": 2}).status_code == 403
        assert client.get("/api/diagnostics", headers=device).status_code == 403
        assert client.post("/api/backup/brain/restore", headers=device, files={"archive": ("bad.zip", b"not-a-backup", "application/zip")}).status_code == 403

        assert client.post("/api/devices/register", headers=master, json={
            "device_id": "memory-reader", "capabilities": ["chat", "memory_read"], "permission_level": 0,
        }).status_code == 200
        reader_created = client.post("/api/devices/memory-reader/token", headers=master, json={"ttl_days": 2})
        reader = {"Authorization": f"Bearer {reader_created.json()['token']}"}
        assert client.get("/api/memory/search", headers=reader, params={"query": "anything"}).status_code == 200
        assert client.post("/api/memory/fact", headers=reader, json={"category": "x", "fact": "y"}).status_code == 403
        assert client.post("/api/backup/brain/restore", headers=reader, files={"archive": ("bad.zip", b"x", "application/zip")}).status_code == 403

        revoked = created.json()["token_id"]
        assert client.post(f"/api/device-tokens/{revoked}/revoke", headers=master).status_code == 200
        assert client.post("/api/chat", headers=device, json={"message": "después", "device": "android-chat"}).status_code == 401

        exp_created = client.post("/api/devices/memory-reader/token", headers=master, json={"ttl_days": 1})
        exp_token_id = exp_created.json()["token_id"]
        with memory.get_db() as conn:
            conn.execute("UPDATE device_tokens SET expires_at='2000-01-01T00:00:00', last_used_at=NULL WHERE token_id=?", (exp_token_id,))
        expired = {"Authorization": f"Bearer {exp_created.json()['token']}"}
        assert client.post("/api/chat", headers=expired, json={"message": "expirado"}).status_code == 401
        with memory.get_db() as conn:
            row = conn.execute("SELECT last_used_at, revoked FROM device_tokens WHERE token_id=?", (exp_token_id,)).fetchone()
            assert row["last_used_at"] is None and row["revoked"] == 1

print("DEVICE PERMISSIONS TEST OK: 403 por capability, restore master-only, revoke y expiry.")
