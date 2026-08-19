"""Regresión: touch_device solo actualiza presencia."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_touch_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "touch-secret"})
    import memory

    memory.init_db()
    memory.register_device("touch-device", ["chat", "voice"], 2, "Teléfono", "android")
    before = next(item for item in memory.get_devices() if item["device_id"] == "touch-device")
    memory.touch_device("touch-device", ["admin"])
    after = next(item for item in memory.get_devices() if item["device_id"] == "touch-device")
    assert after["capabilities"] == before["capabilities"] == ["chat", "voice"]
    assert after["permission_level"] == before["permission_level"] == 2
    assert after["name"] == before["name"] == "Teléfono"
    assert after["device_type"] == before["device_type"] == "android"
    assert after["revoked"] == before["revoked"] == 0

print("DEVICE TOUCH TEST OK: touch_device conserva metadata y permisos.")
