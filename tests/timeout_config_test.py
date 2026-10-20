from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_API = (ROOT / "lumen-pc" / "desktop_api.py").read_text(encoding="utf-8")
assert "ACTION_COMPLETION_TIMEOUT = max(60.0, REQUESTED_CLIENT_TIMEOUT, POST_ACTION_TIMEOUT + 15.0)" in DESKTOP_API
assert "timeout=ACTION_COMPLETION_TIMEOUT" in DESKTOP_API
cancel_block = DESKTOP_API[DESKTOP_API.index("    def cancel_action"):DESKTOP_API.index("    def cancel_generation")]
assert "timeout=ACTION_COMPLETION_TIMEOUT" in cancel_block
assert "timeout=30.0" not in cancel_block


def probe(post: str, client: str) -> tuple[float, float, float]:
    env = os.environ.copy()
    env.update({
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-secret-timeout-2026",
        "GAIA_POST_ACTION_LLM_TIMEOUT": post,
        "GAIA_CLIENT_ACTION_TIMEOUT": client,
        "GAIA_DATA_DIR": str(ROOT / ".timeout-test-data"),
    })
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "timeout_probe.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    values = result.stdout.strip().split()
    return tuple(float(item) for item in values[-3:])


post, client, effective = probe("30", "60")
assert post == 30 and client == 60 and effective >= 60 and effective > post
post, client, effective = probe("90", "60")
assert post == 90 and client >= 91 and effective > post
post, client, effective = probe("90", "120")
assert post == 90 and client == 120 and effective >= 120
post, client, effective = probe("abc", "60")
assert post == 30 and client == 60 and effective == 60
post, client, effective = probe("30", "not-a-number")
assert post == 30 and client == 60 and effective == 60
print("TIMEOUT CONFIG TEST OK: effective desktop timeout follows post/client values and invalid env falls back safely.")
