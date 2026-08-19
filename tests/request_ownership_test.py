"""Ownership de requests SSE y cancelación entre dispositivos."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_request_owner_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "request-owner-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    from main import app
    import memory
    from authz import authenticate
    from routes.api import ChatRequest, _assistant_stream

    master = {"Authorization": "Bearer request-owner-secret"}
    with TestClient(app) as client:
        device_headers = {}
        for device_id in ("owner-a", "owner-b"):
            assert client.post("/api/devices/register", headers=master, json={"device_id": device_id, "capabilities": ["chat"]}).status_code == 200
            created = client.post(f"/api/devices/{device_id}/token", headers=master, json={"ttl_days": 1})
            assert created.status_code == 200, created.text
            device_headers[device_id] = {"Authorization": f"Bearer {created.json()['token']}"}

        owner_principal = authenticate(device_headers["owner-a"]["Authorization"])

        async def prime_stream():
            generator = _assistant_stream(ChatRequest(message="hola ownership", device="owner-a"), owner_principal)
            meta_line = await generator.__anext__()
            payload = json.loads(meta_line.split("data: ", 1)[1])
            return generator, payload["request_id"]

        generator, request_id = asyncio.run(prime_stream())
        try:
            cross_device = client.post("/api/assistant/cancel", headers=device_headers["owner-b"], json={"request_id": request_id})
            assert cross_device.status_code == 403, cross_device.text
            owner_cancel = client.post("/api/assistant/cancel", headers=device_headers["owner-a"], json={"request_id": request_id})
            assert owner_cancel.status_code == 200, owner_cancel.text
            master_cancel = client.post("/api/assistant/cancel", headers=master, json={"request_id": request_id})
            assert master_cancel.status_code == 200, master_cancel.text
        finally:
            asyncio.run(generator.aclose())
            memory.delete_state(f"request_owner:{request_id}")
            memory.delete_state(f"cancel:{request_id}")

print("REQUEST OWNERSHIP TEST OK: cross-device 403, owner 200, master 200 y cleanup.")
