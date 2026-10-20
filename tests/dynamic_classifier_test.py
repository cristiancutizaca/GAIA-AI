from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

import intent_classifier
import llm

all_count = len(intent_classifier._REGISTRY.all())
audio = intent_classifier.capability_shortlist("baja el volumen al 20")
assert audio and all(item["category"] == "audio" for item in audio), audio
assert len(audio) < all_count

async def fake_health():
    return {"status": "test_only"}

async def fake_chat(_system, _messages, **_kwargs):
    return json.dumps({"intent_type": "action", "capability": "audio.set_volume", "parameters": {"level": 20}, "confidence": 0.98, "source": "llm"})

async def fake_unknown(_system, _messages, **_kwargs):
    return json.dumps({"intent_type": "action", "capability": "windows.teleport", "parameters": {}, "confidence": 0.99, "source": "llm"})

async def run():
    original_health = llm.check_backend
    original_chat = llm.chat_completion
    try:
        llm.check_backend = fake_health
        llm.chat_completion = fake_chat
        intent_classifier._HEALTH_CACHE = (0.0, False)
        intent = await intent_classifier.classify_intent("ajusta el volumen")
        assert intent is not None and intent.name == "set_volume" and intent.args["level"] == "20" and intent.source == "llm", intent
        llm.chat_completion = fake_unknown
        intent_classifier._HEALTH_CACHE = (0.0, False)
        assert await intent_classifier.classify_intent("teletransporta una ventana") is None
    finally:
        llm.check_backend = original_health
        llm.chat_completion = original_chat

asyncio.run(run())
print("DYNAMIC CLASSIFIER TEST OK: registry-derived shortlist, capability/parameters normalization and invented capability rejection.")
