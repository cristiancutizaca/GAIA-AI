# Harvest 10 — Browser Use + Pipecat

**Classification: `PATTERN_ADOPTED`**

This harvest found reusable **design patterns**, not a reason to replace GAIA's Core, Permission Layer, Action Host, Safe Mode, Kill Switch, RBAC, Event Bus, or Capability Router. No source code is copied.

## Verified project posture and licenses

- **Browser Use** (`browser-use/browser-use`) is an open-source Python/TypeScript browser-agent library. Its current README separates the local library from hosted agent/browser services and says the library is MIT-licensed. The repository `LICENSE` on `main` is **MIT License**, copyright **2024 Gregor Zunic**. [1] [2]
- **Pipecat** (`pipecat-ai/pipecat`) is an open-source Python framework for real-time voice/multimodal agents. Its repository `LICENSE` on `main` is **BSD 2-Clause**, copyright **2024–2026 Daily**. [3] [4]
- **Uncertainty:** license verification covers the two repositories' top-level `LICENSE` files as fetched from `main`, not every dependency, bundled integration, generated artifact, or hosted service. Browser Use explicitly says its hosted services/data policy is separate from the MIT library; Pipecat Cloud is likewise a separate hosted component. Recheck the exact commit and dependency notices before any code reuse or redistribution.

## Concrete patterns GAIA can adopt

1. **Typed action registry with generated schemas — Permission Layer + Capability Router.** Browser Use's `Registry.action(...)` turns a function into a named action with a description, a Pydantic parameter model, optional domain filters, and a termination flag; `execute_action` validates parameters before dispatch and builds an allowlisted action model for the current URL. [5] GAIA can apply the same pattern to capability declarations: every capability has a stable name, typed input schema, human-readable purpose, resource/domain scope, and an explicit terminal-risk flag. GAIA's existing Permission Layer remains the final decision point; the schema is not authorization.

2. **Minimal injected execution context — Action Host.** Browser Use only injects special objects such as the browser session, CDP client, file system, available paths, and sensitive-data presence into the action call, and its registry distinguishes special parameters from user parameters. [5] GAIA's Action Host should pass the smallest capability-scoped context possible, rather than exposing the whole Core or ambient credentials to an action.

3. **Defense-in-depth resource restrictions — Permission Layer + Safe Mode.** Browser Use supports action-level `allowed_domains` and profile-level `allowed_domains`, `prohibited_domains`, and optional `block_ip_addresses`; its MCP documentation warns that the server has browser/filesystem access and recommends trusted clients and sandboxing. [6] [7] GAIA can add equivalent per-capability resource scopes and default-deny network/file targets. These are guardrails, not a complete trust boundary or a substitute for RBAC, human approval, or the Kill Switch; the report does not treat an allowlist as proof of safety.

4. **Bounded execution and external stop polling — Safe Mode + Kill Switch.** Browser Use exposes `step_timeout`, `max_failures`, and an async `register_should_stop_callback`; the callback marks the agent stopped and interrupts the run, while step execution is wrapped in a timeout. [8] GAIA can standardize per-action/per-step deadlines, retry budgets, and an externally polled stop signal. The Kill Switch must remain outside the model/tool path and must preempt ordinary work.

5. **Typed, priority-aware event lanes — Event Bus + Kill Switch.** Pipecat separates `DataFrame`, `ControlFrame`, and high-priority `SystemFrame` traffic. System frames are ordered ahead of normal work and are not discarded by interruption; `CancelFrame` performs immediate shutdown, while `EndFrame` drains queued work for graceful termination. [9] [10] GAIA can use typed event envelopes and a priority lane so revocation, cancellation, and shutdown cannot wait behind ordinary capability results. Do not mark authority-revocation events as uninterruptible.

6. **Targeted and broadcast bus messages with readiness discovery — Event Bus + Capability Router + RBAC.** Pipecat's worker bus has source/target addressing, broadcast messages, typed lifecycle/job/progress/cancellation messages, and a worker registry with readiness notifications. [11] GAIA can adopt source/target/correlation fields, explicit broadcast-vs-targeted semantics, and capability-worker readiness/health events. Authorization still belongs to GAIA RBAC and the Permission Layer; bus addressability alone is not permission.

7. **Ordered lifecycle hooks with sync/async distinction — Event Bus + auditability.** Pipecat exposes lifecycle and processor events through handlers; synchronous handlers are for fast inline decisions, while asynchronous handlers are for logging/I/O and do not block the caller. [12] GAIA can separate authority-path hooks (short, deterministic, fail-closed where required) from audit/telemetry sinks (async, retryable, and non-authoritative).

8. **Graceful stop, immediate cancel, idle expiry, and one cleanup point — Safe Mode + Kill Switch + Action Host.** Pipecat's worker supports setup/start timeouts, idle timeout cancellation, task-manager tracking, and an `on_pipeline_finished` hook that runs after normal end, cancellation, or stop. [13] GAIA can distinguish graceful completion from emergency revocation, expire idle sessions, track spawned tasks, and make cleanup/idempotent audit persistence happen exactly once at the terminal boundary.

## GAIA decision

Adopt the patterns above inside GAIA's existing authority chain. Do **not** embed Browser Use's browser/MCP control surface as an authority, do **not** treat Pipecat's bus as an RBAC system, and do **not** replace GAIA Core or its Permission Layer. The most valuable near-term pattern is a shared typed capability envelope with scope, deadline, correlation ID, risk/termination metadata, and a high-priority revocation path.

## References

[1]: https://github.com/browser-use/browser-use "Browser Use current README"
[2]: https://raw.githubusercontent.com/browser-use/browser-use/main/LICENSE "Browser Use MIT license"
[3]: https://github.com/pipecat-ai/pipecat "Pipecat current README"
[4]: https://raw.githubusercontent.com/pipecat-ai/pipecat/main/LICENSE "Pipecat BSD 2-Clause license"
[5]: https://github.com/browser-use/browser-use/blob/main/browser_use/tools/registry/service.py "Browser Use action registry source"
[6]: https://github.com/browser-use/browser-use/blob/main/browser_use/browser/profile.py "Browser Use browser profile restrictions"
[7]: https://docs.browser-use.com/open-source/customize/integrations/mcp-server "Browser Use local MCP security and tool surface"
[8]: https://github.com/browser-use/browser-use/blob/main/browser_use/agent/service.py "Browser Use agent stop callbacks and bounded steps"
[9]: https://docs.pipecat.ai/api-reference/server/frames/overview "Pipecat frame categories and priority semantics"
[10]: https://docs.pipecat.ai/pipecat/learn/pipeline-termination "Pipecat graceful versus immediate termination"
[11]: https://docs.pipecat.ai/pipecat/fundamentals/agent-bus "Pipecat worker bus routing and message types"
[12]: https://docs.pipecat.ai/api-reference/server/events/overview "Pipecat lifecycle event handlers"
[13]: https://github.com/pipecat-ai/pipecat/blob/main/src/pipecat/pipeline/worker.py "Pipecat PipelineWorker lifecycle and cleanup hooks"
