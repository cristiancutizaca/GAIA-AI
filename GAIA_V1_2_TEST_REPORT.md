# GAIA v1.2 test report

- Baseline v1.1 regression after packaging permission repair: **127 PASS, 0 FAIL, 3 DEPENDENCY_MISSING** (Tkinter GUI tests).
- v1.2 platform test: **PASS**; local stdio MCP initialize/discovery/call, memory ownership, skill validation, scheduler, backup checksum round-trip, observability redaction, device pairing, graph edges and web prompt-injection guard.
- v1.2 compile: **102 Python files PASS**.
- No physical PASS is claimed for Windows UI, browser rendering, microphone, speakers, GPU, Ollama, Pipecat/Silero or external SDK services.
