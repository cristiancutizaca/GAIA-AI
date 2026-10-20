# GAIA forensic diff audit

Compared baseline `GAIA-AI-v1.0-RC6` with the current repair package. 310 files are byte-identical; 26 paths are new or modified; no baseline file was deleted.

| Path/group | Status | Functional change | Risk | Decision |
|---|---|---|---|---|
| `lumen-core/harness_backend.py` | New | Optional SDK adapter, isolated workspace, no direct tools | Medium | Keep, feature-flagged |
| `deepseek-harness/*`, `DEEPSEEK_HARNESS.md` | New | Runtime policy, disabled shell patches and operator instructions | Medium | Keep, document blocked runtime |
| `tests/*deepseek*`, `tools/test_deepseek_harness_e2e.py` | New | Contract/fallback/E2E probes | Low | Keep |
| `lumen-core/llm.py` | Modified | Harness route with controlled Ollama fallback and shutdown | High | Keep; tested fallback |
| `lumen-core/model_router.py` | Modified | Profile selection and bounded context/predict limits | Medium | Keep |
| `lumen-core/config.py` | Modified | DSH settings, paths and safe defaults | High | Keep; localhost-first |
| `lumen-core/requirements.txt` | Modified | Pinned `deepseek-harness-sdk==0.1.5rc1` | Medium | Keep optional install path |
| `lumen-pc/requirements-windows.txt` | Modified | Verified pycaw pin retained | Medium | Keep |
| `install-deepseek-harness.*` | New | Explicit, user-invoked SDK install | Medium | Keep; no auto-install |
| `install-gaia.ps1` | Modified | Harness-aware install and Doctor flow | High | Keep; Windows validation required |
| `tools/gaia_doctor.py` | Modified | DSH detection and read-only status | Medium | Keep |
| `tools/build_release.py` | Modified | Allowlist includes Harness assets | Medium | Keep; clean build PASS |
| `tools/validate_rc6.py` | Modified | External venv validation and package-first runner | High | Repair transition check |
| `.env.example`, `.gitignore`, docs | Modified | Configuration and release documentation | Low | Keep |

No changes were made to the baseline tree.
