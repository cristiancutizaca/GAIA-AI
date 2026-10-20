# GAIA v1.1 test report

Automated foundation tests cover all-disabled startup, feature flags, plugin isolation, event redaction/state validation, MCP risk/allowlist/confirmation/permission behavior, CLI/Doctor V2 and legacy RC6 regression contracts.

Result in the Linux sandbox: **127 PASS, 0 FAIL, 3 DEPENDENCY_MISSING** (the three GUI tests require Tkinter). Compilation covered 88 Python files. Physical browser, audio, GPU, Windows UI, Ollama and external SDK behavior remain validation-required.
