from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

import llm


async def main() -> None:
    original = llm._chat_once
    started = asyncio.Event()

    async def slow_once(*args, **kwargs):
        started.set()
        await asyncio.sleep(0.08)
        return "ok"

    llm._chat_once = slow_once
    before = llm.metrics()
    try:
        first = asyncio.create_task(llm.chat_completion("system", [{"role": "user", "content": "uno"}]))
        await started.wait()
        second = asyncio.create_task(llm.chat_completion("system", [{"role": "user", "content": "dos"}]))
        await asyncio.sleep(0.01)
        second.cancel()
        try:
            await second
        except asyncio.CancelledError:
            pass
        assert llm.metrics()["queued"] == 0
        assert await first == "ok"
    finally:
        llm._chat_once = original
        await llm.shutdown_http_client()
    after = llm.metrics()
    assert after["llm_calls"] - before["llm_calls"] == 2
    assert after["completed"] - before["completed"] == 1
    assert after["cancelled"] - before["cancelled"] >= 1
    assert after["queue_wait_ms"] >= before["queue_wait_ms"]


asyncio.run(main())
print("LLM QUEUE TEST OK: queued cancellation, FIFO semaphore, completion metrics and lifecycle client shutdown.")
