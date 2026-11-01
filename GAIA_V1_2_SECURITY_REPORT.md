# GAIA v1.2 security report

Implemented defenses: MCP allow/deny lists and confirmation; explicit stdio argv (no shell); HTTP URL scheme/domain checks; web-content untrusted boundary and prompt-injection markers; owner/namespace memory queries; skill permission denial; temporary coding workspaces; path traversal checks; no plaintext secret fallback; backup exclusion of `.env`, secrets and tokens; redacted observability; owner-scoped device pairing; visualizer read-only.

Residual risk: external SDKs, browser rendering, audio, real model calls, remote MCP, OS GUI and Windows keyrings require physical/host validation. Never enable Computer Use or interactive browser actions without Action Host integration and approval.
