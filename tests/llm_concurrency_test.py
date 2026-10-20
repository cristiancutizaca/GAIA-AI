"""Semaphore regression: at most one heavy LLM call when configured at 1."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="gaia_concurrency_") as tmp:
    os.environ.update({
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-secret-concurrency-2026",
        "GAIA_MAX_CONCURRENT_LLM_REQUESTS": "1",
        "GAIA_DATA_DIR": tmp,
    })
    sys.path.insert(0, str(ROOT / "lumen-core"))
    import llm

    active = 0
    maximum = 0

    async def fake_chat_once(*_args, **_kwargs):
        nonlocal_state["active"] += 1
        nonlocal_state["maximum"] = max(nonlocal_state["maximum"], nonlocal_state["active"])
        await asyncio.sleep(0.03)
        nonlocal_state["active"] -= 1
        return "respuesta"

    nonlocal_state = {"active": 0, "maximum": 0}
    original = llm._chat_once
    llm._chat_once = fake_chat_once
    try:
        async def run():
            await asyncio.gather(
                llm.chat_completion("sistema", [{"role": "user", "content": "uno"}]),
                llm.chat_completion("sistema", [{"role": "user", "content": "dos"}]),
            )
        asyncio.run(run())
        assert nonlocal_state["maximum"] == 1, nonlocal_state
    finally:
        llm._chat_once = original

print("LLM CONCURRENCY TEST OK: max concurrent heavy calls=1.")
