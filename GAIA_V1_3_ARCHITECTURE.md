# GAIA v1.3 architecture

`PlatformRuntime` is owned by the real Core FastAPI lifespan. It lazily owns `CapabilityRouter`, SQLite Memory V2, HTTP Browser fallback, MCP Manager and persistent automation metadata. `/api/chat` delegates capability-shaped requests to the runtime; ordinary conversation continues through the existing GAIA LLM path. All externally affecting actions remain behind GAIA auth, Permission Layer and Action Host.
