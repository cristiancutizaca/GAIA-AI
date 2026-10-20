#!/usr/bin/env python3
"""Smoke físico real: GAIA -> DeepSeek Harness SDK -> Ollama -> modelo local."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

os.environ.setdefault("LUMEN_LLM_BACKEND", "deepseek-harness")
os.environ.setdefault("LUMEN_LLM_MODEL", "qwen3.5:4b")
os.environ.setdefault("GAIA_MODEL_NORMAL", os.environ["LUMEN_LLM_MODEL"])
os.environ.setdefault("GAIA_DSH_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("GAIA_DSH_PROFILE", "sdk-minimal")
os.environ.setdefault("GAIA_LLM_CONTEXT", "4096")
os.environ.setdefault("GAIA_MAX_CONCURRENT_LLM_REQUESTS", "1")
os.environ.setdefault("LUMEN_SECRET", "physical-deepseek-harness-smoke-secret")

if not os.environ.get("LUMEN_DATA_DIR"):
    temp = tempfile.TemporaryDirectory(prefix="gaia_dsh_e2e_")
    os.environ["LUMEN_DATA_DIR"] = temp.name
    os.environ["GAIA_MEMORY_DB"] = str(Path(temp.name) / "memory.db")
else:
    temp = None

import harness_backend


async def main() -> int:
    health = await harness_backend.harness_health()
    if not health.get("reachable"):
        print(f"E2E FAIL: {health}", file=sys.stderr)
        return 2
    model = os.environ.get("LUMEN_LLM_MODEL", "qwen3.5:4b")
    models = set(health.get("available_models", []))
    if model not in models and not any(item.startswith(model + ":") for item in models):
        print(f"E2E FAIL: falta el modelo {model}. Ejecuta: ollama pull {model}", file=sys.stderr)
        return 3
    response = await harness_backend.harness_chat(
        "Eres GAIA. Esta es una prueba técnica.",
        [{"role": "user", "content": "Responde exactamente GAIA_OK y nada más."}],
        {"num_predict": 64, "num_ctx": 2048},
        model,
    )
    await harness_backend.shutdown_harnesses()
    if "GAIA_OK" not in response:
        print(f"E2E FAIL: respuesta inesperada: {response!r}", file=sys.stderr)
        return 4
    print("DEEPSEEK HARNESS E2E OK")
    return 0


try:
    raise SystemExit(asyncio.run(main()))
finally:
    if temp is not None:
        temp.cleanup()
