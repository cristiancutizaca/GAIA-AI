# Harvest 09 — Jared barehands

- **ID:** `harvest-09-barehands`
- **Repository:** [jaredrhod/barehands](https://github.com/jaredrhod/barehands), `main`
- **Classification:** `PATTERN_ADOPTED`
- **GAIA action:** Adopt the concrete authority/safety patterns below inside GAIA's existing Core and authority model; do not replace GAIA with barehands and do not copy its implementation.

## What was verified

The current README describes a webcam/Chrome hand-tracked glass board with a stdlib-only Python localhost server. The current tree includes `server.py`, `stage.html`, `bin/board.sh`, `bin/board-state.sh`, `barehands.md`, `TROUBLESHOOTING.md`, `state/README.md`, and `barehands.json.example`. The agent-facing document explicitly treats barehands as a “body” with an external AI as its “brain.”

`server.py` exposes a local command/state protocol: `POST /cmd`, `POST /state` (tracker heartbeat and command dequeue), `GET /state` (last scene snapshot), read-only jailed note/tree endpoints, `/props`, `/config`, and `/orb`. Commands are checked against a fixed `_ALLOWED` list; media commands are resolved against a configured media root and rejected when the resolved file is not inside that root. `board.sh` is a thin localhost client and `board-state.sh` is a read-only state projection for the agent. The repository's documented local boundary is useful, but localhost is not an actor-authentication boundary.

## Concrete patterns GAIA can adopt

| GAIA authority area | Adoptable pattern | GAIA-specific boundary |
|---|---|---|
| **Core** | Keep the AI/core separate from the UI/action body. Treat renderers and device adapters as replaceable bodies driven by typed intents. | GAIA Core remains the authority; barehands supplies no policy, planning, identity, or durable authority. |
| **Permission Layer** | Use configured capability/resource roots; resolve paths first, then prove containment before reading/staging; keep note reads read-only and reject invalid requests with a clear error. | Implement in GAIA's existing permission layer with canonical resource IDs and actor context; do not rely on a filesystem path string or localhost alone. |
| **Action Host** | Use a narrow local action host with a typed command envelope, a fixed allowlist, bounded queue draining, and explicit 2xx/4xx outcomes. The tracker heartbeat consuming at most eight queued commands is a concrete backpressure pattern. | GAIA Action Host must remain behind GAIA authorization, rate limits, audit, and cancellation. |
| **Safe Mode** | Fail soft when optional state files are absent; make non-idle status decay to idle after a configurable timeout so a crashed writer cannot leave a permanent “thinking” state. Expose explicit empty/disconnected/degraded states to the caller. | GAIA should preserve truthful state and surface the timeout as stale/unknown in audit, rather than silently treating it as successful completion. |
| **Event Bus** | Separate a latest snapshot/heartbeat from a queued command channel: consumers can render the newest state while commands are delivered incrementally. | Map this to GAIA's typed event bus with event IDs, ordering/acknowledgement, replay policy, and audit metadata. |
| **Capability Router** | Route high-level verbs (`present`, `add_card`, `add_img`, `reset`, etc.) through one canonical dispatcher and reject unknown verbs centrally. | GAIA's router must map verbs to declared capabilities and permissions; the barehands allowlist by itself is not authorization. |
| **Kill Switch** | Retain the idea of a prominent user-visible `clear/reset` affordance for the board. | This is only a UI reset, not a GAIA kill switch: it does not halt the agent, revoke tokens, cancel in-flight work, or prevent new actions. GAIA must keep its independent kill switch. |
| **RBAC** | No RBAC implementation was found. The useful negative pattern is to keep capability allowlisting distinct from actor/role authorization. | Do not claim barehands provides RBAC. GAIA must supply identity, role/capability grants, per-action authorization, and revocation. |

## Security/licensing disposition

The source is suitable as a **pattern reference only**. The service has no authentication or per-caller identity on `/cmd`; any process able to reach the bound localhost port can submit an allowlisted action. Its media jail is a useful containment pattern but is not a complete security boundary, and the project does not provide GAIA-grade audit, RBAC, cancellation, or emergency stop semantics.

**Verified license:** `GNU Affero General Public License v3.0`, with the README and source headers stating **AGPL-3.0-or-later**; GitHub repository metadata reports SPDX `AGPL-3.0`. Copyright notice: Jared Rhodenizer, 2026. README also identifies MediaPipe (Apache 2.0) and three.js (MIT) as CDN-loaded dependencies that the repository does not redistribute. No barehands code is reused in GAIA under this harvest, so no AGPL integration approval is requested.

**Uncertainty:** License verification is based on the current `main` README, `LICENSE`, source headers, and GitHub API metadata (current tree SHA observed: `eb23bed2d772f9d5a24de26fb92f46c3c76d69cf`). The GitHub SPDX field says `AGPL-3.0` and does not encode the README's “or later” wording; this is not a legal opinion. Dependency versions loaded from public CDNs are also not pinned in the inspected README.

## Sources

- [README.md](https://github.com/jaredrhod/barehands/blob/main/README.md)
- [barehands.md](https://github.com/jaredrhod/barehands/blob/main/barehands.md)
- [server.py](https://raw.githubusercontent.com/jaredrhod/barehands/main/server.py)
- [board.sh](https://raw.githubusercontent.com/jaredrhod/barehands/main/bin/board.sh) and [board-state.sh](https://raw.githubusercontent.com/jaredrhod/barehands/main/bin/board-state.sh)
- [TROUBLESHOOTING.md](https://raw.githubusercontent.com/jaredrhod/barehands/main/TROUBLESHOOTING.md)
- [state/README.md](https://raw.githubusercontent.com/jaredrhod/barehands/main/state/README.md)
- [LICENSE](https://github.com/jaredrhod/barehands/blob/main/LICENSE)
- [GitHub repository metadata](https://api.github.com/repos/jaredrhod/barehands)
