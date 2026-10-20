# GAIA v1.3 known issues

- Core wiring is real for memory, local HTTP browser reads and local MCP stdio, but planner vocabulary is intentionally narrow.
- Browser Use rendering/click/type is not connected; HTTP fallback is correctly named and read-only.
- Persistent automation metadata exists, but execution must be routed through the existing Planner/Permission/Action Host bridge before being called production E2E.
- Skills are registered and validated but not yet selected/executed by the natural-language planner.
- Voice, OpenHands, Mem0, Graphiti, LiveKit, Android and Computer Use require optional dependencies or physical systems.
