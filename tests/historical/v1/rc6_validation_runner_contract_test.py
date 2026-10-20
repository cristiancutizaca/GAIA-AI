from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "validate_rc6.py"
ENV = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}

def run(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(RUNNER), *args], cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=timeout)

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

with tempfile.TemporaryDirectory(prefix="gaia_rc6_runner_contract_") as temp:
    out = Path(temp)
    preflight = run("--preflight", "--output-dir", str(out / "preflight"))
    assert preflight.returncode in {0, 1}, preflight.stderr
    report = json.loads((out / "preflight" / "validation.json").read_text(encoding="utf-8"))
    assert report["runner"] == "gaia_rc6_validator"
    assert report["release"] == "1.0-RC6"
    assert report["side_effect_policy"] == {"hardware_mutated": False, "models_downloaded": False, "ollama_started": False, "services_started": False, "shell": False}
    assert report["steps"][0]["name"] == "preflight"
    assert report["steps"][0]["status"] in {"PASS", "DEPENDENCY_MISSING", "FAIL"}
    assert (out / "preflight" / "validation.md").is_file()

    package = run("--package-gate", "--output-dir", str(out / "package"))
    assert package.returncode == 0, package.stderr + package.stdout + ((out / "package" / "package_gate.log").read_text(encoding="utf-8") if (out / "package" / "package_gate.log").is_file() else "")
    package_report = json.loads((out / "package" / "validation.json").read_text(encoding="utf-8"))
    assert package_report["steps"][0]["name"] == "package_gate"
    assert package_report["steps"][0]["status"] == "PASS"

    physical = run("--physical-template", "--output-dir", str(out / "physical"))
    assert physical.returncode == 0, physical.stderr
    physical_report = json.loads((out / "physical" / "validation.json").read_text(encoding="utf-8"))
    assert physical_report["steps"][0]["status"] == "PENDING"
    assert any(path.name.startswith("physical_validation_RC6_") for path in (out / "physical" / "physical_contract-evidence").glob("*.json"))

    blocked = run("--install-dependencies", "--output-dir", str(out / "blocked"))
    assert blocked.returncode != 0
    blocked_report = json.loads((out / "blocked" / "validation.json").read_text(encoding="utf-8"))
    assert [step["name"] for step in blocked_report["steps"]] == ["package_gate", "preflight_initial", "install_dependencies"]
    assert blocked_report["steps"][0]["status"] == "PASS"
    assert blocked_report["steps"][-1]["status"] == "BLOCKED"

    runner_text = RUNNER.read_text(encoding="utf-8")
    assert "validate_rc4.py" not in runner_text and "gaia_rc4_validator" not in runner_text
    assert "tools/validate_rc6.py" in runner_text and "gaia_rc6_validator" in runner_text
    for report_path in out.rglob("*.json"):
        assert str(ROOT) not in report_path.read_text(encoding="utf-8")

print("RC6 VALIDATION RUNNER CONTRACT TEST OK: package-first, dependency boundary, RC6 identity, external evidence, bounded modes and side-effect policy hold.")
