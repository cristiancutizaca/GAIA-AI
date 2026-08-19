from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="gaia_vault_missing_") as tmp:
    env = os.environ.copy()
    env.update({
        "GAIA_HOME": str(Path(tmp) / "not-mounted"),
        "GAIA_VAULT": str(Path(tmp) / "not-mounted"),
        "LUMEN_DATA_DIR": str(Path(tmp) / "fallback-data"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-secret-vault-missing",
    })
    script = "import sys; sys.path.insert(0, 'lumen-core'); import config; print(config.VAULT_STATUS); print(config.DATA_DIR)"
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "missing_fallback", result.stdout
    assert "fallback-data" in lines[1], result.stdout
    assert not (Path(tmp) / "not-mounted").exists()

print("VAULT MISSING TEST OK")
