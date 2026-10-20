from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "validate_rc6.py"
ENV = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}


def invoke(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


with tempfile.TemporaryDirectory(prefix="gaia_rc6_legacy_named_runner_contract_") as tmp:
    out = Path(tmp)
    preflight = invoke("--preflight", "--output-dir", str(out / "preflight"))
    assert preflight.returncode in {0, 1}, preflight.stderr
    report = json.loads((out / "preflight" / "validation.json").read_text(encoding="utf-8"))
    assert report["runner"] == "gaia_rc6_validator"
    assert report["release"] == "1.0-RC6"
    assert report["side_effect_policy"] == {
        "hardware_mutated": False,
        "models_downloaded": False,
        "ollama_started": False,
        "services_started": False,
        "shell": False,
    }
    assert report["steps"][0]["name"] == "preflight"
    assert report["steps"][0]["status"] in {"PASS", "DEPENDENCY_MISSING", "FAIL"}
    assert (out / "preflight" / "validation.md").is_file()

    package = invoke("--package-gate", "--output-dir", str(out / "package"))
    assert package.returncode == 0, package.stderr + package.stdout + ((out / "package" / "package_gate.log").read_text(encoding="utf-8") if (out / "package" / "package_gate.log").is_file() else "")
    package_report = json.loads((out / "package" / "validation.json").read_text(encoding="utf-8"))
    assert package_report["steps"][0]["name"] == "package_gate"
    assert package_report["steps"][0]["status"] == "PASS"

    physical = invoke("--physical-template", "--output-dir", str(out / "physical"))
    assert physical.returncode == 0, physical.stderr
    physical_report = json.loads((out / "physical" / "validation.json").read_text(encoding="utf-8"))
    assert physical_report["steps"][0]["status"] == "PENDING"
    assert any(path.name.startswith("physical_validation_RC6_") for path in (out / "physical" / "physical_contract-evidence").glob("*.json"))

    blocked = invoke("--install-dependencies", "--output-dir", str(out / "blocked"))
    assert blocked.returncode != 0
    blocked_report = json.loads((out / "blocked" / "validation.json").read_text(encoding="utf-8"))
    assert [step["name"] for step in blocked_report["steps"]] == ["package_gate", "preflight_initial", "install_dependencies"]
    assert blocked_report["steps"][-1]["status"] == "BLOCKED"

    nested_venv = out / "nested-venv"
    created = subprocess.run([sys.executable, "-m", "venv", str(nested_venv)], capture_output=True, text=True, timeout=120)
    assert created.returncode == 0, created.stderr
    nested_python = nested_venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    transitioned = invoke(
        "--preflight",
        "--venv-ready",
        "--venv-path",
        str(nested_python),
        "--output-dir",
        str(out / "transition"),
    )
    assert transitioned.returncode in {0, 1}, transitioned.stderr
    transition_report = json.loads((out / "transition" / "validation.json").read_text(encoding="utf-8"))
    assert transition_report["environment"]["virtualenv_active"] is True
    assert transition_report["environment"]["sys_prefix"] == str(nested_venv)
    assert transition_report["environment"]["python_executable"].startswith(str(nested_venv))

runner_text = RUNNER.read_text(encoding="utf-8")
assert "validate_rc4.py" not in runner_text and "gaia_rc4_validator" not in runner_text
assert "tools/validate_rc6.py" in runner_text and "gaia_rc6_validator" in runner_text
assert "os.execv" in runner_text and "shell=False" in runner_text

print("RC6 VALIDATION RUNNER CONTRACT TEST OK: package-first, dependency boundary, external venv transition, RC6 identity and side-effect policy hold.")
