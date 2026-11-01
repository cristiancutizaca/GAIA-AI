# GAIA v1.3 E2E report

## Passing flow

`POST /api/chat` with master bearer auth → Core session claim → `PlatformRuntime.handle_chat` → Capability Router → capability policy → backend → redacted result → `ChatResponse` and Core memory transcript.

Covered cases: memory remember/retrieve across sessions; local HTTP page title extraction; MCP stdio initialize/list/call; `/api/platform/status`.

## Not claimed

No E2E claim for rendered browser click/DOM mutation, real audio, external Mem0/Graphiti/OpenHands, Android, remote devices or Computer Use.
