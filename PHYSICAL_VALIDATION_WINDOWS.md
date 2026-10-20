HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS
For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# Physical validation — Windows / ASUS TUF

Run on Windows 11 with Python 3.11 after extracting the release. Do not treat Linux results as physical evidence.

1. Copy `.env.example` to `.env` without overwriting an existing valid file; set a strong `LUMEN_SECRET`.
2. Run `powershell -ExecutionPolicy Bypass -File .\install-gaia.ps1`; confirm it creates/reuses `.venv` idempotently and finishes with read-only Doctor.
3. Run `python tools\gaia_doctor.py --json --mode safe`; record Python, dependencies, audio, GPU and Ollama statuses.
4. With Ollama already installed and manually started, verify the selected Qwen model exists; do not run `ollama pull` automatically.
5. Start Core on localhost and verify `/api/health`, `/api/status` and one real conversation.
6. Verify Safe Mode blocks external actions and Action Host rejects an unallowlisted benign probe.
7. Run the Windows, GUI, voice and Android checklists; record PASS/FAIL/PENDING with evidence outside the release.
8. Stop Core and repeat start/stop; confirm no orphan processes and no unexpected LAN bind.

Required evidence: OS/Python versions, installer exit codes, Doctor JSON, one redacted health/conversation trace, and explicit Ollama/model availability. Never include secrets, DBs, recordings or private logs in the release.
