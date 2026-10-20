# OpenManus → GAIA authority-model harvest

- **ID:** `harvest-02-openmanus`
- **Project:** [FoundationAgents/OpenManus](https://github.com/FoundationAgents/OpenManus)
- **Classification:** `PATTERN_ADOPTED`
- **Verified license:** **MIT License**, copyright `2025 manna_and_poem`. The repository’s `LICENSE` text and GitHub API metadata both identify MIT (`SPDX: MIT`).[3][4]
- **License uncertainty:** This verifies the root project license only. OpenManus depends on and integrates other projects (including Browser Use, MCP, Daytona, crawl4ai, and charting packages); their licenses were not audited here. Any source-code reuse would still require preserving the MIT notice and reviewing dependency notices. This harvest recommends patterns, not copying source.

## What was inspected

The current `main` branch README documents a Python 3.12 agent framework, local and `uv` installation, configurable LLM backends, MCP execution, Browser Use CLI 3.0, a data-analysis agent, and separate chart-visualization documentation.[2][9] The source tree exposes distinct `agent`, `flow`, `mcp`, `sandbox`, and `tool` areas.[5] The repository metadata reports `main` as the default branch and MIT as the declared license.[4]

## Concrete patterns GAIA can adopt

**Core — bounded, explicit agent lifecycle.** `BaseAgent` defines `IDLE`, `RUNNING`, `FINISHED`, and `ERROR` transitions; a context manager marks failures as `ERROR`; `run()` enforces `max_steps`, increments a step counter, detects repeated assistant output, and performs sandbox cleanup.[6] GAIA can adopt these as Core invariants: bounded work, explicit terminal/error states, stuck-loop detection, and `finally`-style teardown. This augments GAIA’s Core; it does not replace it.

**Action Host — one tool contract and deterministic dispatch.** `BaseTool` standardizes `name`, `description`, parameter schema, async `execute`, and structured `ToolResult` success/error output.[10] `ToolCollection` provides name-based lookup, rejects unknown tools, skips duplicate names, and converts `ToolError` into a result rather than crashing the dispatcher.[8] GAIA can adopt this contract at its existing Action Host boundary so every action has a discoverable schema, a stable result envelope, and a deterministic registration policy.

**Capability Router — namespaced MCP capabilities with lifecycle control.** `MCPClients` connects to multiple SSE or stdio servers, records server IDs and server instructions, turns each discovered remote tool into a local proxy, prefixes names as `mcp_<server>_<tool>`, and removes a server’s tools on disconnect.[11] `MCPAgent` periodically refreshes tool schemas and notices additions, removals, and shutdown.[7] GAIA can adopt server-scoped capability IDs, explicit connect/disconnect, schema refresh, and capability provenance. The Permission Layer must authorize each capability before the existing Router exposes it; OpenManus itself does not provide that authorization.

**Kill Switch — explicit termination plus teardown.** OpenManus models `terminate` as a special tool that changes agent state to `FINISHED`; MCP cleanup disconnects sessions, and the base run path cleans the sandbox.[7][6] Its sandbox shell also exposes `terminate_command` for killing a named tmux session.[14] GAIA can adopt a distinct cancellation/termination command that is observable, idempotent, and followed by deterministic Action Host cleanup. This is a cooperative kill path, not evidence of a process-level emergency stop; GAIA’s existing Kill Switch must remain authoritative.

**Safe Mode — bounded execution, not a security boundary.** `PythonExecute` runs code in a child process and terminates it after a timeout.[13] The configuration model also exposes sandbox memory, CPU, timeout, and `network_enabled` controls, while Daytona-backed tools scope work to `/workspace`.[12][15] GAIA can adopt resource budgets, child-process termination, workspace scoping, and an explicit network-denied default as Safe Mode controls. Do **not** treat the Python helper as isolation: it uses `exec` with copied builtins and has no allowlist or syscall policy. The shell tool accepts arbitrary commands inside its sandbox and supports long-lived tmux sessions.[14]

**Human escalation — useful Action Host primitive, not authorization.** `AskHuman` pauses for an interactive question and returns the answer.[16] GAIA can adopt a typed “request human decision” action for escalation or clarification, but the Permission Layer/RBAC must decide whether the request is allowed and what approval means. It is not a substitute for RBAC or policy enforcement.

## Authority-model comparison

- **Core:** concrete bounded lifecycle and stuck-loop patterns are adoptable.[6]
- **Permission Layer:** no concrete RBAC or policy-enforcement layer was found. Tool lookup is not authorization; retain GAIA’s existing authority checks before dispatch.[8][11]
- **Action Host:** the standardized tool contract, structured results, duplicate handling, and invalid-tool failures are adoptable.[8][10]
- **Safe Mode:** adopt budgets, timeout termination, workspace scoping, and network-denied configuration only; reject the assumption that `exec` or a command sandbox alone is sufficient isolation.[12][13][14]
- **Kill Switch:** adopt explicit cooperative terminate/cancel and teardown hooks; keep GAIA’s authoritative kill path.[6][7][14]
- **RBAC:** no roles, subjects, grants, or deny/allow evaluation were found; no RBAC pattern to import.
- **Event Bus:** state, memory, and logging are present, but no pub/sub event bus or durable event contract was found.[6][17] GAIA should not add OpenManus-shaped event infrastructure based on this inspection.
- **Capability Router:** adopt MCP server identity, namespacing, schema refresh, and connect/disconnect lifecycle behind GAIA policy checks.[7][11]

## GAIA action

Adopt the **patterns**, not the backend: (1) bounded state-machine execution and stuck-loop detection in the existing Core; (2) a uniform, schema-first action contract and structured failures at the existing Action Host; (3) server-scoped capability IDs and refresh/teardown in the existing Capability Router; and (4) explicit cooperative cancellation with resource budgets in Safe Mode. Do not replace GAIA’s Core, Permission Layer, Action Host, Safe Mode, Kill Switch, RBAC, Event Bus, or Capability Router, and do not directly expose OpenManus MCP/shell/Python capabilities without GAIA authorization and isolation.

## References

[1]: https://github.com/FoundationAgents/OpenManus "Official OpenManus repository"
[2]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/README.md "OpenManus current README"
[3]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/LICENSE "OpenManus root MIT license text"
[4]: https://api.github.com/repos/FoundationAgents/OpenManus "GitHub repository metadata and declared license"
[5]: https://api.github.com/repos/FoundationAgents/OpenManus/git/trees/main?recursive=1 "OpenManus current source tree"
[6]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/agent/base.py "OpenManus BaseAgent lifecycle"
[7]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/agent/mcp.py "OpenManus MCPAgent"
[8]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/tool/tool_collection.py "OpenManus ToolCollection"
[9]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/tool/chart_visualization/README.md "OpenManus chart visualization documentation"
[10]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/tool/base.py "OpenManus BaseTool and ToolResult"
[11]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/tool/mcp.py "OpenManus MCP client and remote tool proxy"
[12]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/config.py "OpenManus runtime and sandbox configuration"
[13]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/tool/python_execute.py "OpenManus Python execution tool"
[14]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/tool/sandbox/sb_shell_tool.py "OpenManus sandbox shell tool"
[15]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/daytona/tool_base.py "OpenManus Daytona sandbox tool base"
[16]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/tool/ask_human.py "OpenManus human escalation tool"
[17]: https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/schema.py "OpenManus agent state and message schema"
