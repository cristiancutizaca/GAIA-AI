#!/usr/bin/env python3
"""Read-only diagnostics for the GAIA resident desktop. Never prints secrets."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)


def check() -> dict:
    result = {
        "platform": platform.system(),
        "python": platform.python_version(),
        "virtualenv": sys.prefix != sys.base_prefix,
        "core_url": os.getenv("LUMEN_CORE_URL", f"http://127.0.0.1:{os.getenv('LUMEN_PORT', '8090')}"),
        "required": {},
        "core_online": False,
        "action_host_online": False,
        "actions_enabled": False,
        "ollama_online": False,
        "configured_model": os.getenv("LUMEN_LLM_MODEL", "qwen3.5:4b"),
        "model_present": False,
        "gpu_loaded": None,
        "wakeword_model_ready": False,
        "autostart": "UNKNOWN",
        "log_dir": str(Path(os.getenv("GAIA_RESIDENT_LOG_DIR", str(Path.home() / ".gaia" / "logs")))),
    }
    for item in ("httpx", "dotenv", "fastapi", "PySide6", "sounddevice", "numpy", "uvicorn"):
        result["required"][item] = importlib.util.find_spec(item) is not None
    if result["required"]["httpx"]:
        import httpx
        try:
            resp = httpx.get(result["core_url"].rstrip("/") + "/api/health", timeout=3)
            result["core_online"] = resp.status_code == 200 and resp.json().get("status") in ("online", "ok", "healthy")
        except (httpx.HTTPError, ValueError):
            pass
        secret = os.getenv("LUMEN_SECRET", "").strip()
        if result["core_online"] and secret:
            headers = {"Authorization": f"Bearer {secret}"}
            try:
                status = httpx.get(result["core_url"].rstrip("/") + "/api/action-host/status",
                                   headers=headers, timeout=3)
                if status.status_code == 200:
                    result["action_host_online"] = status.json().get("online") is True
                controls = httpx.get(result["core_url"].rstrip("/") + "/api/actions/control",
                                     headers=headers, timeout=3)
                if controls.status_code == 200:
                    result["actions_enabled"] = controls.json().get("enabled") is True
            except (httpx.HTTPError, ValueError):
                pass
        ollama = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        if not ollama.startswith(("http://", "https://")):
            ollama = "http://" + ollama
        try:
            tags = httpx.get(ollama.rstrip("/") + "/api/tags", timeout=3)
            tags.raise_for_status()
            result["ollama_online"] = True
            result["model_present"] = any(x.get("name") == result["configured_model"] or x.get("model") == result["configured_model"]
                                          for x in tags.json().get("models", []))
            running = httpx.get(ollama.rstrip("/") + "/api/ps", timeout=3)
            if running.status_code == 200:
                models = running.json().get("models", [])
                if models:
                    result["gpu_loaded"] = any(int(x.get("size_vram") or 0) > 0 for x in models)
        except (httpx.HTTPError, ValueError):
            pass
    wake_model = os.getenv("GAIA_WAKEWORD_MODEL", "").strip()
    result["wakeword_model_ready"] = bool(wake_model and Path(wake_model).is_file()
                                         and importlib.util.find_spec("openwakeword"))
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import gaia_startup
        result["autostart"] = gaia_startup.status().get("status", "UNKNOWN")
    except (OSError, ImportError):
        result["autostart"] = "UNKNOWN"
    result["ready_for_desktop"] = (
        result["virtualenv"] and result["core_online"] and
        all(result["required"].values())
    )
    result["ready_for_chat"] = result["ready_for_desktop"] and result["ollama_online"] and result["model_present"]
    result["ready_for_pc_actions"] = result["ready_for_desktop"] and result["action_host_online"] and result["actions_enabled"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = check()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")
    return 0 if report["ready_for_desktop"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
