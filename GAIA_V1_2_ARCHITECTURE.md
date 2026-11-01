# GAIA v1.2 architecture

The new platform lives under `lumen-core/gaia_platform/` and never replaces RC6 Core. The authority chain remains `User → GAIA → Planner → risk → Permission Layer → preflight → Action Host → adapter → target`.

MCP, browser, voice, memory, workers, scheduler, secrets, backup, observability, devices and visualizer use explicit contracts. Optional external SDKs are loaded only behind flags. The safe default is local SQLite, all new integrations disabled, localhost-first and no automatic model/service startup.
