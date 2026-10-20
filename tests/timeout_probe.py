from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))
sys.path.insert(0, str(ROOT / "lumen-pc"))

import config
import desktop_api

print(config.POST_ACTION_LLM_TIMEOUT, config.CLIENT_ACTION_TIMEOUT, desktop_api.ACTION_COMPLETION_TIMEOUT)
