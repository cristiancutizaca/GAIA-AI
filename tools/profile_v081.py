"""Mediciones reproducibles de startup/idle para el hardening v0.9.0.

La herramienta es read-only respecto al proyecto: usa un directorio temporal,
backend mock y no inicia un servidor ni ejecuta capabilities del host.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "lumen-core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))


def rss_mb() -> float:
    # Linux reports KiB; macOS reports bytes. The sandbox is Linux, but keep the
    # conversion explicit for portability of the diagnostic output.
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return raw / (1024.0 if sys.platform != "darwin" else 1024.0 * 1024.0)


async def idle_probe() -> dict[str, float | int | bool]:
    from event_engine import EventEngine
    from automation_runtime import AutomationRuntime

    runtime = AutomationRuntime()
    started = time.perf_counter()
    await runtime.start()
    startup_ms = (time.perf_counter() - started) * 1000.0
    await asyncio.sleep(0.10)
    status = runtime.status()
    await runtime.stop()
    return {
        "runtime_startup_ms": round(startup_ms, 3),
        "idle_queue_depth": int(status.get("events", {}).get("queue_depth", 0)),
        "idle_event_engine_running": bool(status.get("events", {}).get("running", False)),
        "idle_scheduler_running": bool(status.get("scheduler", {}).get("running", False)),
        "idle_rss_mb": round(rss_mb(), 3),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gaia_profile_v081_") as tmp:
        os.environ.update({
            "LUMEN_DATA_DIR": tmp,
            "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
            "LUMEN_LLM_BACKEND": "mock",
            "LUMEN_SECRET": "profile-v081-secret",
            "GAIA_AUTOMATION_MODE": "ROUTINES",
            "LUMEN_PROACTIVE_ENABLED": "false",
        })
        import_start = time.perf_counter()
        for module_name in ("config", "memory", "automation_store", "event_engine", "scheduler", "automation_runtime"):
            importlib.import_module(module_name)
        import_ms = (time.perf_counter() - import_start) * 1000.0
        data = {"profile": "v0.9.0", "import_ms": round(import_ms, 3), "rss_mb_after_import": round(rss_mb(), 3)}
        data.update(asyncio.run(idle_probe()))
        print(json.dumps(data, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
