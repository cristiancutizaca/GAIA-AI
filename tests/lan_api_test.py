"""HTTP contracts for opt-in LAN pairing and feature negotiation."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_lan_api_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-lan-api-master-secret",
        "GAIA_LAN_ENABLED": "true",
        "LUMEN_HOST": "0.0.0.0",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    from main import app

    master = {"Authorization": "Bearer test-lan-api-master-secret"}
    with TestClient(app) as client:
        started = client.post("/api/pairing/start", headers=master, json={"device_id": "android-lan", "capabilities": ["chat", "actions_request", "unknown"]})
        assert started.status_code == 200, started.text
        body = started.json()
        assert body["protocol_version"] == "1.0-RC6"
        assert body["pairing_uri"] == body["qr_payload"]
        parsed_uri = urlparse(body["pairing_uri"])
        assert parsed_uri.scheme == "gaia" and parsed_uri.netloc == "pair"
        query = parse_qs(parsed_uri.query)
        assert query["id"] == [body["pairing_id"]] and query["code"] == [body["code"]] and query["url"]
        completed = client.post("/api/pairing/complete", json={"pairing_id": body["pairing_id"], "code": body["code"], "features": {"chat": "1", "actions_execute": "1"}})
        assert completed.status_code == 200 and completed.json()["device_id"] == "android-lan"
        paired = completed.json()
        assert paired["token"] and paired["token_id"] and paired["onboarding"]["status"] == "complete"
        assert paired["token_return"] if "token_return" in paired else True
        assert paired["negotiation"]["restricted"] is True
        replay = client.post("/api/pairing/complete", json={"pairing_id": body["pairing_id"], "code": body["code"], "features": {"chat": "1"}})
        assert replay.status_code == 400
        devices = client.get("/api/devices", headers=master)
        assert devices.status_code == 200 and any(item["device_id"] == "android-lan" and item["device_type"] == "android" for item in devices.json())
        android_headers = {"Authorization": "Bearer " + paired["token"]}
        android_chat = client.post("/api/chat", headers=android_headers, json={"message": "hola", "device": "android-lan"})
        assert android_chat.status_code == 200
        negotiated = client.post("/api/devices/negotiate", headers=master, json={"features": {"chat": "1", "actions_execute": "1"}, "request_remote_actions": True})
        assert negotiated.status_code == 200 and negotiated.json()["restricted"] is False and negotiated.json()["features"]["actions_execute"] == "1"

print("LAN API TEST OK: explicit LAN opt-in, onboarding device/token, conservative Android auth and master feature negotiation.")
