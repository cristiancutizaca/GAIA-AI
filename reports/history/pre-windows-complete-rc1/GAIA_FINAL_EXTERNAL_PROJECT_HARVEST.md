# PersonalJarvis Harvest — Final Comparison Report

**Purpose.** This report synthesizes the ten external harvests into a comparison against GAIA’s existing **Core, Permission Layer, Action Host, Safe Mode, Kill Switch, RBAC, Event Bus, and Capability Router**. It preserves each harvest’s classification, license posture, concrete GAIA improvement, and adoption blocker or boundary.

**Overall result.** All ten harvests are classified **`PATTERN_ADOPTED`**. They recommend additive design patterns only—not replacement architectures—and explicitly report **no source-code integration or copying**. This report therefore makes no claim that any external implementation has been integrated into GAIA.

## Executive comparison

| Harvest | Classification | Verified license posture | Highest-value GAIA improvement | Primary blocker / boundary |
|---|---|---|---|---|
| [PersonalJarvis](https://github.com/PersonalJarvis/PersonalJarvis) | `PATTERN_ADOPTED` | Current `main`: Apache-2.0 + `NOTICE`; releases through 1.6.0 remain MIT; bundled components retain their own terms. | Deterministic, argument-sensitive approval; sole Action Host chokepoint; scoped cancellation; immutable trace events. | Pattern-only recommendation; historical tags/dependencies were not fully audited; no generic RBAC was verified; Safe Mode is not a universal sandbox or rollback. |
| [OpenManus](https://github.com/FoundationAgents/OpenManus) | `PATTERN_ADOPTED` | MIT; dependency licenses were not audited. | Bounded lifecycle/state machine, stuck-loop detection, schema-first tool contract, namespaced MCP capability lifecycle, resource budgets. | No concrete RBAC or policy enforcement; `exec`/shell are not isolation; cooperative terminate is not a process-level emergency stop; no durable event bus found. |
| [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) | `PATTERN_ADOPTED` | MIT; provider SDKs, optional packages, transitive dependencies, hosted services, and third-party systems have separate terms. | First-class exact-argument approval protocol; fail-closed hooks; durable-persistence gating; typed workflow delivery outcomes. | No GAIA-equivalent Core, system-wide Kill Switch, or complete RBAC; tools may run without approval unless configured; dependency audit not performed. |
| [smolagents](https://github.com/huggingface/smolagents) | `PATTERN_ADOPTED` | Apache-2.0; dependencies, Hub tools, MCP servers, and remote sandboxes retain their own terms. | Typed action-step records, capability schemas/closed registry, pluggable Action Host, cooperative interruption. | Local executor explicitly is not a security boundary; no RBAC or durable authority bus; remote code/MCP requires trust and provenance review. |
| [fullstack-agent](https://github.com/jaredrhod/fullstack-agent) | `PATTERN_ADOPTED` | AGPL-3.0-or-later; component-repository licenses were not reviewed. | Deterministic one-interview setup, default-ask consent, exact-child ownership, resumable/non-destructive updates, preview-before-apply. | Not an authorization engine; component internals and Claude Code enforcement were not inspected; AGPL requires separate review for code reuse. |
| [ai-memory-vault](https://github.com/jaredrhod/ai-memory-vault) | `PATTERN_ADOPTED` | CC BY-SA 4.0; no per-file license map or dependency inventory. | Bootstrap/index convention; confirmation gates; backup-before-edit, merge/serialize/verify/restore transactions; task-scoped context routing. | Prompt-driven Markdown is untrusted and not an enforcement boundary; no RBAC, event bus, kill switch, or isolated host; shipped auto-install/broad writes must not become authority logic. |
| [backtalk](https://github.com/jaredrhod/backtalk) | `PATTERN_ADOPTED` | AGPL-3.0-or-later; no independent provenance audit or commercial exception verified. | Exact-match deny-by-default voice approval; single session gate; independently testable interruption and stream cleanup; typed voice events. | No RBAC; `extra_dirs`/`visible_skills` are not sandbox/RBAC; filesystem signals are unauthenticated/non-atomic; AGPL blocks casual code reuse. |
| [ai-visualizer](https://github.com/jaredrhod/ai-visualizer) | `PATTERN_ADOPTED` | AGPL-3.0-or-later; bundled VT323 font is OFL-1.1; `face.png`/`thinking.wav` rights are uncertain. | Read-only telemetry schema with freshness/TTL and benign malformed-input behavior; shared adapter; renderer manifests; deterministic preview harness. | Read-only UI has no Action Host, authorization, or Kill Switch; localhost/path confinement is not a complete security boundary; uncertain media rights block copying. |
| [barehands](https://github.com/jaredrhod/barehands) | `PATTERN_ADOPTED` | AGPL-3.0-or-later; MediaPipe is Apache-2.0 and three.js MIT as CDN dependencies; versions not pinned. | Typed local command envelope, fixed allowlist, path containment, queue backpressure, stale-state decay, snapshot-vs-command channels. | No caller authentication/RBAC/audit/emergency stop; localhost is not actor authentication; UI reset is not a GAIA Kill Switch. |
| [Browser Use + Pipecat](https://github.com/browser-use/browser-use), [Pipecat](https://github.com/pipecat-ai/pipecat) | `PATTERN_ADOPTED` | Browser Use MIT; Pipecat BSD-2-Clause; dependencies, integrations, generated artifacts, and hosted services need separate review. | Typed capability envelopes with schemas/scopes/deadlines; external stop polling; priority revocation lane; targeted/broadcast bus; one cleanup boundary. | Allowlists/bus addressing are not authorization; browser/MCP access requires trust/sandboxing; graceful stop and cancellation semantics must remain GAIA-owned. |

## Harvest-by-harvest findings

### 1. PersonalJarvis — authority-boundary patterns

- **Classification:** `PATTERN_ADOPTED`.
- **GAIA posture:** Adopt patterns inside GAIA’s existing model; do not replace GAIA Core, its authority model, or execution hosts. No PersonalJarvis code is copied.
- **License note:** Current `main` contains **Apache License 2.0** and `NOTICE`. Its licensing document says `main` switched on 2026-08-27 and version 2.0.0 is the first Apache-2.0 release; releases through 1.6.0 remain MIT. Apache reuse requires license/NOTICE, modification, patent, and trademark compliance. Bundled components retain their own licenses; the NOTICE calls out the Silero VAD model as MIT. Verification covers fetched current `main`, not every historical tag or dependency; any future reuse needs file-level provenance and notice review.
- **Concrete GAIA improvements:**
  - **Core:** strengthen structural `typing.Protocol` contracts and reject direct cross-layer calls where an authority boundary is intended; use typed events for lateral communication.
  - **Permission Layer:** implement precedence **blacklist > whitelist > tool default**, argument-sensitive risk hooks, fail-closed malformed tiers, and one exact-call/trace approval receipt. Keep OS/service permissions separate from policy approval.
  - **Action Host:** make it the sole enforcement chokepoint: risk evaluation → plausibility check → approval → execution → events; emit proposed/required/approved/denied/executed records.
  - **Safe Mode:** use the four-way vocabulary **safe / monitor / ask / block**, while documenting that it does not replace OS permissions, service scopes, sandboxing, or rollback.
  - **Kill Switch:** add scoped cancellation, first-reason-wins semantics, bounded acknowledgement, and authority-scoped emergency stop. Preserve the limitation that live-operation cancellation is not universal rollback or proof every process stopped.
  - **RBAC:** use short-lived, mission-scoped capability grants with allowlisted tools/server prefixes, revocation, TTL expiry, fail-closed forbidden tools, no connector credentials, and no direct tool handles. Do not claim a generic PersonalJarvis RBAC model exists.
  - **Event Bus:** adopt immutable trace-correlated events, wildcard/flight-recorder observation, and non-blocking observer isolation.
  - **Capability Router:** keep it selection-only; forward utterances verbatim where appropriate, prevent recursive worker spawning, use explicit capability sets, and route execution/approval through GAIA authority.
- **Blockers/boundaries:** No code reuse was selected; no replacement recommendation; no evidence-based rejection of the project. The only explicit non-adoption is a generic RBAC claim because none was verified. Safe Mode and Kill Switch semantics must not be overstated as universal sandbox/rollback/process termination.
- **Sources:** [architecture](https://raw.githubusercontent.com/PersonalJarvis/PersonalJarvis/main/docs/architecture-overview.md), [protocols](https://raw.githubusercontent.com/PersonalJarvis/PersonalJarvis/main/jarvis/core/protocols.py), [risk tier](https://raw.githubusercontent.com/PersonalJarvis/PersonalJarvis/main/jarvis/safety/risk_tier.py), [tool executor](https://raw.githubusercontent.com/PersonalJarvis/PersonalJarvis/main/jarvis/safety/tool_executor.py), [license](https://raw.githubusercontent.com/PersonalJarvis/PersonalJarvis/main/LICENSE), [NOTICE](https://raw.githubusercontent.com/PersonalJarvis/PersonalJarvis/main/NOTICE).

### 2. OpenManus — bounded execution and capability lifecycle

- **Classification:** `PATTERN_ADOPTED`.
- **GAIA posture:** Augment, but do not replace, GAIA Core, Permission Layer, Action Host, Safe Mode, Kill Switch, RBAC, Event Bus, or Capability Router; do not directly expose OpenManus MCP, shell, or Python capabilities without GAIA authorization and isolation.
- **License note:** Root project is **MIT**, copyright 2025 manna_and_poem. OpenManus integrates Browser Use, MCP, Daytona, crawl4ai, and charting packages, among others; their licenses were not audited. Source reuse would require preserving MIT notices and reviewing dependency notices. This harvest recommends patterns, not copying.
- **Concrete GAIA improvements:**
  - **Core:** adopt explicit `IDLE/RUNNING/FINISHED/ERROR` lifecycle, `max_steps`, step counters, repeated-output/stuck-loop detection, and `finally`-style sandbox cleanup.
  - **Action Host:** standardize name, description, parameter schema, async execution, and structured success/error results; reject unknown tools, skip duplicate names, and convert tool errors to results.
  - **Capability Router:** use server-scoped MCP IDs such as `mcp_<server>_<tool>`, explicit connect/disconnect, schema refresh, removal on disconnect, and capability provenance—but require GAIA authorization before exposure.
  - **Kill Switch:** add observable, idempotent cooperative terminate/cancel followed by deterministic cleanup; keep GAIA’s authoritative kill path.
  - **Safe Mode:** use resource budgets, child-process termination, workspace scoping, timeout controls, and network-denied defaults; add typed human-decision escalation as an Action Host primitive only after policy authorization.
- **Blockers/boundaries:** No concrete RBAC or policy enforcement was found; tool lookup is not authorization. `PythonExecute` uses `exec` and lacks a true allowlist/syscall policy; shell accepts arbitrary commands and long-lived tmux sessions. These are not security isolation. Termination is cooperative, not a process-level emergency stop. No pub/sub or durable event contract was found, so no OpenManus-shaped Event Bus should be inferred.
- **Sources:** [BaseAgent](https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/agent/base.py), [MCPAgent](https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/agent/mcp.py), [ToolCollection](https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/tool/tool_collection.py), [BaseTool](https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/tool/base.py), [configuration](https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/config.py), [Python execution](https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/tool/python_execute.py), [sandbox shell](https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/app/tool/sandbox/sb_shell_tool.py), [license](https://raw.githubusercontent.com/FoundationAgents/OpenManus/main/LICENSE).

### 3. Microsoft Agent Framework — approvals, hooks, and workflow observability

- **Classification:** `PATTERN_ADOPTED`.
- **GAIA posture:** No replacement of GAIA. Use MAF’s patterns within GAIA authority and policy ownership.
- **License note:** **MIT**, from the repository `LICENSE`, with Microsoft copyright and an “AS IS” disclaimer. Provider SDKs, optional packages such as `agent-hooks-sdk`, transitive dependencies, hosted services, and third-party systems have separate terms; no dependency audit was performed. No MAF code is copied or linked into GAIA.
- **Concrete GAIA improvements:**
  - **Permission Layer:** make approval first-class: structured tool name + arguments, explicit approve/reject resume on the same session, queued requests, and standing approvals scoped to tool, canonicalized exact arguments, and (where relevant) server label. Unmatched rules return for approval rather than auto-approving.
  - **Safe Mode:** add agent/model/tool pre/post hooks, apply transforms back into context, block denied actions, buffer streaming output until verdict, gate durable persistence behind approved verdicts, and fail closed on enforcement/interceptor failure.
  - **Core/Action Host:** compose model/client, function invocation, session/context providers, middleware, approval UX, persistence, and telemetry behind explicit host capabilities while keeping authority in GAIA.
  - **Capability Router/Event Bus:** adopt typed graph envelopes and deterministic routing by capability/type, target, and condition; publish delivery outcomes (delivered, dropped by type/target/condition, exception, buffering) for audit/replay.
  - **RBAC:** use narrow durable tool/argument/server-bound grants as primitives, not as a complete identity/role/tenant authorization system.
- **Blockers/boundaries:** Inspected material does not establish a system-wide Kill Switch, GAIA-style authority Core, or security-complete RBAC. `MiddlewareTermination`/`MiddlewareFailure` are per-run/fail-closed abort mechanisms, not an operator kill switch. Tools run without user approval unless approval is configured; application developers must secure inputs/data flows, rate-limit, and add mitigations. No code integration is evidenced.
- **Sources:** [tool approval](https://learn.microsoft.com/en-us/agent-framework/agents/tools/tool-approval), [agent hooks](https://raw.githubusercontent.com/microsoft/agent-framework/main/python/packages/core/agent_framework/_agent_hooks.py), [middleware](https://raw.githubusercontent.com/microsoft/agent-framework/main/python/packages/core/agent_framework/_middleware.py), [harness](https://learn.microsoft.com/en-us/agent-framework/concepts/harness), [workflow observability](https://learn.microsoft.com/en-us/agent-framework/workflows/observability), [safety](https://learn.microsoft.com/en-us/agent-framework/agents/safety), [license](https://github.com/microsoft/agent-framework/blob/main/LICENSE).

### 4. Hugging Face smolagents — typed steps and pluggable execution

- **Classification:** `PATTERN_ADOPTED`.
- **GAIA posture:** Narrowly adopt control/execution patterns; do not replace any GAIA authority component and do not reuse source.
- **License note:** **Apache License 2.0** from `main/LICENSE`; inspected Python files carry Apache headers. Apache obligations include attribution/NOTICE (if present), modified-file notices, and no trademark grant. Current `main` was checked rather than a pinned release/commit; dependencies, Hub tools, MCP servers, and remote sandbox providers retain their own terms.
- **Concrete GAIA improvements:**
  - **Core:** add typed action-step records containing model input/output, parsed action, tool call, observation, and final answer; add `max_steps`, planning intervals, final-output validation, and continuation semantics without moving authority decisions into the model loop.
  - **Permission Layer:** add capability manifests, schema/signature validation, explicit authorized-import allowlists as least-privilege hints, and a closed registry for persisted capability/agent types.
  - **Action Host:** use a pluggable executor/host interface for local/Docker/remote backends with cleanup, quotas, credential scoping, and approved-backend selection.
  - **Safe Mode:** use defense-in-depth preflight, import/capability allowlists, optional remote isolation, and explicit “not a boundary” labels.
  - **Kill Switch:** add cooperative stop checks between action steps plus GAIA-owned hard termination at Action Host/process boundary.
  - **Event Bus/Router:** emit typed lifecycle events from action-step logs; use capability descriptors/collections and lazy initialization behind GAIA trust, discovery, routing, and authorization.
- **Blockers/boundaries:** The local Python executor is explicitly **not** a security boundary; remote isolation is recommended for real isolation. `additional_authorized_imports=["*"]` is unsafe, `trust_remote_code=True` is an operator trust decision, and local escapes/host filesystem/network access are out of scope. No user/role/tenant RBAC or durable authority bus was found. A local timeout cannot force-kill a running Python thread.
- **Sources:** [LICENSE](https://raw.githubusercontent.com/huggingface/smolagents/main/LICENSE), [repository](https://github.com/huggingface/smolagents), [security policy](https://github.com/huggingface/smolagents/blob/main/SECURITY.md).

### 5. Jared fullstack-agent — deterministic setup and non-destructive operations

- **Classification:** `PATTERN_ADOPTED`.
- **GAIA posture:** Adopt bounded orchestration, consent, lifecycle, signal, and update patterns as GAIA-native designs; do not replace GAIA or copy project code.
- **License note:** **AGPL-3.0-or-later**, confirmed by API metadata, README, full `LICENSE`, and SPDX headers. Modified versions conveyed or run as a service must remain under the same license with source available; closed-source commercial questions are directed to the author. The four component repositories’ licenses were not reviewed. Any future code reuse requires AGPL compatibility/legal review.
- **Concrete GAIA improvements:**
  - **Core/Capability Router:** perform one interview, then deterministic fixed-order orchestration; produce an explicit capability manifest; support explicit `all`, `voice`, and `hands` profiles.
  - **Permission Layer:** default action consent to `ask`; distinguish microphone mode from action consent; make bypass an explicit opt-in; enforce through GAIA policy rather than prompt text.
  - **Action Host/Kill Switch:** record owned child PIDs, trap exit/int/term, kill only exact children started by the invocation, and avoid killing unrelated processes sharing a port. Treat this as scoped operational cleanup, not a complete kill switch.
  - **Event Bus:** use an inspectable one-direction local status seam for low-risk UI signals, with GAIA-owned validation, integrity, retention, and authorization; do not infer durable delivery/authentication/atomic writes.
  - **Safe Mode/Core:** preserve user artifacts, ask before scanning beyond approved paths, copy rather than move custom content, support idempotent reruns and resume, and use preview-before-apply updates with fast-forward-only behavior, config/data separation, and local-edits-win handling.
- **Blockers/boundaries:** The project is primarily Markdown instructions and launch/update scripts, not an authorization/policy engine. Component repositories and Claude Code runtime enforcement were not inspected, so their permissions/security/event behavior is unverified. The latest `main` commit was unsigned and there are no GitHub releases. No generic RBAC implementation was found; identity is configuration/personality, not access control.
- **Sources:** [repository](https://github.com/jaredrhod/fullstack-agent), [conductor](https://raw.githubusercontent.com/jaredrhod/fullstack-agent/main/fullstack-agent.md), [start.sh](https://raw.githubusercontent.com/jaredrhod/fullstack-agent/main/start.sh), [update.sh](https://raw.githubusercontent.com/jaredrhod/fullstack-agent/main/update.sh), [license](https://raw.githubusercontent.com/jaredrhod/fullstack-agent/main/LICENSE).

### 6. Jared ai-memory-vault — transactional memory and bounded context

- **Classification:** `PATTERN_ADOPTED`.
- **GAIA posture:** Adopt bounded patterns behind GAIA authority; do not use the vault or its prompt/build files as control-plane code.
- **License note:** **CC BY-SA 4.0** (`CC-BY-SA-4.0`), confirmed by metadata and `LICENSE`; README identifies copyright © 2026 Jared Rhodenizer and permits commercial use. Adaptation requires attribution, notices, modification indication, and ShareAlike. No per-file licensing map or dependency inventory was found; adapted repository material requires legal review.
- **Concrete GAIA improvements:**
  - **Core:** add a small pinned boot manifest for identity, memory location, startup sequence, and invariants; maintain a human-readable root index and re-read the authoritative index after context compaction.
  - **Permission Layer/RBAC:** make source/config edits read-only by default; require explicit confirmation for code/config/commit/push/deploy; keep scope narrow and make personal profile sections opt-in. Treat these as GAIA policy gates, not a role matrix.
  - **Action Host/Safe Mode:** preflight reachability/writability; never create over existing data; back up before every edit; merge rather than replace; use a real serializer; verify target path and preservation of prior entries; if verification fails, restore backup and stop.
  - **Event Bus:** use append-only daily/session records and checkpoints as an audit/event-log pattern only.
  - **Capability Router:** route task-specific “Jobs” to only the notes/context slice needed for the task.
- **Blockers/boundaries:** Markdown is an untrusted instruction payload, not an enforcement boundary. No cryptographic capability model, RBAC engine, Event Bus, Kill Switch, or isolated Action Host is implemented. Historical failures include shell escaping corrupting valid JSON, conditional backups, parse-only validation destroying writes, half-finished installs appearing complete, and redirects landing in the wrong project folder. Do not adopt its personality, automatic installation, broad shell/file writes, or self-maintaining prompt authority as GAIA control logic.
- **Sources:** [repository](https://github.com/jaredrhod/ai-memory-vault), [README](https://github.com/jaredrhod/ai-memory-vault/blob/main/README.md), [build/instructions](https://github.com/jaredrhod/ai-memory-vault/blob/main/ai-memory-vault.md), [license](https://github.com/jaredrhod/ai-memory-vault/blob/main/LICENSE).

### 7. Jared backtalk — voice approval, interruption, and status events

- **Classification:** `PATTERN_ADOPTED`.
- **GAIA posture:** Adopt authority, approval, interruption, and event-contract patterns inside existing GAIA components; do not embed backtalk or treat configuration as authority.
- **License note:** **AGPL-3.0-or-later**, copyright Jared Rhodenizer (2026), verified from `LICENSE`, README, and SPDX headers. README states network-served modified versions must provide source and invites contact for closed-source commercial use. No separate commercial exception or contributor-license grant was verified. Verification is repository-level on mutable `main`, not an independent provenance audit.
- **Concrete GAIA improvements:**
  - **Permission Layer:** default `permission_mode: "ask"`; summarize actions plainly; expose literal command/path details; approve only exact allowlisted affirmative phrases; deny every other answer and pass the reason back; timeout/silence (~75 seconds) denies.
  - **Action Host:** put one long-lived session behind a single tool gate; make cwd and allowed extra directories explicit; allow read-only work without unnecessary approval interruption.
  - **Safe Mode:** keep push-to-talk as default; make open-mic explicit and warned; separate auto-approve from hands-free microphone mode.
  - **Kill Switch:** support immediate interruption by key/quit/Ctrl-C; deny pending permission requests on interruption; drain stale stream messages and rebuild a fresh session if alignment cannot be repaired.
  - **Event Bus:** translate idle/listening/thinking/speaking, waveform, loading PID, direction, completion, and rate-limit signals into typed GAIA events with authorization/audit metadata; preserve non-blocking/best-effort telemetry behavior without using files as authority.
  - **Capability Router/Core:** render tool-specific intent with optional full details; reserve exact phrases for control actions; keep transport/presentation separate from Core identity and authority.
- **Blockers/boundaries:** No RBAC, identity, role hierarchy, tenant isolation, or role grants; `extra_dirs` and `visible_skills` are reach/context filters, not sandbox/RBAC. Filesystem signals are unauthenticated and non-atomic. AGPL posture blocks casual code reuse. No code was copied or integrated.
- **Sources:** [README](https://raw.githubusercontent.com/jaredrhod/backtalk/main/README.md), [main.py](https://raw.githubusercontent.com/jaredrhod/backtalk/main/backtalk/main.py), [brain.py](https://raw.githubusercontent.com/jaredrhod/backtalk/main/backtalk/brain.py), [signals.py](https://raw.githubusercontent.com/jaredrhod/backtalk/main/backtalk/signals.py), [license](https://raw.githubusercontent.com/jaredrhod/backtalk/main/LICENSE).

### 8. Jared ai-visualizer — read-only telemetry and renderer contracts

- **Classification:** `PATTERN_ADOPTED`.
- **GAIA posture:** Keep GAIA authority unchanged. Treat this as an optional read-only visualization/telemetry consumer or design reference—not an authority, executor, or permission system.
- **License note:** **AGPL-3.0-or-later**, with the bundled `assets/VT323-OFL.txt` separately under **SIL Open Font License 1.1**. `face.png` and `thinking.wav` have no clearly separate license notice in the inspected repository; reuse rights are uncertain and they should not be copied. AGPL network-source obligations mean direct incorporation requires separate legal review. No code/media was copied.
- **Concrete GAIA improvements:**
  - **Core/Event Bus:** define a versioned, minimum read-only telemetry contract (state, level, waveform, alert/loading) with enum values, timestamps, freshness/TTL, malformed-input fallback, and read-only subscribers.
  - **Safe Mode/QA:** retain mock/demo/shot modes for deterministic UI tests and screenshots, explicitly labeled as simulated state rather than live authority.
  - **Capability Router:** use declarative renderer manifests and a narrow read-only view-model API; keep renderer discovery separate from capability/action registration.
  - **Optional local host:** bind loopback by default, expose only GET/static reads, enforce resolved-path containment, and isolate user configuration from update-managed code.
  - **UI architecture:** normalize telemetry once in a shared adapter so multiple views agree on smoothing/state/usage formatting; reject stale/missing data to inert state.
- **Blockers/boundaries:** No POST/action routes, subprocess execution, tool invocation, or state mutation; therefore no Action Host capability. No authorization, RBAC, or stop/revoke/quarantine endpoint. Localhost/path confinement is not a complete security boundary. Uncertain rights for bundled media block copying.
- **Sources:** [README](https://raw.githubusercontent.com/jaredrhod/ai-visualizer/main/README.md), [server](https://raw.githubusercontent.com/jaredrhod/ai-visualizer/main/server.py), [core.js](https://raw.githubusercontent.com/jaredrhod/ai-visualizer/main/core.js), [license](https://raw.githubusercontent.com/jaredrhod/ai-visualizer/main/LICENSE).

### 9. Jared barehands — narrow command protocol and state freshness

- **Classification:** `PATTERN_ADOPTED`.
- **GAIA posture:** Adopt authority/safety patterns inside GAIA; do not replace GAIA and do not copy implementation.
- **License note:** **AGPL-3.0-or-later**, with README/source headers and GitHub metadata reporting AGPL-3.0. README identifies MediaPipe as Apache-2.0 and three.js as MIT CDN dependencies; versions were not pinned. The GitHub SPDX field does not encode the README’s “or later” wording. No AGPL code integration is requested.
- **Concrete GAIA improvements:**
  - **Core:** retain separation between AI/core and UI/action body; drive replaceable device adapters with typed intents.
  - **Permission Layer:** configure capability/resource roots; canonicalize paths and prove containment before read/stage; keep note reads read-only; reject invalid requests clearly; require actor context rather than relying on path strings or localhost.
  - **Action Host:** use a typed command envelope, fixed allowlist, bounded queue drain (the observed tracker consumes at most eight commands), and explicit 2xx/4xx outcomes behind authorization, rate limits, audit, and cancellation.
  - **Safe Mode:** fail softly when optional state is absent; decay non-idle status to idle/unknown after a timeout; expose empty/disconnected/degraded states truthfully.
  - **Event Bus:** separate latest snapshot/heartbeat from queued command delivery; add event IDs, ordering, acknowledgement, replay policy, and audit metadata.
  - **Capability Router:** route high-level verbs through one canonical dispatcher and reject unknown verbs centrally; map verbs to declared capabilities and permissions.
  - **Kill Switch:** retain a user-visible clear/reset affordance only as UI behavior; keep GAIA’s independent cancellation/revocation/emergency stop.
  - **RBAC:** explicitly keep capability allowlisting distinct from actor/role authorization, and supply identity, grants, per-action checks, and revocation in GAIA.
- **Blockers/boundaries:** `/cmd` has no authentication or per-caller identity; any process reaching localhost can submit an allowlisted action. Media jail is containment, not complete security. The service lacks GAIA-grade audit, RBAC, cancellation, and emergency stop. No code was reused.
- **Sources:** [README](https://github.com/jaredrhod/barehands/blob/main/README.md), [server.py](https://raw.githubusercontent.com/jaredrhod/barehands/main/server.py), [board.sh](https://raw.githubusercontent.com/jaredrhod/barehands/main/bin/board.sh), [board-state.sh](https://raw.githubusercontent.com/jaredrhod/barehands/main/bin/board-state.sh), [license](https://github.com/jaredrhod/barehands/blob/main/LICENSE).

### 10. Browser Use + Pipecat — typed capability envelopes and priority control

- **Classification:** `PATTERN_ADOPTED`.
- **GAIA posture:** Adopt design patterns inside GAIA’s existing authority chain. Do not embed Browser Use browser/MCP control as an authority, treat Pipecat’s bus as RBAC, or replace GAIA Core/Permission Layer.
- **License note:** Browser Use repository is **MIT**, copyright 2024 Gregor Zunic. Pipecat is **BSD 2-Clause**, copyright 2024–2026 Daily. Verification covers top-level `LICENSE` files on `main`, not every dependency, integration, generated artifact, or hosted service; Browser Use hosted services/data policy and Pipecat Cloud are separate components. Recheck exact commits and dependency notices before reuse or redistribution. No source code is copied.
- **Concrete GAIA improvements:**
  - **Permission Layer/Capability Router:** adopt typed action registries with stable names, descriptions, Pydantic-like input schemas, human-readable purpose, domain/resource scope, and explicit terminal-risk flag; validate before dispatch. Treat schemas as data, not authorization.
  - **Action Host:** inject only minimal capability-scoped context (session, CDP, filesystem/approved paths, sensitive-data presence); do not expose whole Core or ambient credentials.
  - **Permission Layer/Safe Mode:** add per-capability allowed/prohibited domains, blocked IP policy, default-deny network/file targets, and defense-in-depth resource restrictions; keep RBAC, approval, and Kill Switch separate.
  - **Safe Mode/Kill Switch:** standardize per-action deadlines, retry/failure budgets, step timeouts, externally polled stop callbacks, and a Kill Switch outside the model/tool path.
  - **Event Bus:** adopt typed, priority-aware lanes: revocation/cancellation/shutdown must not wait behind ordinary results; distinguish graceful drain from immediate cancel.
  - **Event Bus/Router/RBAC:** add source/target/correlation fields, targeted versus broadcast semantics, worker readiness/health events, and lifecycle/job/progress/cancellation messages; bus addressability does not grant permission.
  - **Action Host/audit:** separate short deterministic authority hooks from asynchronous retryable telemetry sinks; track tasks and persist cleanup/audit exactly once at the terminal boundary; support idle expiry.
- **Blockers/boundaries:** Browser/MCP access needs trusted clients and sandboxing; allowlists are not complete trust boundaries. Pipecat bus routing is not RBAC. Authority-revocation events must remain interruptible even when prioritized. Graceful stop, immediate cancellation, idle expiry, and cleanup semantics must remain GAIA-owned.
- **Sources:** [Browser Use registry](https://github.com/browser-use/browser-use/blob/main/browser_use/tools/registry/service.py), [Browser Use profiles](https://github.com/browser-use/browser-use/blob/main/browser_use/browser/profile.py), [Browser Use stop controls](https://github.com/browser-use/browser-use/blob/main/browser_use/agent/service.py), [Pipecat frame overview](https://docs.pipecat.ai/api-reference/server/frames/overview), [Pipecat termination](https://docs.pipecat.ai/pipecat/learn/pipeline-termination), [Pipecat agent bus](https://docs.pipecat.ai/pipecat/fundamentals/agent-bus), [Browser Use license](https://raw.githubusercontent.com/browser-use/browser-use/main/LICENSE), [Pipecat license](https://raw.githubusercontent.com/pipecat-ai/pipecat/main/LICENSE).

## Cross-harvest GAIA improvement backlog

The individual harvests converge on a small set of additive improvements. These are **recommendations only**; this report does not state that any have been implemented.

### Priority 1 — authority and action safety

1. **Shared typed capability envelope:** stable capability ID, typed schema/signature, actor/context, resource/domain scope, canonical arguments, risk/termination metadata, correlation ID, deadline, and provenance.
2. **One Action Host chokepoint:** no direct tool execution; enforce evaluate → preflight → approval → execute → postcondition/audit; return structured success/error envelopes.
3. **Exact-call approval receipts:** deterministic precedence, argument-sensitive risk, canonicalized arguments, one-call scope by default, explicit standing-grant TTLs, and fail-closed policy/interceptor failure.
4. **Fail-closed transactional writes:** preflight, backup before every edit, merge/serialize, verify, restore-and-stop on uncertainty, with preview-before-apply and copy-before-replace.
5. **Independent cancellation path:** high-priority revocation lane, external stop polling, cooperative step checks, hard process/host termination where available, bounded acknowledgement, and exactly-once terminal cleanup/audit.

### Priority 2 — bounded execution and routing

6. **Bounded Core lifecycle:** explicit states, step/retry/deadline budgets, stuck-loop detection, output validation, and deterministic teardown.
7. **Capability lifecycle:** server-scoped IDs, closed registries, provenance, connect/disconnect, schema refresh, lazy initialization, readiness/health events, and recursion guards.
8. **Scope separation:** distinct flags and policies for microphone/hands-free, auto-approval, network/file access, renderer telemetry, and action authority.
9. **Context minimization:** inject only approved capability-scoped context; route task-specific memory rather than whole-vault/whole-Core context.

### Priority 3 — observability and UI boundaries

10. **Typed Event Bus:** immutable trace/correlation fields, source/target, targeted/broadcast semantics, priority lanes, lifecycle/delivery outcomes, event IDs, ordering/ack/replay policy, and separate synchronous authority hooks from asynchronous telemetry.
11. **Read-only telemetry adapter:** freshness/TTL, stale/malformed fallback to inert/unknown state, shared normalization for many views, renderer manifests, loopback/path confinement, and deterministic mock/shot QA modes.
12. **Explicit negative guarantees:** document that allowlists, localhost, prompt instructions, UI reset, local interpreters, and filesystem signal files are not substitutes for identity, RBAC, authorization, sandboxing, audit, or Kill Switch semantics.

## Licensing and integration conclusion

- All ten harvests remain **`PATTERN_ADOPTED`**.
- No harvest supplies evidence of code copied, linked, or integrated into GAIA. The external license notes are therefore recorded for provenance and future review, not as a claim of current third-party dependency inclusion.
- If future implementation reuses source, text, assets, or generated artifacts, conduct file-level provenance and dependency review first. Particular review triggers are **AGPL-3.0-or-later** (fullstack-agent, backtalk, ai-visualizer, barehands), **CC BY-SA 4.0** (ai-memory-vault), Apache/MIT/BSD notice obligations, uncertain visualizer media rights, and hosted-service/third-party terms.
- The practical recommendation is to implement GAIA-native equivalents behind GAIA’s existing authority chain, with tests and provenance records, rather than importing external control planes.

## Source reports

- [harvest-01-personaljarvis.md](./harvest-01-personaljarvis.md)
- [harvest-02-openmanus.md](./harvest-02-openmanus.md)
- [harvest-03-microsoft-agent-framework.md](./harvest-03-microsoft-agent-framework.md)
- [harvest-04-smolagents.md](./harvest-04-smolagents.md)
- [harvest-05-fullstack-agent.md](./harvest-05-fullstack-agent.md)
- [harvest-06-ai-memory-vault.md](./harvest-06-ai-memory-vault.md)
- [harvest-07-backtalk.md](./harvest-07-backtalk.md)
- [harvest-08-ai-visualizer.md](./harvest-08-ai-visualizer.md)
- [harvest-09-barehands.md](./harvest-09-barehands.md)
- [harvest-10-browser-use-pipecat.md](./harvest-10-browser-use-pipecat.md)
