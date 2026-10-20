from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_dsh_fallback_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "deepseek-harness",
        "LUMEN_LLM_MODEL": "qwen3.5:4b",
        "GAIA_DSH_FALLBACK_TO_OLLAMA": "true",
        "LUMEN_SECRET": "deepseek-harness-fallback-secret",
    })
    import llm
    from model_router import selection_for

    fake = types.ModuleType("harness_backend")

    class HarnessBackendError(RuntimeError):
        pass

    async def harness_chat(*_args, **_kwargs):
        raise HarnessBackendError("runtime intentionally unavailable")

    fake.HarnessBackendError = HarnessBackendError
    fake.harness_chat = harness_chat
    sys.modules["harness_backend"] = fake

    async def fake_ollama(*_args, **_kwargs):
        return "OLLAMA_FALLBACK_OK"

    llm._ollama_chat = fake_ollama
    result = asyncio.run(llm._chat_once("GAIA", [{"role": "user", "content": "hola"}], {"num_ctx": 4096}, selection_for("normal")))
    assert result == "OLLAMA_FALLBACK_OK"

print("DEEPSEEK HARNESS FALLBACK TEST OK")
