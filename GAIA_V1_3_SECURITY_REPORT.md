# GAIA v1.3 security report

Implemented in the production path: bearer authentication for API routes; runtime capability checks; memory owner/namespace isolation; MCP allowlist and confirmation; web content labeled untrusted; SSRF blocking for loopback/private/link-local/reserved addresses unless an explicit local-test profile allows it; no shell interpolation for MCP stdio; redacted events; persistent automation owner checks; no plaintext secret fallback.

Not production-enabled: rendered browser interactions, Computer Use, external Mem0/Graphiti/OpenHands/Pipecat/LiveKit.
