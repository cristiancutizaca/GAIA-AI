from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "physical_validation.py"
ENV = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}

def run(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=timeout)

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

with tempfile.TemporaryDirectory(prefix="gaia_rc6_physical_integrity_") as temp:
    out = Path(temp)
    created = run("new", "--output-dir", str(out))
    assert created.returncode == 0, created.stderr
    report_path = Path(json.loads(created.stdout)["json"])
    markdown_path = report_path.with_suffix(".md")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["release"] == "1.0-RC6"
    assert len(report["checks"]) == 12
    assert report["summary"] == {"BLOCKED": 0, "FAIL": 0, "NOT_MEASURED": 0, "PASS": 0, "PENDING": 12, "SKIP": 0}
    assert sum(report["summary"].values()) == len(report["checks"]) == 12
    assert report["operator_confirmed"] is False
    assert report["release_authorization"] == "NO_FINAL_RELEASE_AUTHORIZATION"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "| `PENDING` | 12 |" in markdown
    assert "| `PASS` | 0 |" in markdown

    before_show = sha(report_path)
    shown = run("show", "--report", str(report_path))
    assert shown.returncode == 0, shown.stderr
    assert sha(report_path) == before_show

    missing_evidence = run("record", "--report", str(report_path), "--check", "windows_runtime", "--status", "PASS", "--operator-confirmed")
    assert missing_evidence.returncode != 0 and "evidence" in missing_evidence.stderr.lower()

    evidence = out / "evidence.txt"
    evidence.write_text("synthetic redacted operator evidence", encoding="utf-8")
    missing_confirmation = run("record", "--report", str(report_path), "--check", "windows_runtime", "--status", "PASS", "--evidence-file", str(evidence), "--method", "bounded operator check", "--limitations", "synthetic test")
    assert missing_confirmation.returncode != 0 and "confirm" in missing_confirmation.stderr.lower()

    recorded = run("record", "--report", str(report_path), "--check", "windows_runtime", "--status", "PASS", "--evidence-file", str(evidence), "--operator-confirmed", "--method", "bounded operator check", "--limitations", "synthetic test")
    assert recorded.returncode == 0, recorded.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["summary"]["PASS"] == 1 and report["summary"]["PENDING"] == 11
    assert len(report["history"]) == 1
    assert run("validate", "--report", str(report_path)).returncode == 0

    tampered = json.loads(report_path.read_text(encoding="utf-8"))
    tampered["summary"]["PENDING"] = 0
    report_path.write_text(json.dumps(tampered, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tampered_hash = sha(report_path)
    rejected = run("validate", "--report", str(report_path))
    assert rejected.returncode != 0 and "REPORT_INCONSISTENT" in rejected.stderr
    assert sha(report_path) == tampered_hash

    repaired = run("validate", "--report", str(report_path), "--repair-summary")
    assert repaired.returncode == 0, repaired.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["summary"]["PASS"] == 1 and report["summary"]["PENDING"] == 11
    assert len(report["history"]) == 2
    assert report["history"][-1]["event"] == "repair_summary"
    assert report["history"][-1]["automatic"] is True
    assert run("validate", "--report", str(report_path)).returncode == 0

    finalized = run("finalize", "--report", str(report_path))
    assert finalized.returncode == 0, finalized.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["closed_at"]
    assert report["release_authorization"] == "NO_FINAL_RELEASE_AUTHORIZATION"
    assert run("validate", "--report", str(report_path)).returncode == 0
    immutable = run("record", "--report", str(report_path), "--check", "uia", "--status", "FAIL", "--method", "post-close")
    assert immutable.returncode != 0 and "finalizada" in immutable.stderr

print("RC6 PHYSICAL VALIDATION INTEGRITY TEST OK: initial summary, read-only validate, explicit repair, PASS evidence/confirmation, history, finalization and authorization are consistent.")
