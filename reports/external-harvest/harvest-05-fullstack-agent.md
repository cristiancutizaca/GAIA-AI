# Harvest 05 — Jared `fullstack-agent`

- **ID:** `harvest-05-fullstack-agent`
- **Project:** [`jaredrhod/fullstack-agent`](https://github.com/jaredrhod/fullstack-agent)
- **Reviewed revision:** `main` at `5bb159f47dbd6fa8f108651d0532a43aef16346b` (latest commit exposed by GitHub API; 2026-08-30). Repository metadata was updated 2026-10-04.
- **Classification:** `PATTERN_ADOPTED`
- **GAIA action:** Adopt the bounded orchestration, consent, lifecycle, signal, and non-destructive-update patterns below as GAIA-native designs. Do **not** replace GAIA Core, Permission Layer, Action Host, Safe Mode, Kill Switch, RBAC, Event Bus, or Capability Router; no project code is copied.

## What the project is

A Claude Code-only installer/conductor that assembles four sibling repositories: persistent text-file memory (`ai-memory-vault`), voice (`backtalk`), visualizer (`ai-visualizer`), and optional webcam “hands” (`barehands`). Its own code is primarily Markdown instructions plus POSIX/Windows launch/update scripts; it is not an authorization or policy engine.

## Concrete patterns GAIA can adopt

1. **One interview, then deterministic orchestration (Core / Capability Router).** `fullstack-agent.md` collects identity, vault, microphone, voice-engine, face, and permission choices once, then supplies those answers to each component wizard in a fixed order. Optional pieces are selected explicitly; launcher modes (`all`, `voice`, `hands`) compose only the requested capabilities. Adopt as a GAIA setup/profile flow that produces an explicit capability manifest, not as a replacement for GAIA Core or Router.
2. **Conservative consent as the default (Permission Layer).** The installer distinguishes microphone mode from action consent and defaults action consent to `ask`: the agent asks aloud before writing a file or running a command; `bypassPermissions` is an explicit opt-in. It also documents a reversible change back to confirmation. Adopt the UX and policy shape, while enforcing consent in GAIA’s existing Permission Layer rather than relying on prompt text.
3. **Explicit process ownership and scoped shutdown (Action Host / Kill Switch).** `start.sh` records child PIDs, traps `EXIT/INT/TERM`, and kills only processes it started; the handoff instructions explicitly warn not to kill an unrelated process that merely owns a port. `Ctrl-C` is the documented stop path. Adopt per-invocation process ownership, exact-child cleanup, and an emergency stop that does not target unrelated services. This is a useful operational kill pattern, not a complete authority kill switch.
4. **File-backed, one-direction status seam (Event Bus).** The visualizer reads voice status artifacts (`.voice_state`/`.voice_waveform`) from a configured `bus_dir`; troubleshooting says to configure one direction only and restart after config changes. Adopt a small, inspectable local event channel for low-risk UI/status signals, with GAIA-owned validation, integrity, retention, and authorization. The repository does not specify durable delivery, authentication, replay, or atomic-write guarantees.
5. **Non-destructive adoption, bounded filesystem scope, and resumable setup (Safe Mode / Core).** The wizard says never delete/overwrite/move user-built artifacts, asks before scanning outside the home or user-supplied paths, copies rather than moves custom scenes, and treats reruns as safe/idempotent. `claude --continue` resumes interrupted setup. Adopt these invariants for GAIA onboarding/migrations: explicit scope, copy-before-replace, resumability, and user-visible preservation.
6. **Preview-before-apply updates (Safe Mode / Action Host).** `update.sh` lists incoming commits before pulling, uses `--ff-only`, preserves personal config files outside tracked content, and keeps a user config on a one-time migration. Adopt change preview, fast-forward-only default, config/data separation, and “local edits win” handling for GAIA-managed updates.

## GAIA authority-model comparison

| GAIA authority | Evidence in `fullstack-agent` | GAIA disposition |
|---|---|---|
| **Core** | Markdown conductor owns phases, ordering, answers, wiring, and handoff. | Adopt the orchestration pattern inside GAIA Core; do not replace Core. |
| **Permission Layer** | Explicit `ask` vs `bypassPermissions`; default ask and spoken confirmation. | Adopt as a consent UX/policy input; GAIA must enforce it. |
| **Action Host** | Shell/Batch launchers start sibling services and own their lifecycle. | Adopt exact child ownership and bounded execution; keep GAIA Action Host authoritative. |
| **Safe Mode** | Non-destructive adoption, path-bound scanning, rerunnable/resumable setup, preview-before-apply updates. | Adopt these safeguards as GAIA Safe Mode invariants. |
| **Kill Switch** | `Ctrl-C` plus PID cleanup stops processes started by the launcher. | Adopt scoped process cleanup as one implementation detail; no global kill authority is present. |
| **RBAC** | No roles, subjects, tenant boundaries, policy evaluation, or role-to-capability matrix; identity in `CLAUDE.md` is personality/configuration, not access control. | No adoptable RBAC implementation found. Retain GAIA RBAC. |
| **Event Bus** | Configured `bus_dir` and voice state/waveform files connect voice to visualizer. | Adopt only the inspectable local status-channel pattern; do not treat it as a secure/general event bus. |
| **Capability Router** | Menu-driven component selection plus `all`/`voice`/`hands` launcher modes. | Adopt explicit capability profiles/mode routing; GAIA Router remains the authority for capability grants. |

## License and reuse boundary

**Verified:** GNU Affero General Public License v3.0 or later (**AGPL-3.0-or-later**), confirmed by the repository API metadata (`spdx_id: AGPL-3.0`), `README.md`, the full `LICENSE`, and SPDX headers in scripts. README states that modified versions conveyed or run as a service must remain under the same license with source available, and directs closed-source commercial-product questions to the author. This report recommends **patterns only**, not copying or linking project code; any future code reuse requires a separate AGPL compatibility/legal review. The licenses of the four component repositories were not reviewed here.

## Uncertainty / limits

This review covered the current repository README, `CLAUDE.md`, `fullstack-agent.md`, `TROUBLESHOOTING.md`, `CONTRIBUTING.md`, launcher/update scripts, repository metadata, and license. The component repositories and Claude Code’s enforcement/runtime were not inspected, so claims about their internal permissions, security, event semantics, and model/tool behavior remain unverified. The project has no GitHub releases; the latest `main` commit is unsigned per the API response.

## Sources

- [Repository](https://github.com/jaredrhod/fullstack-agent)
- [README](https://raw.githubusercontent.com/jaredrhod/fullstack-agent/main/README.md)
- [`fullstack-agent.md`](https://raw.githubusercontent.com/jaredrhod/fullstack-agent/main/fullstack-agent.md)
- [`CLAUDE.md`](https://raw.githubusercontent.com/jaredrhod/fullstack-agent/main/CLAUDE.md)
- [`TROUBLESHOOTING.md`](https://raw.githubusercontent.com/jaredrhod/fullstack-agent/main/TROUBLESHOOTING.md)
- [`start.sh`](https://raw.githubusercontent.com/jaredrhod/fullstack-agent/main/start.sh)
- [`update.sh`](https://raw.githubusercontent.com/jaredrhod/fullstack-agent/main/update.sh)
- [`LICENSE`](https://raw.githubusercontent.com/jaredrhod/fullstack-agent/main/LICENSE)
- [GitHub repository API metadata](https://api.github.com/repos/jaredrhod/fullstack-agent)
- [Latest `main` commit API record](https://api.github.com/repos/jaredrhod/fullstack-agent/commits/main)
