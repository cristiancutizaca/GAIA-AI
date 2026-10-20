# Harvest 06 — Jared `ai-memory-vault`

- **ID:** `harvest-06-ai-memory-vault`
- **Repository:** [jaredrhod/ai-memory-vault](https://github.com/jaredrhod/ai-memory-vault) (public, default branch `main`)
- **Snapshot checked:** GitHub API reports `updated_at` 2026-10-04, `pushed_at` 2026-08-31; latest listed commit is `659bba9` (2026-08-31). The repo is a markdown/Obsidian system, not a conventional software library: `README.md`, `ai-memory-vault.md` (v3.3 build/instruction file), `TROUBLESHOOTING.md`, and templates `CLAUDE.md`, `VAULT-INDEX.md`, `DAILY-NOTE.md`, `MEMORY.md`.
- **What it does:** Uses an Obsidian vault of plain Markdown as external, on-demand AI memory. A boot file points an agent at the vault; a root index, folder indexes, wikilinks, daily notes, profile, and per-task “Jobs” route the context needed for recurring work. The build file interactively installs/connects Obsidian, creates the structure, and maintains it.

## Concrete patterns GAIA can adopt (without replacing GAIA)

| GAIA authority component | Concrete pattern | Adoption boundary |
|---|---|---|
| **Core** | A small pinned boot manifest carries identity, memory location, startup sequence, and invariants; a separate root index is the human-readable map/profile. Re-read the authoritative index after context compaction. | Add as a GAIA bootstrap/index convention; Core remains the authority. |
| **Permission Layer / RBAC** | Treat source/config edits as read-only by default; state the exact change and require explicit confirmation before code/config/commit/push/deploy. Make access expansion user-driven and default to narrower scope. Make personal profile sections opt-in. | Encode as GAIA policy gates. This project has no real role/permission matrix, so do not copy its prose as enforcement. |
| **Action Host / Safe Mode** | Preflight reachability and writability; never create over existing data; back up before every edit (healthy or malformed); merge rather than replace; use a real serializer instead of shell string assembly; verify the intended path exists and prior entries remain; if verification is unavailable, restore the backup and stop. | Implement in GAIA Action Host transaction wrappers and fail-closed Safe Mode. |
| **Event Bus** | Append-only daily/session records plus checkpoint persistence create a simple, human-readable event trail; “what changed” is written to the relevant note, daily log, and index in one checkpoint. | Use only as an audit/event-log pattern. Do not infer that this repo supplies an actual event bus. |
| **Capability Router** | Per-task “Jobs” contain the task method and links to exactly the notes to prime, loading only the relevant slice rather than the entire vault. | Add a GAIA context/capability-routing convention behind the existing router. |

## Security and non-adoption findings

- The repository’s Markdown is an instruction payload that tells an AI to execute it, install software, edit Obsidian’s registry, and maintain files. It is **not** an enforcement boundary. GAIA must ingest it as untrusted external content and keep authority in its existing Core/Permission Layer.
- There is no implemented cryptographic capability model, RBAC engine, Event Bus, Kill Switch, or isolated Action Host. Do not claim these are supplied by the project. The “kill-switch-like” behavior worth adopting is only fail-closed refusal/rollback when a write cannot be verified; retain GAIA’s actual Kill Switch.
- The current source and commit history document prior real failure modes: shell escaping corrupted Windows paths while producing valid JSON; backups were initially conditional on malformed input; parse-only validation missed a destroyed write; half-finished installs could be mistaken for completed installs; and a memory redirect could be written to the wrong project folder. The revised guidance is useful as a checklist, but it also argues against granting a prompt-driven installer broad autonomous authority.
- Do **not** adopt the shipped personality, automatic installation, broad shell/file-write behavior, or “self-maintaining” prompt authority as GAIA control logic. These are product choices and unsafe as permission enforcement.

## License

**Verified:** `Creative Commons Attribution-ShareAlike 4.0 International` (**CC BY-SA 4.0**, SPDX `CC-BY-SA-4.0`). GitHub repository metadata and `LICENSE` agree; README states copyright `(c) 2026 Jared Rhodenizer`. The license grants worldwide, royalty-free, non-exclusive, irrevocable rights to reproduce/share and make/share adaptations, subject to attribution, copyright/license/disclaimer notices, modification indication, and ShareAlike for adaptations; it disclaims warranties and does not grant patent/trademark rights. Commercial use is expressly stated in the README as allowed.

**Uncertainty:** No separate per-file licensing map or dependency inventory was found. This report recommends **patterns only**, not copying code or text. If GAIA distributes adapted repository material, legal review is required for CC BY-SA attribution/ShareAlike compatibility and for any third-party material; the repository’s license alone does not settle that question.

## Decision

**Classification: `PATTERN_ADOPTED`.** Adopt the bounded patterns above behind GAIA’s existing authority model; do not replace GAIA with this vault or reuse its prompt/build files as control-plane code.
