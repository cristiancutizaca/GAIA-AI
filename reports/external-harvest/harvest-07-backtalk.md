# Harvest 07 — Jared backtalk

- **Project:** [jaredrhod/backtalk](https://github.com/jaredrhod/backtalk)
- **Observed branch:** `main`; GitHub tree SHA observed: `84b3a6cd321060cabb74aad6ebe794621cf99bd3`
- **Classification:** `PATTERN_ADOPTED`
- **GAIA action:** Adopt the concrete authority, approval, interruption, and event-contract patterns below inside GAIA’s existing Core/Permission Layer/Action Host/Safe Mode/Kill Switch/Event Bus/Capability Router. Do **not** replace GAIA, directly embed backtalk, or treat its configuration as an authority model.

## What was inspected

The current README, repository tree, `backtalk.md`, `TROUBLESHOOTING.md`, and source files `backtalk/main.py`, `brain.py`, `config.py`, `ptt.py`, and `signals.py` were inspected. The tree has no separate `docs/` directory; the two documentation files above are the project’s operational/setup docs. The repository is a voice front end for an existing Claude Code agent: local speech-to-text/TTS, a persistent streaming SDK session, optional visualizer integrations, and a terminal/voice control console.

## Concrete patterns GAIA can adopt

| GAIA authority area | Concrete backtalk pattern | Safe adoption boundary |
|---|---|---|
| **Permission Layer** | Default `permission_mode: "ask"`; tool-specific approval callback; the action is summarized in plain language by code, with `details` exposing the literal command/path; only an exact allowlist of affirmative phrases approves; every other answer denies and is passed back as the reason; silence (~75 seconds) denies. | Reuse the deny-by-default, exact-match, explain-before-approve contract. Keep GAIA’s existing policy source of truth and confirmation UX. |
| **Action Host** | One long-lived SDK client/session routes tool calls through a single `can_use_tool` gate; session cwd and allowed extra directories are explicit configuration; read-only work can proceed without an approval interruption. | Apply as an adapter boundary around GAIA’s existing Action Host, not as a new executor or backend. |
| **Safe Mode** | Push-to-talk is the default: microphone closed except while the key is held; open-mic is an explicit opt-in with warnings about room audio/self-triggering. Auto-approve is clearly separated from microphone “hands-free.” | Preserve GAIA’s Safe Mode semantics and make risky input/approval modes distinct capabilities, never one overloaded flag. |
| **Kill Switch** | A hold-to-talk key interrupts speech/agent work; explicit quit phrases and Ctrl-C stop the loop; permission requests are denied when the turn is interrupted. `brain.reset_turn()` drains stale stream messages and rebuilds a fresh session if alignment cannot be repaired. | Add an immediate, independently testable stop path and post-cancel stream cleanup to GAIA’s Kill Switch. Preserve GAIA’s stronger shutdown/audit guarantees. |
| **Event Bus** | A tiny observable contract publishes states (`idle`, `listening`, `thinking`, `speaking`), waveform samples, loading PID, direction cues, reply completion, and optional rate limits in `signals_dir`; writes are best-effort and never crash the voice loop; waveform writes are throttled. | Model these as typed GAIA Event Bus events with authorization/audit metadata. Do not copy the filesystem bus as an authority channel; the source writes are not an authenticated or atomic event log. |
| **Capability Router** | Tool-aware renderers map `Write/Edit/Bash/WebFetch` to human-readable intent and provide a separate full-detail rendering; exact console phrases are reserved for control actions. | Adopt capability-specific descriptions and explicit “details” expansion in GAIA’s router. Keep GAIA’s capability registry, schemas, and policy evaluation authoritative. |
| **Core** | The voice layer deliberately has no personality/identity of its own; it points at an existing agent directory/`CLAUDE.md` and adds only spoken-delivery discipline. | Reinforce GAIA’s separation of transport/presentation from Core identity and authority. |
| **RBAC** | No actual RBAC, subject identity, role hierarchy, tenant isolation, or per-role capability grants were found. `extra_dirs` and `visible_skills` are reach/context filters, explicitly not a sandbox or RBAC system. | No RBAC adoption from this project; retain GAIA RBAC as the authority model. |

## Security and reuse decision

Useful patterns are architectural, not code reuse. Direct code reuse is not recommended because the project’s own README and `LICENSE` both state **GNU Affero General Public License version 3 or later (AGPL-3.0-or-later)**, copyright Jared Rhodenizer (2026). The README also says modified network-served versions must provide source and invites contact for closed-source commercial use. No separate commercial exception or contributor-license grant was verified.

**Verified license:** `AGPL-3.0-or-later`, confirmed from the repository `LICENSE` (full GNU AGPL v3 text), README license section, and SPDX headers in inspected Python sources. **Uncertainty:** the `main` branch is mutable and no independent copyright/provenance audit was performed; this is a repository-level verification, not legal advice. The report therefore recommends patterns only, with no backtalk code copied or integrated.

## Sources

- [README.md](https://raw.githubusercontent.com/jaredrhod/backtalk/main/README.md)
- [backtalk.md](https://raw.githubusercontent.com/jaredrhod/backtalk/main/backtalk.md)
- [TROUBLESHOOTING.md](https://raw.githubusercontent.com/jaredrhod/backtalk/main/TROUBLESHOOTING.md)
- [main.py](https://raw.githubusercontent.com/jaredrhod/backtalk/main/backtalk/main.py)
- [brain.py](https://raw.githubusercontent.com/jaredrhod/backtalk/main/backtalk/brain.py)
- [config.py](https://raw.githubusercontent.com/jaredrhod/backtalk/main/backtalk/config.py)
- [ptt.py](https://raw.githubusercontent.com/jaredrhod/backtalk/main/backtalk/ptt.py)
- [signals.py](https://raw.githubusercontent.com/jaredrhod/backtalk/main/backtalk/signals.py)
- [LICENSE](https://raw.githubusercontent.com/jaredrhod/backtalk/main/LICENSE)
