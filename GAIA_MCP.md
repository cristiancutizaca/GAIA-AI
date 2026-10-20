# GAIA MCP Gateway

`MCPGateway` provides an MCP-shaped JSON-RPC surface for initialize, tools/list and tools/call plus connection, health, allowlist, denylist, namespaces, timeout/cancellation at the caller boundary and audit metrics.

Tools are classified READ_ONLY, LOW_RISK, INTERACTIVE, EXTERNAL_SIDE_EFFECT or PRIVILEGED. Interactive and sensitive calls require explicit confirmation; side effects additionally require a GAIA Permission Layer callback. No MCP server is started automatically.
