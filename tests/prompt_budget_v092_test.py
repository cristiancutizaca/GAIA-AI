from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_prompt_budget_v092_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "prompt-budget-v092-secret",
        "GAIA_HARDWARE_PROFILE": "laptop_balanced",
        "GAIA_PERFORMANCE_PROFILE": "balanced",
        "GAIA_MEMORY_CONTEXT_MAX_CHARS": "4096",
        "GAIA_MEMORY_RELEVANCE_LIMIT": "8",
        "GAIA_AUTOMATION_MODE": "OFF",
    })
    from routes.api import _prepare_context, prompt_metrics

    _prepare_context("prompt-budget-session", "mensaje interactivo que no debe aparecer en las métricas", "pc-main")
    metrics = prompt_metrics()
    assert metrics["context_budget"] <= 4096
    assert metrics["memory_item_limit"] <= 8
    assert metrics["total_chars"] >= metrics["system_chars"]
    assert all(isinstance(value, int) for value in metrics.values())
    assert all("mensaje interactivo" not in str(value) for value in metrics.values())

print("PROMPT BUDGET V092 TEST OK: laptop context cap, bounded memory selection and size-only diagnostics.")
