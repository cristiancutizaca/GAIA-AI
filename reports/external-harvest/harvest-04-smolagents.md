# Harvest 04 — Hugging Face `smolagents`

- **ID:** `harvest-04-smolagents`
- **Project:** [huggingface/smolagents](https://github.com/huggingface/smolagents)
- **Classification:** `PATTERN_ADOPTED`
- **GAIA action:** Adopt narrowly scoped control and execution patterns in GAIA; do not replace GAIA’s Core, Permission Layer, Action Host, Safe Mode, Kill Switch, RBAC, Event Bus, or Capability Router.
- **Inspection basis:** GitHub `main` README/source (`agents.py`, `local_python_executor.py`, `tools.py`), current Hugging Face docs (guided tour, tools, secure code execution), and `SECURITY.md`/`LICENSE`.

## License and uncertainty

**Verified license: Apache License 2.0** from [`main/LICENSE`](https://raw.githubusercontent.com/huggingface/smolagents/main/LICENSE); the inspected Python source files also carry Apache-2.0 headers. No `smolagents` code is copied into GAIA by this harvest. Apache 2.0 permits use, modification, and distribution subject to license/attribution, NOTICE (if present), and modified-file notice obligations; trademark rights are not granted. This is a verification of the repository’s current `main` state, not a pinned release/commit audit. Dependencies, Hub tools, MCP servers, and remote sandbox providers have their own terms/licenses and were not cleared here.

## Concrete patterns GAIA can adopt

| GAIA authority component | Observed `smolagents` pattern | Safe GAIA adoption (additive, not replacement) |
|---|---|---|
| **Core** | A small step-oriented ReAct loop records model input/output, parsed action, tool call, observation, and final answer in memory; configurable `max_steps`, planning interval, final-answer checks, and `reset=False` continuation. | Add a typed **action-step record** and explicit terminal/output validation to GAIA’s existing Core. Keep GAIA’s authority decisions outside the model loop. |
| **Permission Layer** | `Tool` requires a name, description, typed input schema, output type, and matching `forward` signature; names/types are validated. `CodeAgent` has an explicit authorized-import allowlist. Deserialization uses a closed `AGENT_REGISTRY` rather than arbitrary class imports. | Add **capability manifests + schema/signature validation** and a **closed registry** for persisted capability/agent types. Treat authorized imports as a least-privilege hint only—not as GAIA RBAC. |
| **Action Host** | `PythonExecutor` is a host abstraction with local, Docker, E2B, Modal, and Blaxel implementations. Tool/MCP connections have context-manager/`finally` cleanup patterns. | Use an executor/host interface so GAIA can select an already-approved backend per capability and enforce cleanup, quotas, and credential scoping in GAIA’s host. |
| **Safe Mode** | AST-based `LocalPythonExecutor` restricts imports/dunder access and caps operations/loops, but both README and docs explicitly say it is **not a security boundary**. Remote Docker/E2B/Modal/Blaxel execution is recommended for real isolation; MCP docs warn that stdio servers execute local code and remote servers still require trust. | Adopt **defense-in-depth preflight checks, import/capability allowlists, remote isolation as an optional backend, and explicit “not a boundary” labels**. Never treat the local interpreter as GAIA Safe Mode. |
| **Kill Switch** | `agent.interrupt()` stops at the end of the current step and raises; max-step termination and executor operation/loop/time guards bound runs. The local timeout implementation cannot force-kill a running Python thread. | Add a **cooperative stop flag checked between action steps**, plus GAIA-owned hard termination at the Action Host/process boundary. Preserve GAIA’s stronger Kill Switch semantics where available. |
| **RBAC** | No user/role/tenant RBAC or pre-tool authorization model is provided; tool metadata describes affordances but does not authorize an actor. `trust_remote_code=True` is an explicit trust decision. | **Do not import RBAC from smolagents.** Only reuse schema/manifest inputs as data for GAIA’s existing RBAC and require authorization before every side-effecting capability. |
| **Event Bus** | No durable authority event bus was found. There are fine-grained run logs, memory serialization, streaming model deltas, and observable tool/step outputs. | Add an adapter that emits GAIA Event Bus events from the typed action-step lifecycle; logs are an observability pattern, not a replacement for GAIA’s Event Bus. |
| **Capability Router** | `ToolCollection`/MCP adapters, Hub tools, lazy tool setup, model/provider agnosticism, and managed agents expose capabilities through a common tool surface. | Reuse the **capability descriptor/collection and lazy initialization ideas** behind GAIA’s existing Capability Router, with GAIA ownership of discovery, trust, routing, and authorization. |

## Security-boundary findings

- The project’s own guidance says code agents can execute model-authored code and that local execution is inherently risky; remote sandboxing is the robust isolation path.
- `additional_authorized_imports=["*"]` is explicitly cautioned against because it lets the agent import anything installed; this is not an authorization system.
- Hub-loaded tools/agents require `trust_remote_code=True`, making provenance review an operator decision rather than an enforced permission layer.
- The security policy says local executor escapes, host filesystem access, and network access are out of scope because the local executor makes no isolation guarantee. GAIA should therefore reject any design that uses it as Safe Mode.

## Decision

`PATTERN_ADOPTED`: the useful harvest is the **typed action-step lifecycle, capability schema validation/closed registry, pluggable Action Host contract, explicit cooperative interruption, and capability collection lifecycle**. These are patterns for GAIA’s existing authority model; smolagents is not a replacement backend or authority layer, and no source code is reused.
