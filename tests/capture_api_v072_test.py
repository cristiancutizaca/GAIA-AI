"""v0.7.2 authenticated capture resource retrieval contract."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))
sys.path.insert(0, str(ROOT / "lumen-pc"))

with tempfile.TemporaryDirectory(prefix="gaia_capture_api_v072_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-capture-api-v072-master-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    from fastapi.testclient import TestClient  # noqa: E402
    from main import app  # noqa: E402
    from PIL import Image  # noqa: E402
    import screen_capture  # noqa: E402

    screen_capture.cleanup_captures()
    capture = screen_capture._save_image(Image.new("RGB", (3, 3), color=(90, 20, 10)), kind="window", identity="99", owner_device="android-capture", target_host="pc-main", request_id="request-1")
    master = {"Authorization": "Bearer test-capture-api-v072-master-secret"}
    with TestClient(app) as client:
        response = client.get(capture["retrieval_url"], headers=master)
        assert response.status_code == 200 and response.content.startswith(b"\x89PNG"), response.text
        registered = client.post("/api/devices/register", headers=master, json={"device_id": "android-capture", "capabilities": ["chat"], "permission_level": 0})
        assert registered.status_code == 200, registered.text
        token = client.post("/api/devices/android-capture/token", headers=master, json={"ttl_days": 2}).json()["token"]
        owner = client.get(capture["retrieval_url"], headers={"Authorization": f"Bearer {token}"})
        assert owner.status_code == 200 and owner.content.startswith(b"\x89PNG")
    screen_capture.cleanup_captures()

print("CAPTURE API V072 TEST OK: authenticated retrieval, device ownership and ephemeral PNG resource.")
