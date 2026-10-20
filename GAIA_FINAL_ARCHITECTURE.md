# GAIA Final Architecture

GAIA conserva una única cadena de autoridad:

`API / CLI → Core → PlatformRuntime → Planner + Capability Router → Permission Layer → Action Host / backend → Event Bus / Observability`

El Planner solo propone; no ejecuta. Cada capability tiene provider, risk y permission. `authority.authorize` bloquea por defecto: permisos ausentes, Safe Mode, Kill Switch y side-effects sin confirmación. MCP repite la comprobación en su propio manager para evitar bypasses directos.

## Runtime components

- **Core:** FastAPI, chat, auth, memory APIs, startup/shutdown.
- **PlatformRuntime:** lifecycle, capabilities, planner, skills, MCP, browser, memory, jobs, projects, filesystem sandbox, breakers.
- **Persistence:** existing Core SQLite plus project/job/automation stores; no credentials or downloaded models in release.
- **Optional backends:** Whisper/Edge TTS, MCP servers, browser automation, graph memory and coding workers are feature-flagged.
- **Recovery:** backup manifest/checksums, rollback documentation and physical validation ledger.

No external project replaces GAIA Core, Permission Layer or Action Host.


## v1.6 real providers

`real_backends.py` adds lazy, actual upstream boundaries for Browser Use, Pipecat, Silero VAD, Mem0, Graphiti, OpenHands and UI-TARS. They are never authorities. Browser Use is selected only with `GAIA_FEATURE_BROWSER=true`; Mem0/Graphiti require explicit configuration; OpenHands uses a copied workspace; UI-TARS is blocked in headless environments. `static/gaia_visualizer.html` consumes sanitized Event Bus events over SSE and cannot execute effects.
