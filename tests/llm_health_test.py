from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))
os.environ.update({"LUMEN_LLM_BACKEND": "ollama", "LUMEN_LLM_MODEL": "qwen3.5:9b", "LUMEN_SECRET": "test-secret-health"})
import llm


class Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Client:
    mode = "missing"

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url: str):
        if self.mode == "offline":
            raise httpx.ConnectError("offline")
        return Response({"models": [{"name": "other:latest"}]})


original = llm.httpx.AsyncClient
llm.httpx.AsyncClient = Client
try:
    Client.mode = "missing"
    missing = asyncio.run(llm.check_backend())
    assert missing["status"] == "model_missing"
    assert "ollama pull qwen3.5:9b" in missing["hint"]
    Client.mode = "offline"
    offline = asyncio.run(llm.check_backend())
    assert offline["status"] == "offline" and offline["reachable"] is False
    assert "no descargará modelos" in offline["hint"]
finally:
    llm.httpx.AsyncClient = original

print("LLM HEALTH TEST OK")
