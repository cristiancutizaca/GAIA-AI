"""Auditable RC6 validation runner with explicit dependency transition."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "product": "GAIA-AI",
    "release": "1.0-RC6",
    "version": "1.0.0-rc6-pc",
    "protocol": "1.0-RC6",
    "schema_min": 8,
    "schema_max": 9,
}
REQUIRED_REQUIREMENT_FILES = (ROOT / "lumen-core" / "requirements.txt", ROOT / "lumen-pc" / "requirements.txt")
IMPORT_ALIASES = {
    "edge-tts": "edge_tts",
    "openai-whisper": "whisper",
    "pillow": "PIL",
    "python-dotenv": "dotenv",
    "python-multipart": "multipart",
    "uvicorn": "uvicorn",
}
SECRET_PATTERNS = (
    (re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(LUMEN_SECRET\s*=\s*)[^\s]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:api[_ -]?key|token|secret|password)\s*[:=]\s*)[^\s]+"), r"\1[REDACTED]"),
)
ALLOWED_STATUSES = {"PASS", "FAIL", "PENDING", "SKIP", "BLOCKED", "DEPENDENCY_MISSING", "NOT_MEASURED", "TIMEOUT"}


@dataclass
class Step:
    name: str
    status: str
    elapsed_ms: float = 0.0
    returncode: int | None = None
    detail: str = ""
    count: int | None = None
    passed: int | None = None
    failed: int | None = None
    skipped: int | None = None
    pending: int | None = None
    timeout: int | None = None

    def public(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None and value != ""}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(text: str) -> str:
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def safe_external_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        return resolved
    raise ValueError("La evidencia debe estar fuera del árbol RC6")


def run_command(command: list[str], *, cwd: Path, timeout: int, log_path: Path | None = None) -> tuple[int, float, bool]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
        output = redact(completed.stdout or "")
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(output, encoding="utf-8")
        return completed.returncode, (time.perf_counter() - started) * 1000.0, False
    except subprocess.TimeoutExpired as error:
        output = redact((error.stdout or "") if isinstance(error.stdout, str) else "")
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(output + "\n[TIMEOUT]\n", encoding="utf-8")
        return 124, (time.perf_counter() - started) * 1000.0, True


def parse_requirement(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("-"):
        return None
    match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?(?:[<>=!~].*)?$", line)
    if not match:
        return None
    package = match.group(1)
    return package, IMPORT_ALIASES.get(package.lower(), package.replace("-", "_"))


def dependency_report(interpreter: str | None = None) -> dict[str, Any]:
    specs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for requirements in REQUIRED_REQUIREMENT_FILES:
        if not requirements.is_file():
            continue
        for line in requirements.read_text(encoding="utf-8", errors="replace").splitlines():
            parsed = parse_requirement(line)
            if parsed is None or parsed[0].lower() in seen:
                continue
            specs.append(parsed)
            seen.add(parsed[0].lower())
    target = str(Path(interpreter).expanduser().absolute()) if interpreter else str(Path(sys.executable).absolute())
    probe_code = """import importlib.metadata, importlib.util, json, sys
specs = json.loads(sys.argv[1])
packages = []
for package, module in specs:
    present = importlib.util.find_spec(module) is not None
    try:
        version = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        version = None
    packages.append({'package': package, 'module': module, 'installed': present, 'version': version})
