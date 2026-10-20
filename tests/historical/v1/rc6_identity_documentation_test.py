from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

manifest = json.loads((ROOT / "release_manifest.json").read_text(encoding="utf-8"))
assert manifest["product"] == "GAIA-AI"
assert manifest["protocol"] == "1.0-RC6"
assert manifest["release"] == "1.0-RC6"
assert manifest["version"] == "1.0.0-rc6-pc"
assert manifest["schema_min"] == 8 and manifest["schema_max"] == 9
assert manifest["manifest_format"] == 1 and manifest["deterministic"] is True
assert manifest["documentation_projection"] == "all Markdown/TXT members of project archive"

from config import VERSION
assert VERSION == "1.0.0-rc6-pc"
assert "PROTOCOL_VERSION = \"1.0-RC6\"" in (ROOT / "lumen-core" / "lan_protocol.py").read_text(encoding="utf-8")
assert "HOST_VERSION = \"1.0.0-rc6-pc\"" in (ROOT / "lumen-pc" / "action_host.py").read_text(encoding="utf-8")
assert "version: 1.0.0-rc6+1" in (ROOT / "lumen-mobile" / "pubspec.yaml").read_text(encoding="utf-8")
assert 'versionName "1.0-RC6"' in (ROOT / "lumen-mobile" / "android" / "app" / "build.gradle").read_text(encoding="utf-8")

active_docs = {
    "README.md": "# GAIA-AI v1.0-RC6",
    "CHANGELOG.md": "# Changelog",
    "AUDIT.md": "# GAIA-AI v1.0-RC6 Audit",
    "TEST_REPORT.md": "# TEST REPORT — GAIA-AI v1.0-RC6",
    "FINAL_VALIDATION.txt": "GAIA-AI v1.0-RC6 — FINAL VALIDATION",
    "KNOWN_LIMITATIONS.md": "# GAIA-AI v1.0-RC6 Known Limitations",
    "MODIFIED_FILES.md": "# GAIA-AI v1.0-RC6 — Modified Files",
    "RC6_REQUIREMENTS.md": "# GAIA-AI v1.0-RC6 Requirements",
    "PERFORMANCE_RC6_REPORT.md": "# GAIA-AI v1.0-RC6 Performance and Reproducibility Report",
    "PERFORMANCE_COMPARISON_RC5_RC6.md": "# GAIA-AI v1.0-RC6 Performance Comparison",
    "PHYSICAL_VALIDATION_RC6.md": "# GAIA-AI v1.0-RC6 Physical Validation",
    "WINDOWS_RC6_VALIDATION_CHECKLIST.md": "# GAIA-AI v1.0-RC6 Windows Validation Checklist",
    "MIGRATION_MATRIX_RC5_RC6.md": "# Migration Matrix RC5 → RC6",
    "RELEASE_DECISION_RC6.md": "# GAIA-AI v1.0-RC6 Release Decision",
    "SECURITY_MODEL.md": "# GAIA-AI v1.0-RC6 Security Model",
    "THREAT_MODEL.md": "# GAIA-AI v1.0-RC6 Threat Model",
    "UPDATE_ROLLBACK_GUIDE.md": "# GAIA-AI v1.0-RC6 — Update, Migration and Rollback Guide",
    "DOCUMENT_CLASSIFICATION_RC6.md": "# GAIA-AI v1.0-RC6 Document Classification",
}
for name, heading in active_docs.items():
    text = (ROOT / name).read_text(encoding="utf-8")
    assert text.startswith(heading), name
    assert "v1.0-final" not in text and "production-ready" not in text.lower()

historical_warning = "HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS"
historical_operational = [
    "WINDOWS_FIRST_TEST_CHECKLIST.md",
    "PHYSICAL_VALIDATION_V100.md",
    "V100_PREPARATION.md",
    "GAIA_VAULT_MIGRATION.md",
    "PHYSICAL_VALIDATION_RC4.md",
    "RC4_REQUIREMENTS.md",
    "PHYSICAL_VALIDATION_RC5.md",
    "WINDOWS_RC5_VALIDATION_CHECKLIST.md",
]
for name in historical_operational:
    text = (ROOT / name).read_text(encoding="utf-8")
    assert text.startswith(historical_warning), name
    assert "For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md." in text, name

runner = (ROOT / "tools" / "validate_rc6.py").read_text(encoding="utf-8")
assert "gaia_rc6_validator" in runner and "GAIA-AI-v1.0-RC6" in runner
assert "tools/validate_rc6.py" in runner and "1.0-RC5" not in runner and "validate_rc5" not in runner
wrapper = (ROOT / "validate-gaia-rc6.ps1").read_text(encoding="utf-8")
assert "tools/validate_rc6.py" in wrapper and "GAIA-AI-v1.0-RC6" in wrapper
migrator = (ROOT / "tools" / "gaia_migrate.py").read_text(encoding="utf-8")
assert "RC6_VERSION" in migrator and "gaia-rc6-snapshot-1" in migrator
assert "RC5_VERSION" not in migrator
assert "GAIA-AI-v1.0-RC5-final.zip" not in "\n".join(active_docs)
assert not (ROOT / "tools" / "validate_rc5.py").exists()
assert not (ROOT / "validate-gaia-rc5.ps1").exists()
print("RC6 IDENTITY/DOCUMENTATION TEST OK: active identity, RC6 docs, historical warnings, entrypoints and no-final policy hold.")
