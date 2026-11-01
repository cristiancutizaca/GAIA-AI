# GAIA v1.3 test report

- v1.2 baseline: 128 PASS, 0 FAIL, 3 Tkinter dependency-missing.
- v1.3 platform integration: PASS (persistent automation, ownership, SSRF, injection guard, Skill registry).
- v1.3 Core E2E: PASS through real `POST /api/chat` for platform status, memory write/read, local HTTP browser read and local MCP stdio call.
- Python compilation after wiring: required before release; no physical pass inferred.
