from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_dsh_test_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "deepseek-harness",
        "LUMEN_LLM_MODEL": "qwen3.5:4b",
        "GAIA_LLM_CONTEXT": "4096",
        "LUMEN_SECRET": "deepseek-harness-test-secret",
    })
    import config
    import harness_backend
    import model_router

    prompt = harness_backend._prompt("Eres GAIA", [{"role": "user", "content": "hola"}])
    assert "Eres GAIA" in prompt and "hola" in prompt
    assert config.LLM_MODEL == "qwen3.5:4b"
    assert config.DSH_PROFILE == "sdk-minimal"
    assert config.DSH_FALLBACK_TO_OLLAMA is True
    assert config.DSH_WORKSPACE != ROOT
    assert model_router.profile_options("code")["num_ctx"] == 4096

    safe_patch = ROOT / "deepseek-harness" / "gaia-safe.patch.yml"
    patch_text = safe_patch.read_text(encoding="utf-8")
    assert "persistent-bash" in patch_text and "persistent-pwsh" in patch_text
    assert patch_text.count("disabled: true") == 2

    requirements = (ROOT / "lumen-core" / "requirements.txt").read_text(encoding="utf-8")
    assert "deepseek-harness-sdk==0.1.5rc1" in requirements
    assert not (ROOT / "deepseek-harness" / "package-lock.json").exists()
    assert not (ROOT / "deepseek-harness" / "package.json").exists()

print("DEEPSEEK HARNESS INTEGRATION TEST OK")
