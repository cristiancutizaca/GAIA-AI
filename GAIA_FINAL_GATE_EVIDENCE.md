# GAIA v2.0 — Final Gate Evidence

- Gate: `GATE_V20_SOFTWARE`
- Tests discovered: `129`
- Passed: `129`
- Failed: `0`
- Timeouts: `0`
- Syntax compile check: `PASS`
- v2.0 identity/launcher contract: `PASS`
- Release package hygiene: `PASS`
- Archive builder: `PASS`
- Archive members: verified by the v2.0 builder manifest
- Physical validation: `PENDING_PHYSICAL_VALIDATION` where hardware, Windows or credentials are unavailable

The gate is isolated per test. Before each test, local `__pycache__`, test data, diagnostics and physical-validation state are removed. The archive itself excludes bytecode and private state.
