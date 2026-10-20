from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_release.py"

with tempfile.TemporaryDirectory(prefix="gaia_rc6_builder_contract_") as tmp:
    base = Path(tmp)
    a = base / "a"
    b = base / "b"
    env = {**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"}
    for output in (a, b):
        result = subprocess.run([sys.executable, str(BUILDER), "--output-dir", str(output)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stderr + result.stdout
    archive_a = a / "GAIA-AI-v1.0-RC6-final.zip"
    archive_b = b / "GAIA-AI-v1.0-RC6-final.zip"
    assert archive_a.read_bytes() == archive_b.read_bytes()
    assert (a / "GAIA-AI-v1.0-RC6-final.zip.sha256").read_text(encoding="utf-8").split()[0]

    duplicate = base / "duplicate.zip"
    with zipfile.ZipFile(duplicate, "w") as bundle:
        bundle.writestr("GAIA-AI-v1.0-RC6/a.txt", "one")
        bundle.writestr("GAIA-AI-v1.0-RC6/A.txt", "two")
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_release_rc6_contract", BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.verify_archive(duplicate, {"GAIA-AI-v1.0-RC6/a.txt", "GAIA-AI-v1.0-RC6/A.txt"})
    except RuntimeError as exc:
        assert "normalización" in str(exc)
    else:
        raise AssertionError("normalized duplicate ZIP members must be rejected")

print("RC6 BUILDER CONTRACT TEST OK: deterministic A/B bytes, sidecar hash and normalized duplicate rejection hold.")
