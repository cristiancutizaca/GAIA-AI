from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

ACTIVE_FILES = (
    ".env.example", ".gitignore", "install-gaia.ps1", "validate-gaia-rc6.ps1", "setup-windows.bat",
    "README.md", "CHANGELOG.md", "AUDIT.md", "TEST_REPORT.md", "FINAL_VALIDATION.txt", "KNOWN_LIMITATIONS.md",
    "MODIFIED_FILES.md", "RC6_REQUIREMENTS.md", "PERFORMANCE_RC6_REPORT.md", "PERFORMANCE_COMPARISON_RC5_RC6.md",
    "PHYSICAL_VALIDATION_RC6.md", "WINDOWS_RC6_VALIDATION_CHECKLIST.md", "MIGRATION_MATRIX_RC5_RC6.md",
    "RELEASE_DECISION_RC6.md", "SECURITY_MODEL.md", "THREAT_MODEL.md", "UPDATE_ROLLBACK_GUIDE.md",
    "DOCUMENT_CLASSIFICATION_RC6.md", "release_manifest.json", "tools/build_release.py", "tools/build_docs.py",
    "tools/gaia_benchmark.py", "tools/gaia_migrate.py", "tools/physical_validation.py", "tools/validate_rc6.py",
    "tests/release_package_test.py", "tests/rc6_identity_documentation_test.py", "tests/rc6_document_parity_test.py",
    "tests/rc6_physical_validation_test.py", "tests/rc6_validation_runner_test.py", "tests/rc6_validation_runner_contract_test.py",
    "tests/rc6_migrator_cli_contract_test.py", "tests/rc6_powershell_wrapper_contract_test.py", "tests/rc6_benchmark_contract_test.py",
    "tests/rc6_builder_contract_test.py",
)
REQUIRED_DIRS = ("lumen-core", "lumen-pc", "lumen-mobile", "tools", "tests")
HISTORICAL_WARNING_FILES = (
    "WINDOWS_FIRST_TEST_CHECKLIST.md", "PHYSICAL_VALIDATION_V100.md", "V100_PREPARATION.md", "GAIA_VAULT_MIGRATION.md",
    "PHYSICAL_VALIDATION_RC4.md", "RC4_REQUIREMENTS.md", "PHYSICAL_VALIDATION_RC5.md", "WINDOWS_RC5_VALIDATION_CHECKLIST.md",
    "RC5_REQUIREMENTS.md", "RC2_INDEPENDENT_FINDINGS_REPRO.md", "RC2_REQUIREMENTS.md", "RC3_REQUIREMENTS.md",
    "PHYSICAL_VALIDATION_WINDOWS.md", "ANDROID_BUILD_ATTEMPT.md", "MIGRATION_LUMEN_GAIA.md", "ROLLBACK.md", "SAFE_MODE.md",
    "V051_REQUIREMENTS.md", "V052_REQUIREMENTS.md", "V054_REQUIREMENTS.md", "V0541_REQUIREMENTS.md", "V0542_REQUIREMENTS.md",
    "V0543_REQUIREMENTS.md", "V060_REQUIREMENTS.md", "V061_REQUIREMENTS.md", "V062_REQUIREMENTS.md", "V070_REQUIREMENTS.md",
    "V071_REQUIREMENTS.md", "V072_REQUIREMENTS.md", "V080_REQUIREMENTS.md", "V080_DESIGN.md", "V081_REQUIREMENTS.md",
    "V090_REQUIREMENTS.md", "V091_REQUIREMENTS.md", "V092_REQUIREMENTS.md", "V090_INDEPENDENT_FINDINGS_REPRO.md",
)
WARNING = "HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS"
CURRENT_LINK = "For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md."
FORBIDDEN_NAMES = {".env", ".env.local", ".env.production", ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".gaia_processes.json"}
FORBIDDEN_DIRS = {"data", "logs", "backups", "GAIA_VAULT", "tokens", "secrets", "audio", "models", "build"}
FORBIDDEN_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".sqlite-journal", ".log", ".pyc", ".pyo", ".wav", ".mp3", ".m4a", ".webm", ".pem", ".key", ".token", ".apk", ".aab", ".zip")