print(json.dumps({'python': sys.executable, 'prefix': sys.prefix, 'virtualenv_active': sys.prefix != sys.base_prefix, 'packages': packages}, sort_keys=True))
"""
    try:
        completed = subprocess.run([target, "-c", probe_code, json.dumps(specs)], cwd=str(ROOT), env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", timeout=30, shell=False, check=False)
        probe_output = completed.stdout.strip()
        payload = json.loads(probe_output) if completed.returncode == 0 else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        payload = {}
        completed = None
    packages = payload.get("packages", []) if isinstance(payload, dict) else []
    if not packages:
        packages = [{"package": package, "module": module, "installed": False, "version": None} for package, module in specs]
    missing = [item["package"] for item in packages if not item.get("installed")]
    interpreter_facts = {
        "returncode": completed.returncode if completed is not None else 1,
        "python": payload.get("python", target) if isinstance(payload, dict) else target,
        "prefix": payload.get("prefix") if isinstance(payload, dict) else None,
        "virtualenv_active": payload.get("virtualenv_active") if isinstance(payload, dict) else False,
    }
    status = "PASS" if completed is not None and completed.returncode == 0 and not missing else "DEPENDENCY_MISSING"
    return {"status": status, "packages": packages, "missing": missing, "interpreter_facts": interpreter_facts}


def read_manifest_at(root: Path) -> dict[str, Any]:
    path = root / "release_manifest.json"
    if not path.is_file():
        return {"status": "FAIL", "error": "release_manifest.json missing"}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"status": "FAIL", "error": type(error).__name__}
    mismatches = {key: {"expected": value, "actual": manifest.get(key)} for key, value in EXPECTED.items() if manifest.get(key) != value}
    if manifest.get("manifest_format") != 1 or manifest.get("deterministic") is not True:
        mismatches["manifest_format_or_deterministic"] = True
    return {"status": "PASS" if not mismatches else "FAIL", "mismatches": mismatches}


def preflight(interpreter: str | None = None) -> tuple[Step, dict[str, Any]]:
    started = time.perf_counter()
    dependencies = dependency_report(interpreter)
    manifest = read_manifest_at(ROOT)
    required = [
        ".env.example", ".gitignore", "README.md", "MODIFIED_FILES.md", "TEST_REPORT.md", "FINAL_VALIDATION.txt",
        "RC6_REQUIREMENTS.md", "PERFORMANCE_RC6_REPORT.md", "PERFORMANCE_COMPARISON_RC5_RC6.md", "PHYSICAL_VALIDATION_RC6.md",
        "WINDOWS_RC6_VALIDATION_CHECKLIST.md", "MIGRATION_MATRIX_RC5_RC6.md", "RELEASE_DECISION_RC6.md",
        "UPDATE_ROLLBACK_GUIDE.md", "DOCUMENT_CLASSIFICATION_RC6.md", "tools/validate_rc6.py", "tools/gaia_migrate.py", "tools/build_release.py", "tools/build_docs.py",
    ]
    missing = [name for name in required if not (ROOT / name).is_file()]
    interpreter_facts = dependencies.get("interpreter_facts", {})
    report = {
        "python": platform.python_version(),
        "python_executable": str(interpreter_facts.get("python") or Path(sys.executable).absolute()),
        "sys_prefix": str(interpreter_facts.get("prefix") or sys.prefix),
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "virtualenv_active": bool(interpreter_facts.get("virtualenv_active", sys.prefix != sys.base_prefix)),
        "manifest": manifest,
        "identity": {"product": "GAIA-AI", "release": "1.0-RC6", "version": "1.0.0-rc6-pc", "protocol": "1.0-RC6", "android": "1.0.0-rc6+1", "schema": "8-9"},
        "dependencies": dependencies,
        "missing_required_files": missing,
        "safe_defaults": {"installs_dependencies": False, "starts_ollama": False, "downloads_models": False, "mutates_hardware": False},
    }
    failures = bool(missing) or manifest["status"] != "PASS" or dependencies["status"] == "DEPENDENCY_MISSING"
    detail = f"manifest={manifest['status']}; dependencies={dependencies['status']}; missing_files={len(missing)}; venv={report['virtualenv_active']}"
    status = "DEPENDENCY_MISSING" if dependencies["status"] == "DEPENDENCY_MISSING" else ("FAIL" if failures else "PASS")
    return Step("preflight", status, (time.perf_counter() - started) * 1000.0, detail=detail), report


def package_gate(out_dir: Path, root: Path = ROOT, interpreter: str | None = None) -> Step:
    started = time.perf_counter()
    python = interpreter or sys.executable
    rc, elapsed, timed_out = run_command([python, str(root / "tests" / "release_package_test.py")], cwd=root, timeout=90, log_path=out_dir / "package_gate.log")
    return Step("package_gate", "TIMEOUT" if timed_out else ("PASS" if rc == 0 else "FAIL"), elapsed, rc, detail="release_package_test.py")


def compile_check(out_dir: Path, root: Path = ROOT) -> Step:
    started = time.perf_counter()
    paths = [path for directory in (root / "lumen-core", root / "lumen-pc", root / "tools", root / "tests") if directory.is_dir() for path in directory.rglob("*.py")]
    failures: list[str] = []
    for path in sorted(paths):
        try:
            compile(path.read_text(encoding="utf-8", errors="replace"), str(path), "exec")
        except (SyntaxError, UnicodeError, ValueError) as error:
            failures.append(f"{path.relative_to(root)}:{type(error).__name__}")
    (out_dir / "compile.log").write_text("\n".join(failures), encoding="utf-8")
    return Step("compile", "PASS" if not failures else "FAIL", (time.perf_counter() - started) * 1000.0, detail=f"files={len(paths)} failures={len(failures)}", count=len(paths), failed=len(failures), passed=len(paths) - len(failures))


def tests_run(out_dir: Path, timeout: int, root: Path = ROOT, interpreter: str | None = None, name: str = "tests") -> Step:
    python = interpreter or sys.executable
    tests = sorted(path for path in (root / "tests").glob("*_test.py") if path.name != "release_package_test.py")
    passed = failed = timed_out = 0
    rows: list[dict[str, Any]] = []
    log_dir = out_dir / ("test-logs" if name == "tests" else f"{name}-logs")
    for path in tests:
        rc, elapsed, did_timeout = run_command([python, str(path)], cwd=root, timeout=timeout, log_path=log_dir / f"{path.stem}.log")
        status = "TIMEOUT" if did_timeout else ("PASS" if rc == 0 else "FAIL")
        if status == "PASS":
            passed += 1
        elif status == "TIMEOUT":
            timed_out += 1
        else:
            failed += 1
        rows.append({"name": path.name, "status": status, "returncode": rc, "elapsed_ms": round(elapsed, 3)})
    result_path = out_dir / ("test-results.json" if name == "tests" else f"{name}-results.json")
    result_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    status = "PASS" if failed == 0 and timed_out == 0 else ("TIMEOUT" if timed_out else "FAIL")
    return Step(name, status, sum(row["elapsed_ms"] for row in rows), count=len(tests), passed=passed, failed=failed, skipped=0, timeout=timed_out, detail=result_path.name)


def benchmark_run(out_dir: Path, root: Path = ROOT, interpreter: str | None = None, name: str = "benchmark") -> Step:
    python = interpreter or sys.executable
    rc, elapsed, timed_out = run_command([python, str(root / "tools" / "gaia_benchmark.py"), "--count", "20", "--iterations", "5", "--json-out", str(out_dir / f"{name}.json"), "--markdown-out", str(out_dir / f"{name}.md")], cwd=root, timeout=120, log_path=out_dir / f"{name}.log")
    return Step(name, "TIMEOUT" if timed_out else ("PASS" if rc == 0 else "FAIL"), elapsed, rc, detail=f"external {name}.json/{name}.md")


def physical_contract(out_dir: Path, root: Path = ROOT, interpreter: str | None = None, name: str = "physical_contract") -> Step:
    python = interpreter or sys.executable
    physical_dir = out_dir / f"{name}-evidence"
    physical_dir.mkdir(parents=True, exist_ok=True)
    rc, elapsed, timed_out = run_command([python, str(root / "tools" / "physical_validation.py"), "new", "--output-dir", str(physical_dir)], cwd=root, timeout=30, log_path=out_dir / f"{name}.log")
    if rc != 0 or timed_out:
        return Step(name, "TIMEOUT" if timed_out else "FAIL", elapsed, rc, detail="physical new failed")
    reports = sorted(physical_dir.glob("physical_validation_RC6_*.json"))
    if not reports:
        return Step(name, "FAIL", elapsed, 1, detail="physical report missing")
    validate_rc, validate_elapsed, validate_timeout = run_command([python, str(root / "tools" / "physical_validation.py"), "validate", "--report", str(reports[-1])], cwd=root, timeout=30, log_path=out_dir / f"{name}-validate.log")
    status = "TIMEOUT" if validate_timeout else ("PENDING" if validate_rc == 0 else "FAIL")
    return Step(name, status, elapsed + validate_elapsed, validate_rc, detail="new report and read-only validate; 12 controls PENDING")


def document_contract(root: Path) -> Step:
    required = ["README.md", "CHANGELOG.md", "AUDIT.md", "TEST_REPORT.md", "FINAL_VALIDATION.txt", "KNOWN_LIMITATIONS.md", "MODIFIED_FILES.md", "RC6_REQUIREMENTS.md", "PERFORMANCE_RC6_REPORT.md", "PERFORMANCE_COMPARISON_RC5_RC6.md", "PHYSICAL_VALIDATION_RC6.md", "WINDOWS_RC6_VALIDATION_CHECKLIST.md", "MIGRATION_MATRIX_RC5_RC6.md", "RELEASE_DECISION_RC6.md", "SECURITY_MODEL.md", "THREAT_MODEL.md", "UPDATE_ROLLBACK_GUIDE.md", "DOCUMENT_CLASSIFICATION_RC6.md"]
    missing = [name for name in required if not (root / name).is_file()]
    errors: list[str] = []
    if not missing:
        active = {"README.md": "# GAIA-AI v1.0-RC6", "CHANGELOG.md": "# Changelog", "AUDIT.md": "# GAIA-AI v1.0-RC6 Audit", "SECURITY_MODEL.md": "# GAIA-AI v1.0-RC6 Security Model", "THREAT_MODEL.md": "# GAIA-AI v1.0-RC6 Threat Model", "KNOWN_LIMITATIONS.md": "# GAIA-AI v1.0-RC6 Known Limitations", "RC6_REQUIREMENTS.md": "# GAIA-AI v1.0-RC6 Requirements", "PERFORMANCE_RC6_REPORT.md": "# GAIA-AI v1.0-RC6 Performance and Reproducibility Report", "PERFORMANCE_COMPARISON_RC5_RC6.md": "# GAIA-AI v1.0-RC6 Performance Comparison", "PHYSICAL_VALIDATION_RC6.md": "# GAIA-AI v1.0-RC6 Physical Validation", "WINDOWS_RC6_VALIDATION_CHECKLIST.md": "# GAIA-AI v1.0-RC6 Windows Validation Checklist", "MIGRATION_MATRIX_RC5_RC6.md": "# Migration Matrix RC5 → RC6", "RELEASE_DECISION_RC6.md": "# GAIA-AI v1.0-RC6 Release Decision", "UPDATE_ROLLBACK_GUIDE.md": "# GAIA-AI v1.0-RC6 — Update, Migration and Rollback Guide", "DOCUMENT_CLASSIFICATION_RC6.md": "# GAIA-AI v1.0-RC6 Document Classification"}
        for name, heading in active.items():
            if not (root / name).read_text(encoding="utf-8").startswith(heading):
                errors.append(f"active_heading:{name}")
        old_docs = ["WINDOWS_FIRST_TEST_CHECKLIST.md", "PHYSICAL_VALIDATION_V100.md", "V100_PREPARATION.md", "GAIA_VAULT_MIGRATION.md", "PHYSICAL_VALIDATION_RC4.md", "RC4_REQUIREMENTS.md", "PHYSICAL_VALIDATION_RC5.md", "WINDOWS_RC5_VALIDATION_CHECKLIST.md"]
        for name in old_docs:
            path = root / name
            if path.is_file():
                historical_text = path.read_text(encoding="utf-8")
                if not historical_text.startswith("HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS"):
                    errors.append(f"historical_warning:{name}")
                if "For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md." not in historical_text:
                    errors.append(f"historical_link:{name}")
        guide = (root / "UPDATE_ROLLBACK_GUIDE.md").read_text(encoding="utf-8")
        if "1.0.0-rc4" in guide or "GAIA-AI-v1.0-RC4" in guide:
            errors.append("active_guide_old_identity")
    status = "PASS" if not missing and not errors else "FAIL"
    return Step("documentation_contract", status, detail=f"missing={len(missing)} errors={len(errors)}")


def forbidden_audit(root: Path) -> Step:
    forbidden: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in {".env", ".venv", "__pycache__", "data", "logs", "backups", "tokens", "secrets", "audio", "models"} for part in rel.parts) or path.suffix.lower() in {".db", ".sqlite", ".pyc", ".log", ".pem", ".key", ".token", ".apk", ".aab"}:
            forbidden.append(str(rel))
    return Step("file_audit", "PASS" if not forbidden else "FAIL", detail=f"forbidden_files={len(forbidden)}")


def security_audit(root: Path = ROOT) -> Step:
    patterns = {
        "shell_true": re.compile(r"\bshell\s*=\s*True\b"),
        "os_system": re.compile(r"\bos\.system\s*\("),
        "eval": re.compile(r"\beval\s*\("),
        "exec": re.compile(r"(?<!\.)\bexec\s*\("),
        "invoke_expression": re.compile(r"Invoke-Expression", re.I),
        "auto_model_download": re.compile(r"(?:subprocess\.(?:run|Popen|call)|os\.system|Start-Process|Invoke-Expression).*?(?:download_model|pull_model|ollama\s+pull|huggingface.*download)", re.I),
    }
    scanned = 0
    findings: list[str] = []
    for path in root.rglob("*"):
        if "tests" in path.relative_to(root).parts:
            continue
        if path.name == "validate_rc6.py":
            continue
        if not path.is_file() or path.suffix.lower() not in {".py", ".ps1", ".bat", ".dart", ".kt", ".kts"}:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        for category, pattern in patterns.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(root)}:{category}")
    return Step("security_audit", "PASS" if not findings else "FAIL", detail=f"files={scanned} findings={len(findings)}")


def clean_extraction(out_dir: Path, archive: Path, interpreter: str | None = None) -> list[Step]:
    python = interpreter or sys.executable
    if not archive.is_file():
        return [Step("clean_extraction_package_gate", "FAIL", detail="archive not found")]
    steps: list[Step] = []
    try:
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted(name for name in names if name.startswith("/") or ".." in Path(name).parts or any(part == "" for part in Path(name).parts))
            roots = sorted({name.split("/", 1)[0] for name in names if "/" in name})
            steps.append(Step("clean_extraction_archive_integrity", "PASS" if bundle.testzip() is None else "FAIL", count=len(names), detail=f"members={len(names)}"))
            steps.append(Step("clean_extraction_unique_paths", "PASS" if not duplicates and not unsafe else "FAIL", detail=f"duplicates={len(duplicates)} unsafe={len(unsafe)}"))
            if roots != ["GAIA-AI-v1.0-RC6"]:
                steps.append(Step("clean_extraction_package_root", "FAIL", detail=f"roots={roots}"))
                return steps
            with tempfile.TemporaryDirectory(prefix="gaia_rc6_clean_extract_") as temp:
                bundle.extractall(temp)
                for info in bundle.infolist():
                    destination = Path(temp) / info.filename
                    if destination.is_file():
                        mode = (info.external_attr >> 16) & 0o777
                        if mode:
                            os.chmod(destination, mode)
                root = Path(temp) / "GAIA-AI-v1.0-RC6"
                gate = package_gate(out_dir / "clean_extraction", root, python)
                gate.name = "clean_extraction_package_gate"
                steps.append(gate)
                manifest = read_manifest_at(root)
                steps.append(Step("clean_extraction_manifest", manifest["status"], detail=json.dumps(manifest.get("mismatches", {}), sort_keys=True)))
                initial_file_audit = forbidden_audit(root)
                initial_file_audit.name = "clean_extraction_file_audit"
                steps.append(initial_file_audit)
                clean_security = security_audit(root)
                clean_security.name = "clean_extraction_security_audit"
                steps.append(clean_security)
                compile_step = compile_check(out_dir / "clean_extraction", root)
                compile_step.name = "clean_extraction_compile"
                steps.append(compile_step)
                test_step = tests_run(out_dir / "clean_extraction", 120, root, python, "clean_extraction_tests")
                steps.append(test_step)
                bench_step = benchmark_run(out_dir / "clean_extraction", root, python, "clean_extraction_benchmark")
                steps.append(bench_step)
                physical_step = physical_contract(out_dir / "clean_extraction", root, python, "clean_extraction_physical_contract")
                steps.append(physical_step)
                steps.append(document_contract(root))
                steps[-1].name = "clean_extraction_documentation"
    except (OSError, zipfile.BadZipFile) as error:
        steps.append(Step("clean_extraction_archive_integrity", "FAIL", detail=type(error).__name__))
    return steps


def venv_python(out_dir: Path) -> Path:
    return out_dir / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def venv_is_usable(path: Path) -> bool:
    if not path.is_file():
        return False
    code = "import sys; assert sys.prefix != sys.base_prefix; print(sys.executable)"
    rc, _, timed_out = run_command([str(path), "-c", code], cwd=ROOT, timeout=30)
    return rc == 0 and not timed_out


def install_dependencies(out_dir: Path, confirm: bool, recreate: bool) -> tuple[Step, Path | None]:
    started = time.perf_counter()
    if not confirm:
        return Step("install_dependencies", "BLOCKED", detail="requires explicit --confirm-install"), None
    venv = out_dir / ".venv"
    if venv.exists() and recreate:
        shutil.rmtree(venv)
    vpy = venv_python(out_dir)
    stamp = out_dir / ".rc6-venv-ready"
    if vpy.is_file() and stamp.is_file() and venv_is_usable(vpy):
        return Step("install_dependencies", "PASS", (time.perf_counter() - started) * 1000.0, detail="existing compatible external venv reused; no reinstall"), vpy
    if venv.exists():
        # A partial or foreign venv is never silently trusted.
        shutil.rmtree(venv)
    rc, elapsed, timed_out = run_command([sys.executable, "-m", "venv", str(venv)], cwd=ROOT, timeout=120, log_path=out_dir / "venv.log")
    if rc != 0 or timed_out:
        return Step("install_dependencies", "TIMEOUT" if timed_out else "FAIL", elapsed, rc, detail="venv creation failed"), None
    vpy = venv_python(out_dir)
    rc, bootstrap_elapsed, timed_out = run_command([str(vpy), "-m", "pip", "install", "setuptools<70", "wheel"], cwd=ROOT, timeout=180, log_path=out_dir / "pip-bootstrap.log")
    if rc != 0 or timed_out:
        return Step("install_dependencies", "TIMEOUT" if timed_out else "FAIL", elapsed + bootstrap_elapsed, rc, detail="private venv bootstrap failed"), None
    requirements = [str(path) for path in REQUIRED_REQUIREMENT_FILES]
    rc, install_elapsed, timed_out = run_command([str(vpy), "-m", "pip", "install", "--no-build-isolation", "-r", requirements[0], "-r", requirements[1]], cwd=ROOT, timeout=900, log_path=out_dir / "pip-install.log")
    if rc != 0 or timed_out:
        return Step("install_dependencies", "TIMEOUT" if timed_out else "FAIL", elapsed + bootstrap_elapsed + install_elapsed, rc, detail="dependency installation failed"), None
    rc, freeze_elapsed, timed_out = run_command([str(vpy), "-m", "pip", "freeze"], cwd=ROOT, timeout=60, log_path=out_dir / "pip-freeze.txt")
    if rc != 0 or timed_out:
        return Step("install_dependencies", "TIMEOUT" if timed_out else "FAIL", elapsed + bootstrap_elapsed + install_elapsed + freeze_elapsed, rc, detail="pip freeze failed"), None
    stamp.write_text(f"python={vpy.absolute()}\nprefix={venv.absolute()}\n", encoding="utf-8")
    return Step("install_dependencies", "PASS", elapsed + bootstrap_elapsed + install_elapsed + freeze_elapsed, rc, detail="new external venv, post-install execution required, pip-freeze.txt"), vpy


def markdown_report(report: dict[str, Any]) -> str:
    lines = ["# GAIA-AI v1.0-RC6 validation report", "", "> Bounded automated evidence only; physical readiness is never inferred from Linux, mocks, imports or local APIs.", "", f"Generated UTC: `{report['generated_at']}`", "", "| Step | Status | Elapsed ms | Detail |", "|---|---|---:|---|"]
    for item in report["steps"]:
        lines.append(f"| `{item['name']}` | **{item['status']}** | {item.get('elapsed_ms', 0):.3f} | {redact(str(item.get('detail', '')))} |")
    lines += ["", "## Environment", "", f"Python `{report['environment'].get('python')}`, executable `{redact(str(report['environment'].get('python_executable')) )}`, prefix `{redact(str(report['environment'].get('sys_prefix')) )}`, OS `{report['environment'].get('os')}`, virtualenv active `{report['environment'].get('virtualenv_active')}`.", "", "Installation occurs only after package gate and explicit confirmation. The runner uses list-form subprocesses with shell=False and timeouts; it never starts Ollama, downloads models, mutates hardware or leaves services running.", "", "Physical controls remain PENDING/NOT_MEASURED until confirmed by the operator on Windows. This report does not authorize a final release.", ""]
    return "\n".join(lines)


def build_report(steps: list[Step], preflight_data: dict[str, Any]) -> dict[str, Any]:
    return {"runner": "gaia_rc6_validator", "generated_at": utc_now(), "release": "1.0-RC6", "environment": preflight_data, "steps": [step.public() for step in steps], "physical_claim": "PENDING unless separately confirmed by the operator", "side_effect_policy": {"ollama_started": False, "models_downloaded": False, "hardware_mutated": False, "services_started": False, "shell": False}}


def write_report(report: dict[str, Any], out_dir: Path, json_out: Path | None, markdown_out: Path | None) -> None:
    jp = safe_external_dir(json_out or (out_dir / "validation.json"))
    mp = safe_external_dir(markdown_out or (out_dir / "validation.md"))
    jp.parent.mkdir(parents=True, exist_ok=True)
    mp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mp.write_text(markdown_report(report), encoding="utf-8")


def overall_status(steps: list[Step]) -> str:
    if any(step.status in {"FAIL", "TIMEOUT", "BLOCKED"} for step in steps):
        return "FAIL"
    missing = [step for step in steps if step.status == "DEPENDENCY_MISSING"]
    if missing:
        initial_only = all(step.name == "preflight_initial" for step in missing)
        installed = any(step.name == "install_dependencies" and step.status == "PASS" for step in steps)
        post_pass = any(step.name == "preflight" and step.status == "PASS" for step in steps)
        if not (initial_only and installed and post_pass):
            return "FAIL"
    return "PASS" if all(step.status in {"PASS", "PENDING", "SKIP", "DEPENDENCY_MISSING"} for step in steps) else "FAIL"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safe, bounded GAIA-AI v1.0-RC6 validation runner")
    modes = parser.add_argument_group("validation modes")
    for name in ("preflight", "package_gate", "compile", "tests", "benchmark", "physical_template", "clean_extraction", "install_dependencies", "all"):
        modes.add_argument(f"--{name.replace('_', '-')}", action="store_true")
    parser.add_argument("--confirm-install", action="store_true")
    parser.add_argument("--recreate-venv", action="store_true")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--test-timeout", type=int, default=90)
    parser.add_argument("--venv-ready", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--venv-path", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    out_dir = safe_external_dir(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = any(getattr(args, key) for key in ("preflight", "package_gate", "compile", "tests", "benchmark", "physical_template", "clean_extraction", "install_dependencies", "all"))
    if not selected:
        parser.error("selecciona un modo de validación")
    timeout = max(1, min(300, args.test_timeout))
    steps: list[Step] = []
    preflight_data: dict[str, Any] = {"python": platform.python_version(), "python_executable": str(Path(sys.executable).resolve()), "sys_prefix": sys.prefix, "os": platform.system(), "architecture": platform.machine(), "virtualenv_active": sys.prefix != sys.base_prefix}
    full = args.all or (args.install_dependencies and args.venv_ready)
    requires_package_first = full or args.install_dependencies or args.clean_extraction
    if requires_package_first:
        gate = package_gate(out_dir)
        steps.append(gate)
        if gate.status != "PASS":
            report = build_report(steps, preflight_data)
            write_report(report, out_dir, args.json_out, args.markdown_out)
            print(json.dumps({"status": "FAIL", "json": str(args.json_out or out_dir / 'validation.json'), "markdown": str(args.markdown_out or out_dir / 'validation.md'), "steps": len(steps)}, sort_keys=True))
            return 1
    if args.install_dependencies and not args.venv_ready:
        initial_step, initial_data = preflight()
        steps.append(Step("preflight_initial", initial_step.status, initial_step.elapsed_ms, initial_step.returncode, initial_step.detail))
        preflight_data["preflight_initial"] = initial_data
        install_step, resolved = install_dependencies(out_dir, args.confirm_install, args.recreate_venv)
        steps.append(install_step)
        if install_step.status != "PASS" or resolved is None:
            report = build_report(steps, preflight_data)
            write_report(report, out_dir, args.json_out, args.markdown_out)
            print(json.dumps({"status": "FAIL", "json": str(args.json_out or out_dir / 'validation.json'), "markdown": str(args.markdown_out or out_dir / 'validation.md'), "steps": len(steps)}, sort_keys=True))
            return 1
        initial_public = initial_step.public()
        initial_public["name"] = "preflight_initial"
        transition = {"preflight_initial": initial_data, "preflight_initial_step": initial_public, "install": install_step.public(), "venv_python": str(resolved.absolute()), "venv_prefix": str(resolved.parent.parent.absolute())}
        (out_dir / "install-transition.json").write_text(json.dumps(transition, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        new_args = list(sys.argv[1:] if argv is None else argv)
        new_args = [item for item in new_args if item not in {"--venv-ready"}]
        new_args += ["--venv-ready", "--venv-path", str(resolved)]
        os.execv(str(resolved), [str(resolved), str(Path(__file__).resolve()), *new_args])
    interpreter = str(args.venv_path.expanduser().absolute()) if args.venv_ready and args.venv_path else sys.executable
    if args.venv_ready:
        # --venv-path permite que un proceso padre fuera del entorno valide un
        # intérprete externo ya creado. La comprobación de aislamiento debe
        # aplicarse al intérprete indicado, no al sys.prefix del padre.
        if not venv_is_usable(Path(interpreter)):
            raise SystemExit("venv transition invalid")
        transition_path = out_dir / "install-transition.json"
        if transition_path.is_file():
            transition = json.loads(transition_path.read_text(encoding="utf-8"))
            preflight_data["preflight_initial"] = transition.get("preflight_initial", {})
            if transition.get("preflight_initial_step"):
                steps.append(Step(**transition["preflight_initial_step"]))
            if transition.get("install"):
                steps.append(Step(**transition["install"]))
        post_step, post_data = preflight(interpreter)
        steps.append(post_step)
        preflight_data["preflight_post"] = post_data
        preflight_data.update(post_data)
    elif full or args.preflight:
        step, data = preflight()
        steps.append(step)
        preflight_data.update(data)
    if args.package_gate and not requires_package_first:
        steps.append(package_gate(out_dir, interpreter=interpreter))
    if full:
        steps.append(document_contract(ROOT))
        steps.append(forbidden_audit(ROOT))
        steps.append(security_audit(ROOT))
    if args.compile or full:
        steps.append(compile_check(out_dir))
    if args.tests or full:
        steps.append(tests_run(out_dir, timeout, interpreter=interpreter))
    if args.benchmark or full:
        steps.append(benchmark_run(out_dir, interpreter=interpreter))
    if args.physical_template or full:
        steps.append(physical_contract(out_dir, interpreter=interpreter))
    if args.clean_extraction or full:
        if args.archive:
            steps.extend(clean_extraction(out_dir, args.archive.expanduser().resolve(), interpreter))
        else:
            steps.append(Step("clean_extraction", "SKIP", detail="no --archive supplied"))
    if args.install_dependencies and args.venv_ready:
        # The install step is already represented by install-transition.json; the
        # post-install preflight above proves that this interpreter is in use.
        pass
    report = build_report(steps, preflight_data)
    write_report(report, out_dir, args.json_out, args.markdown_out)
    status = overall_status(steps)
    print(json.dumps({"status": status, "json": str(args.json_out or out_dir / "validation.json"), "markdown": str(args.markdown_out or out_dir / "validation.md"), "steps": len(steps)}, ensure_ascii=False, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
