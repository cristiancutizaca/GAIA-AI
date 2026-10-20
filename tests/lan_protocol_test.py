"""LAN/pairing protocol primitives for GAIA v0.6."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

from lan_protocol import PairingManager, SlidingWindowRateLimiter, negotiate_features

manager = PairingManager()
started = manager.start("android-test", ["chat", "memory_continuity", "actions_execute", "unknown_feature"])
assert started["device_id"] == "android-test" and started["code"].isdigit() and len(started["code"]) == 6
paired = manager.complete(started["pairing_id"], started["code"])
assert paired["device_id"] == "android-test" and "unknown_feature" not in paired["capabilities"]
try:
    manager.complete(started["pairing_id"], started["code"])
except ValueError:
    pass
else:
    raise AssertionError("pairing code was reusable")

for _ in range(5):
    retry = manager.start("android-attempt-limit", ["chat"])
    for attempt in range(5):
        try:
            manager.complete(retry["pairing_id"], "000000")
        except ValueError:
            pass
    try:
        manager.complete(retry["pairing_id"], retry["code"])
    except ValueError:
        pass
    else:
        raise AssertionError("pairing survived maximum invalid attempts")

limited = SlidingWindowRateLimiter(limit=2, window_seconds=60)
assert limited.check("device-a", now=100)[0] is True
assert limited.check("device-a", now=101)[0] is True
third, retry_after = limited.check("device-a", now=102)
assert third is False and retry_after >= 1
assert limited.check("device-a", now=161)[0] is True

negotiated = negotiate_features({"chat": "1", "actions_execute": "1", "streaming_sse": "1"}, {"chat": "1", "actions_execute": "1", "streaming_sse": "1"})
assert negotiated["features"] == {"chat": "1", "streaming_sse": "1"} and negotiated["restricted"] is True
remote = negotiate_features({"chat": "1", "actions_execute": "1"}, {"chat": "1", "actions_execute": "1"}, allow_remote_actions=True)
assert remote["features"]["actions_execute"] == "1" and remote["restricted"] is False

print("LAN PROTOCOL TEST OK: one-time pairing, attempt cap, sliding rate limit and safe feature negotiation.")