def assert_structure() -> None:
    missing_files = [name for name in ACTIVE_FILES if not (ROOT / name).is_file()]
    missing_dirs = [name for name in REQUIRED_DIRS if not (ROOT / name).is_dir()]
    assert not missing_files, f"missing active RC6 files: {missing_files}"
    assert not missing_dirs, f"missing required directories: {missing_dirs}"
    assert not (ROOT / "tools" / "validate_rc5.py").exists()
    assert not (ROOT / "validate-gaia-rc5.ps1").exists()


def assert_hygiene() -> None:
    bad: list[str] = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if relative.parts[:2] == ("lumen-core", "data") or relative.parts[:1] == (".timeout-test-data",):
            continue
        if path.name in FORBIDDEN_NAMES or any(part in FORBIDDEN_DIRS for part in relative.parts):
            bad.append(str(relative))
        if path.is_file() and path.name != ".env.example":
            if path.name.startswith(".env.") or path.name.endswith(FORBIDDEN_SUFFIXES):
                bad.append(str(relative))
    assert not bad, f"private/local artifacts in release tree: {sorted(set(bad))}"


def assert_manifest() -> None:
    manifest = json.loads((ROOT / "release_manifest.json").read_text(encoding="utf-8"))
    assert manifest == {
        "deterministic": True,
        "documentation_projection": "all Markdown/TXT members of project archive",
        "manifest_format": 1,
        "product": "GAIA-AI",
        "protocol": "1.0-RC6",
        "release": "1.0-RC6",
        "schema_max": 9,
        "schema_min": 8,
        "version": "1.0.0-rc6-pc",
    }


def assert_git_safety() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".env", "*.db", "logs", "backups", "tokens", "__pycache__"):
        assert pattern in text, f".gitignore lacks protection for {pattern}"


def assert_documentation() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in ACTIVE_FILES:
        if name.endswith((".md", ".txt", ".py", ".ps1")) and name not in {"README.md", "release_manifest.json"}:
            assert name in readme, f"README must reference active RC6 file: {name}"
    for name in HISTORICAL_WARNING_FILES:
        path = ROOT / name
        assert path.is_file(), f"historical file missing: {name}"
        text = path.read_text(encoding="utf-8")
        assert text.startswith(WARNING), f"historical warning missing: {name}"
        assert CURRENT_LINK in text, f"historical RC6 link missing: {name}"
    guide = (ROOT / "UPDATE_ROLLBACK_GUIDE.md").read_text(encoding="utf-8")
    assert guide.startswith("# GAIA-AI v1.0-RC6 — Update, Migration and Rollback Guide")
    assert "1.0.0-rc5" not in guide and "GAIA-AI-v1.0-RC5" not in guide
    assert "rollback" in guide.lower() and "snapshot" in guide.lower()
    assert "v1.0-final" not in readme and "production-ready" not in readme.lower()


def assert_no_obvious_secrets() -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name in {".env.example", ".gitignore"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not re.search(r"LUMEN_SECRET\s*=\s*(?!cambia-este-token|test-|plan-|touch-|master-|scheduler-|rc6-)[A-Za-z0-9_./+:-]{16,}", text), f"possible real LUMEN_SECRET in {path}"
        assert not re.search(r"(?:sk|pk)-[A-Za-z0-9]{20,}", text), f"possible API key in {path}"
        assert not re.search(r"Bearer\s+(?!(?:test|plan|touch|master|scheduler|owner|voice|permission|action|backup|fresh|device|request|terminal|rc6)-)[A-Za-z0-9._-]{24,}", text), f"possible bearer token in {path}"


assert_structure()
assert_hygiene()
assert_manifest()
assert_git_safety()
assert_documentation()
assert_no_obvious_secrets()
print("RELEASE PACKAGE TEST OK: active RC6 structure, hygiene, manifest, historical warnings, docs and git safety hold.")
