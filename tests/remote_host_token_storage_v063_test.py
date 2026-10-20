from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "lumen-pc"))

with tempfile.TemporaryDirectory(prefix="gaia_remote_token_v063_") as tmp:
    token_path = Path(tmp) / "remote-host.token"
    os.environ["GAIA_REMOTE_HOST_TOKEN_FILE"] = str(token_path)
    import run_remote_action_host as bootstrap

    bootstrap._write_token("test-remote-host-token-v063")
    assert token_path.is_file()
    assert bootstrap._read_token() == "test-remote-host-token-v063"
    if os.name != "nt":
        assert stat.S_IMODE(token_path.stat().st_mode) == 0o600
    assert token_path.read_bytes() != b"test-remote-host-token-v063\n" if os.name == "nt" else True

source = (ROOT / "tools/run_remote_action_host.py").read_text(encoding="utf-8")
assert "CryptProtectData" in source and "CryptUnprotectData" in source
assert "os.replace" in source and "chmod(0o600)" in source
assert "path.write_text(token" not in source
assert "print(token" not in source
print("REMOTE HOST TOKEN STORAGE V063 TEST OK: DPAPI Windows path and chmod-600 Linux path are explicit; plaintext write removed.")
