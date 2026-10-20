# Harvest 03 — Microsoft Agent Framework

**Classification: `PATTERN_ADOPTED`**

No replacement of GAIA is recommended. Microsoft Agent Framework (MAF) is a multi-language (.NET, Python, and a linked Go SDK) framework for production agents and graph-based multi-agent workflows. The current README explicitly lists middleware, sequential/concurrent/handoff/group orchestration, checkpointing, streaming, human-in-the-loop, OpenTelemetry, and provider flexibility as supported features. [1]

## Patterns GAIA can adopt

- **Permission Layer — approval as a first-class protocol.** MAF marks individual tools as approval-required, returns a structured request containing the tool name and arguments, and resumes with an explicit approve/reject response using the same session. Its harness middleware can queue multiple requests and persist standing approvals scoped to a tool, exact canonicalized arguments, and (for hosted tools) a server label. With no configured auto-approval rules, unmatched requests return to the caller for approval. [2] GAIA should adopt this as a capability-grant/approval protocol inside its existing Permission Layer, not as a replacement for GAIA policy or RBAC.

- **Safe Mode — fail-closed enforcement seams.** The source-level Agent Hooks implementation brackets agent, model, and tool execution (`input`, `output`, `pre/post_model_call`, `pre/post_tool_call`), applies transforms back into the native context, blocks denied actions, buffers streaming output until a verdict, and gates durable persistence behind approved verdicts. Enforcement/interceptor failures become denies or `MiddlewareFailure` rather than silently continuing. [3] [4] This is directly useful for GAIA Safe Mode: deny on policy-host failure, prevent unapproved content from egressing or becoming durable, and define separate pre/post gates.

- **Core/Action Host — composable host pipeline.** MAF's Harness composes a chat client, function-invocation pipeline, session/context providers, middleware/decorators, approval handling, observability, and UX while returning a normal agent object. [5] GAIA can use the same composition boundary in its existing Action Host: keep authority in GAIA Core/Permission Layer, but make execution, approval UX, persistence, and telemetry explicit host capabilities.

- **Capability Router / Event Bus — typed graph routing with delivery outcomes.** MAF workflows use executors, edges, events, and explicit execution paths. Its observability model records executor processing, message sends, edge delivery status, causal links, and structured lifecycle events; delivery outcomes distinguish delivered, type/target/condition drops, exceptions, and buffering. [6] GAIA can adopt typed capability envelopes plus deterministic routing by capability/type, target, and condition, and publish these outcomes on its Event Bus for audit and replay.

- **RBAC-adjacent grants, not RBAC itself.** Tool approval rules demonstrate narrow, durable grants (tool-wide or exact-argument scope) and server-boundary scoping. This is a useful primitive for GAIA's RBAC enforcement and delegation model, but MAF does not provide a GAIA-equivalent identity/role/tenant authorization system in the inspected material.

## Boundaries and non-findings

The inspected MAF material does **not** establish a system-wide Kill Switch, GAIA-style authority Core, or a security-complete RBAC model. `MiddlewareTermination`/`MiddlewareFailure` provide per-run termination and fail-closed abort semantics, not an operator kill switch. MAF's safety documentation also states that tools are invoked without user approval unless approval is configured, and that developers must validate inputs, secure data flows, configure tools, rate-limit, and add responsible-AI mitigations. [7] GAIA should therefore retain its own default-deny authority, Kill Switch, identity/RBAC, and policy ownership.

## License and reuse posture

**Verified license:** MIT License, from the repository's `LICENSE` file; it grants use, copy, modify, publish, distribute, sublicense, and sell rights subject to retaining the copyright and permission notice. The file states copyright Microsoft Corporation and an “AS IS” warranty disclaimer. [8]

This harvest adopts **patterns only**; no MAF code is copied or linked into GAIA, so this is not `CODE_REUSED_WITH_LICENSE`. License uncertainty is limited to components outside the repository's top-level MIT grant: provider SDKs, optional packages (for example `agent-hooks-sdk`), transitive dependencies, hosted services, and third-party systems have their own terms. The README and safety docs expressly place third-party-system licensing, data handling, and permissions on the application developer. [1] [7] A dependency/license audit was not performed.

## References

[1]: https://github.com/microsoft/agent-framework "Microsoft Agent Framework README"
[2]: https://learn.microsoft.com/en-us/agent-framework/agents/tools/tool-approval "Microsoft Agent Framework tool approval"
[3]: https://raw.githubusercontent.com/microsoft/agent-framework/main/python/packages/core/agent_framework/_agent_hooks.py "Agent Framework Python Agent Hooks source"
[4]: https://raw.githubusercontent.com/microsoft/agent-framework/main/python/packages/core/agent_framework/_middleware.py "Agent Framework Python middleware source"
[5]: https://learn.microsoft.com/en-us/agent-framework/concepts/harness "Microsoft Agent Framework Harness"
[6]: https://learn.microsoft.com/en-us/agent-framework/workflows/observability "Microsoft Agent Framework workflow observability"
[7]: https://learn.microsoft.com/en-us/agent-framework/agents/safety "Microsoft Agent Framework safety guidance"
[8]: https://github.com/microsoft/agent-framework/blob/main/LICENSE "Microsoft Agent Framework LICENSE"
