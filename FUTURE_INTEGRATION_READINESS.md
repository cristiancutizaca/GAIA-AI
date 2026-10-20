# Future integration readiness (assessment only)

No listed integration is implemented in this recovery iteration.

| Project | GAIA fit/module | Dependencies | Risk | License review | Prerequisite | Priority |
|---|---|---|---|---|---|---|
| PersonalJarvis | orchestration/adapters | API contract | Medium | Required | stable plugin boundary | Medium |
| MCP / mcp-use | tool adapters behind Action Host | MCP SDK | High | Required | capability mapping | High |
| Browser Use | optional browser adapter | browser runtime | High | Required | remote-action policy | Medium |
| Pipecat | voice pipeline | audio stack | High | Required | voice isolation | Medium |
| Silero VAD | voice preprocessor | model/runtime | Medium | Required | explicit model policy | Medium |
| UI-TARS Desktop | observation adapter | vision/UI runtime | High | Required | read-only UIA boundary | Low |
| Agent-S | planner adapter | agent SDK | High | Required | no direct tools | Low |
| Mem0 | memory provider | vector/store deps | High | Required | provenance/namespace contract | Medium |
| Graphiti | temporal graph memory | graph DB/services | High | Required | backup/migration design | Low |
| OpenHands SDK | coding workflow adapter | SDK/runtime | High | Required | sandboxed workspace | Low |
| smolagents | planner experiment | Python SDK | Medium | Required | Action Host adapter | Low |
| LiveKit Agents | realtime voice | LiveKit stack | High | Required | privacy/consent flow | Low |
| Jared/fullstack-agent visualizer | observability UI | frontend stack | Medium | Required | redacted event schema | Low |

All future work must preserve GAIA ownership, namespaces, permissions, Safe Mode, kill switch and explicit external side effects.
