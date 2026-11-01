# GAIA v1.1 Evolution Foundation

GAIA Core remains the authority. New code is a native, lazy foundation under `lumen-core/gaia_ext/` with explicit boundaries:

`Core → Planner → Permission Layer → Action Host → Adapter → target`

The foundation provides contracts, feature flags, isolated plugin health, a metadata-safe Event Bus, a risk-aware MCP Gateway, read-only visualizer/realtime schemas and optional adapter stubs. All new flags default to false and RC6 can start unchanged.
