from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

import safe_apps

with tempfile.TemporaryDirectory(prefix="gaia_app_discovery_") as tmp:
    os.environ["GAIA_TRUSTED_APPS_FILE"] = str(Path(tmp) / "trusted_apps.json")
    fake = Path(tmp) / "Discord.exe"
    fake.write_bytes(b"MZ")
    row = safe_apps._discovered_from_path(fake, "mock-start-menu", {})
    assert row["app_id"].startswith("discovered:") and row["trusted"] is False and row["blocked"] is False, row
    saved = safe_apps.set_app_trust(row["app_id"], trusted=True, launch_definition=row["launch_definition"], display_name=row["display_name"], source=row["source"], process_names=tuple(row["process_names"]))
    assert saved["trusted"] is True and safe_apps.get_app_trust(row["app_id"])["trusted"] is True
    assert saved["launch_definition"]["executable_identity"]["sha256"]
    assert safe_apps.is_trusted_executable(str(fake)) is True
    fake.write_bytes(b"MZ-changed")
    assert safe_apps.is_trusted_executable(str(fake)) is False
    safe_apps._DISCOVERY_CACHE = (time.monotonic(), [row | {"trusted": True}])
    assert safe_apps.resolve_discovered_app(row["app_id"], require_trusted=True)["app_id"] == row["app_id"]
    once = safe_apps.set_app_trust(row["app_id"], trusted=True, blocked=False, trust_mode="ONCE", uses_remaining=1, launch_definition=row["launch_definition"], display_name=row["display_name"], source=row["source"], process_names=tuple(row["process_names"]))
    assert once["trust_mode"] == "ONCE" and once["uses_remaining"] == 1
    safe_apps._DISCOVERY_CACHE = (time.monotonic(), [row | {"trusted": True, "blocked": False, "trust_mode": "ONCE", "uses_remaining": 1}])
    assert safe_apps.resolve_discovered_app(row["app_id"], require_trusted=True)["app_id"] == row["app_id"]
    assert safe_apps.consume_discovered_app_once(row["app_id"]) is True
    assert safe_apps.resolve_discovered_app(row["app_id"], require_trusted=True) is None

    blocked = safe_apps.set_app_trust(row["app_id"], trusted=False, blocked=True, trust_mode="ALWAYS", launch_definition=row["launch_definition"], display_name=row["display_name"], source=row["source"], process_names=tuple(row["process_names"]))
    safe_apps._DISCOVERY_CACHE = (time.monotonic(), [row | {"trusted": False, "blocked": True}])
    assert blocked["blocked"] is True and safe_apps.resolve_discovered_app(row["app_id"], require_trusted=True) is None

print("APP DISCOVERY TEST OK: canonical app_id, read-only discovery model, persistent trust and blocked state.")
