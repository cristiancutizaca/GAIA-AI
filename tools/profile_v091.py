"""Perfil read-only de GAIA v0.9.1: memoria segura y runtime bounded.

La herramienta usa DB temporal, backend mock y no ejecuta capabilities del host.
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
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return raw / (1024.0 if sys.platform != "darwin" else 1024.0 * 1024.0)


async def idle_probe() -> dict[str, float | int | bool]:
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


def memory_probe() -> dict[str, float | int | bool]:
    import advanced_memory

    for index in range(24):
        advanced_memory.save_item(
            memory_key=f"profile.memory.{index}", kind="project", category="profile",
            content=f"GAIA v0.9.1 memory retrieval sample {index}", source_type="PROJECT",
            source_ref="profile:v091", provenance_type="PROFILE", confidence=0.8,
            importance=0.6, scope="profile", project="GAIA-AI", device_id="profile-pc",
            user_confirmed=True,
        )
    started = time.perf_counter()
    result = advanced_memory.retrieve(
        "GAIA memory retrieval sample", scope="profile", project="GAIA-AI",
        device_id="profile-pc", limit=12, max_chars=2400,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    items = advanced_memory.list_items(scope="profile", project="GAIA-AI", device_id="profile-pc", limit=50)
    return {
        "memory_retrieval_ms": round(max(float(result.get("retrieval_ms", 0)), elapsed_ms), 3),
        "memory_items_count": len(items),
        "memory_result_count": len(result.get("items", [])),
        "memory_context_chars": len(result.get("context_text", "")),
        "memory_context_truncated": bool(result.get("truncated", False)),
        "embedding_backend_enabled": bool(getattr(advanced_memory.embedding_backend, "enabled", False)),
        "namespace_count": len({item.get("namespace_id") for item in items}),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gaia_profile_v091_") as tmp:
        os.environ.update({
            "LUMEN_DATA_DIR": tmp,
            "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
            "LUMEN_LLM_BACKEND": "mock",
            "LUMEN_SECRET": "profile-v091-secret",
            "GAIA_AUTOMATION_MODE": "ROUTINES",
            "LUMEN_PROACTIVE_ENABLED": "false",
        })
        import_start = time.perf_counter()
        for module_name in ("config", "memory", "advanced_memory", "automation_store", "event_engine", "scheduler", "automation_runtime"):
            importlib.import_module(module_name)
        import_ms = (time.perf_counter() - import_start) * 1000.0
        data: dict[str, float | int | bool | str] = {
            "profile": "v0.9.1",
            "import_ms": round(import_ms, 3),
            "rss_mb_after_import": round(rss_mb(), 3),
        }
        data.update(memory_probe())
        data.update(asyncio.run(idle_probe()))
        print(json.dumps(data, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
