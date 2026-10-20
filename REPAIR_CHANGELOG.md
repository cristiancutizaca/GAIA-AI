# Repair changelog

## Applied

1. Preserved the current DeepSeek Harness adapter as optional and isolated.
2. Kept `GAIA_DSH_FALLBACK_TO_OLLAMA=true` as the controlled fallback path.
3. Repaired `tools/validate_rc6.py`: `--venv-ready --venv-path` now checks the supplied external venv instead of incorrectly requiring the parent process to already run inside it.
4. Validated clean release packaging with bytecode redirected outside the project tree.
5. Added recovery audit, test, security, physical-validation and future-readiness documentation.

## Not changed

No authentication, permission, Action Host, Safe Mode, kill switch, ownership, namespace, shell boundary or automatic-model policy was weakened. No external product integration was added.
