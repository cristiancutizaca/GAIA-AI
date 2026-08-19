from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))
sys.path.insert(0, str(ROOT / "lumen-pc"))

import llm  # noqa: E402
from action_engine import ActionEngine  # noqa: E402
from model_router import profile_options, resolve_profile  # noqa: E402


async def run(prompt: str, profile: str) -> dict:
    started = time.perf_counter()
    first_token = None
    chunks = []
    effective_profile = resolve_profile(prompt, requested=profile)
    async for chunk in llm.chat_completion_stream("Responde de forma breve y técnica.", [{"role": "user", "content": prompt}], profile=profile):
        if first_token is None:
            first_token = time.perf_counter()
        chunks.append(chunk)
    ended = time.perf_counter()
    engine = ActionEngine(ROOT)
    selection = llm.selection_for(effective_profile)
    options = profile_options(effective_profile)
    return {
        "backend": llm.LLM_BACKEND,
        "profile_requested": profile,
        "profile": effective_profile,
        "model": selection.selected_model,
        "time_to_first_token_seconds": round(first_token - started, 3) if first_token else "N/A",
        "total_seconds": round(ended - started, 3),
        "tokens_per_second": "N/A",
        "context": options.get("num_ctx", "N/A"),
        "fallback": "N/A (el stream no expone metadata de fallback)",
        "visible_chars": len("".join(chunks)),
        "hardware": {"ram": engine._memory_stats(), "cpu": engine._cpu_stats()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark opcional de GAIA local")
    parser.add_argument("prompt", nargs="?", default="Explica en una frase qué es una API.")
    parser.add_argument("--profile", choices=("auto", *sorted(llm.PROFILES)), default="auto")
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(run(args.prompt, args.profile)), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
