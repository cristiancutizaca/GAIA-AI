"""v0.7.0 token rotation, recovery and performance endpoint contracts."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.update({
    "LUMEN_DATA_DIR": tempfile.mkdtemp(prefix="gaia_token_v063_"),
    "LUMEN_LLM_BACKEND": "mock",
    "LUMEN_SECRET": "test-token-security-v063-master-secret",
    "LUMEN_BACKUP_ENABLED": "false",
    "LUMEN_PROACTIVE_ENABLED": "false",
})
import sys
sys.path.insert(0, str(ROOT / "lumen-core"))

from fastapi.testclient import TestClient
from main import app

master = {"Authorization": "Bearer test-token-security-v063-master-secret"}
with TestClient(app) as client:
    registered = client.post(
        "/api/devices/register",
        headers=master,
        json={"device_id": "android-rotate", "capabilities": ["chat", "diagnostics"], "permission_level": 0},
    )
    assert registered.status_code == 200, registered.text
    created = client.post("/api/devices/android-rotate/token", headers=master, json={"ttl_days": 2})
    assert created.status_code == 200, created.text
    old = created.json()
    old_headers = {"Authorization": f"Bearer {old['token']}"}
    assert client.get("/api/status", headers=old_headers).status_code == 200

    rotated = client.post("/api/devices/android-rotate/rotate-token", headers=master, json={"ttl_days": 3})
    assert rotated.status_code == 200, rotated.text
    new = rotated.json()
    assert new["status"] == "rotated" and new["old_tokens_revoked"] is True
    assert new["token"] and new["token"] != old["token"]
    assert client.get("/api/status", headers=old_headers).status_code == 401
    new_headers = {"Authorization": f"Bearer {new['token']}"}
    assert client.get("/api/status", headers=new_headers).status_code == 200

    token_rows = client.get("/api/devices/android-rotate/tokens", headers=master)
    assert token_rows.status_code == 200
    rows = token_rows.json()
    assert any(row["token_id"] == old["token_id"] and row["revoked"] for row in rows)
    assert any(row["token_id"] == new["token_id"] and not row["revoked"] for row in rows)
    assert all("token" not in row and "token_hash" not in row for row in rows)

    performance = client.get("/api/diagnostics/performance", headers=master)
    assert performance.status_code == 200, performance.text
    metrics = performance.json()
    assert metrics["version"] == "2.0.0" and "llm" in metrics and "performance" in metrics

print("TOKEN SECURITY V063 TEST OK: atomic rotation, old-token revocation, new-token continuity, secret-free listing and performance metrics.")
