from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "physical_validation.py"
env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
with tempfile.TemporaryDirectory(prefix="gaia_rc4_physical_contract_") as tmp:
    external = Path(tmp)
    created = subprocess.run([sys.executable, str(TOOL), "new", "--output-dir", str(external)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert created.returncode == 0, created.stderr
    metadata = json.loads(created.stdout)
    report = Path(metadata["json"])
    markdown = Path(metadata["markdown"])
    assert report.parent == external and markdown.parent == external
    data = json.loads(report.read_text(encoding="utf-8"))
    assert len(data["checks"]) == 12
    assert all(item["status"] == "PENDING" and item["operator_confirmed"] is False for item in data["checks"])
    assert data["release_authorization"] == "NO_FINAL_RELEASE_AUTHORIZATION"

    show = subprocess.run([sys.executable, str(TOOL), "show", "--report", str(report)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert show.returncode == 0, show.stderr
    assert json.loads(show.stdout)["summary"]["PENDING"] == 12

    evidence = external / "redacted-evidence.txt"
    evidence.write_text("redacted metadata only\n", encoding="utf-8")
    blocked_pass = subprocess.run([sys.executable, str(TOOL), "record", "--report", str(report), "--check", "windows_runtime", "--status", "PASS", "--evidence-file", str(evidence)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert blocked_pass.returncode != 0
    assert "operator-confirmed" in blocked_pass.stderr

    recorded = subprocess.run([sys.executable, str(TOOL), "record", "--report", str(report), "--check", "windows_runtime", "--status", "PASS", "--evidence-file", str(evidence), "--operator-confirmed", "--notes", "redacted"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert recorded.returncode == 0, recorded.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    check = next(item for item in data["checks"] if item["id"] == "windows_runtime")
    assert check["status"] == "PASS" and check["operator_confirmed"] is True
    assert check["evidence"].startswith("provided=true;bytes=")
    assert data["summary"]["PENDING"] == 11 and len(data["history"]) == 1

    finalized = subprocess.run([sys.executable, str(TOOL), "finalize", "--report", str(report)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert finalized.returncode == 0, finalized.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["closed_at"] and data["release_authorization"] == "NO_FINAL_RELEASE_AUTHORIZATION"
    assert "No physical result" in markdown.read_text(encoding="utf-8")

    overwrite = subprocess.run([sys.executable, str(TOOL), "record", "--report", str(report), "--check", "uia", "--status", "SKIP"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert overwrite.returncode != 0 and "finalizada" in overwrite.stderr

print("RC4 PHYSICAL VALIDATION TEST OK: timestamped external ledger, evidence, confirmation and immutable finalize rules hold.")
