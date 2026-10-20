from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "tools" / "gaia_benchmark.py"

with tempfile.TemporaryDirectory(prefix="gaia_rc6_benchmark_contract_") as tmp:
    out = Path(tmp)
    json_path = out / "benchmark.json"
    markdown_path = out / "benchmark.md"
    result = subprocess.run(
        [sys.executable, str(BENCHMARK), "--count", "200", "--iterations", "30", "--json-out", str(json_path), "--markdown-out", str(markdown_path)],
        cwd=ROOT,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

assert payload["benchmark"] == "gaia_rc6_bounded"
assert payload["status"] == "PASS"
assert payload["fixture"] == {"memory_items": 200, "retrieval_iterations": 30, "temporary_sqlite": True}
assert payload["governor"]["iterations"] == 30
for group in (payload["memory"]["save"], payload["memory"]["retrieve"], payload["governor"]["observe"]):
    assert set(group) == {"mean_ms", "median_ms", "p95_ms", "max_ms", "total_ms"}
    assert all(isinstance(group[key], (int, float)) and group[key] >= 0 for key in group)
    assert group["median_ms"] <= group["p95_ms"] <= group["max_ms"]
assert payload["side_effects"] == {
    "read_only_host": True,
    "ollama_started": False,
    "model_downloaded": False,
    "hardware_mutated": False,
    "services_started": False,
}
assert "# GAIA-AI RC6 bounded benchmark" in markdown
for label in ("Mean ms", "Median ms", "p95 ms", "Max ms", "Total ms", "Memory items", "Retrieval iterations", "Governor iterations"):
    assert label in markdown
assert "Ollama started / model downloaded | False / False" in markdown
assert "Hardware mutated / services started | False / False" in markdown
assert "gaia_rc4" not in markdown and "RC4" not in markdown

print("RC6 BENCHMARK CONTRACT TEST OK: bounded fixtures, percentile fields, JSON/Markdown agreement and zero side effects hold.")
