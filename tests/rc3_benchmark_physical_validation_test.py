from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
with tempfile.TemporaryDirectory(prefix="gaia_rc3_contract_") as tmp:
    out = Path(tmp)
    benchmark = subprocess.run([
        sys.executable, str(ROOT / "tools" / "gaia_benchmark.py"), "--count", "20", "--iterations", "5",
        "--json-out", str(out / "benchmark.json"), "--markdown-out", str(out / "benchmark.md"),
    ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert benchmark.returncode == 0, benchmark.stderr
    result = json.loads((out / "benchmark.json").read_text(encoding="utf-8"))
    assert result["status"] == "PASS"
    assert result["read_only_host"] is True and result["ollama_started"] is False
    assert result["model_downloaded"] is False and result["hardware_mutated"] is False
    assert result["fixture"] == {"memory_items": 20, "retrieval_iterations": 5, "temporary_sqlite": True}
    assert "PENDING" in (out / "benchmark.md").read_text(encoding="utf-8")

    physical = subprocess.run([
        sys.executable, str(ROOT / "tools" / "physical_validation.py"), "--output", str(out / "physical.md"),
        "--json-output", str(out / "physical.json"),
    ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert physical.returncode == 0, physical.stderr
    report = json.loads((out / "physical.json").read_text(encoding="utf-8"))
    assert report["operator_confirmed"] is False and report["sandbox_measurements"] is False
    assert all(item["status"] == "PENDING" for item in report["checks"])
    assert "No production" in (out / "physical.md").read_text(encoding="utf-8")

print("RC3 BENCHMARK/PHYSICAL VALIDATION TEST OK: bounded benchmark is read-only and physical readiness remains PENDING by default.")
