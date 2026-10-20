# Harvest 08 — `jaredrhod/ai-visualizer`

- **Repository:** https://github.com/jaredrhod/ai-visualizer
- **Current revision checked:** default branch `main`; tree SHA `6921e1d4b06bdd4a34c5264882d5257c4d5f70fd` (GitHub API, 2026-10-04 metadata).
- **Classification:** `PATTERN_ADOPTED`
- **GAIA posture:** Keep GAIA’s authority model unchanged. Treat this project only as an optional, read-only visualization/telemetry consumer or as a source of design patterns; do not make it an authority, action executor, or permission system.

## What the project concretely is

The README describes four browser “faces” driven by a tiny voice signal bus. `server.py` is a Python-standard-library HTTP server exposing only GET-style `/state` and `/config` plus static files. It reads `.voice_state`, `.voice_waveform`, `.voice_loading_pid`, optional `.voice_alert`, and optional `.voice_rate_limits`; it does not write the bus or execute agent actions. `core.js` polls `/state`, normalizes state/waveform data, and exposes a common `AV` view model to each face. A face is discovered by placing `faces/<id>/index.html` and optional `face.json` in the folder.

The server binds to `127.0.0.1` by default, serves only paths resolved beneath its repository directory, and returns a safe idle/zero-waveform view when bus files are missing or malformed. Waveform data is accepted as speech only when its timestamp is less than 0.6 seconds old. `--mock`, `?demo=1`, and `?shot=...` provide synthetic or deterministic rendering modes; these are test/preview facilities, not authority controls.

## Comparison with the GAIA authority model

| GAIA component | Evidence in ai-visualizer | GAIA decision |
|---|---|---|
| **Core** | Shared `core.js` turns raw signals into `AV.state`, `AV.level`, smoothed `AV.env`, `AV.samples`, `AV.alert`, and config fields for multiple renderers. | **Adopt the pattern:** a shared, versioned telemetry adapter for GAIA UIs. The visualizer remains a leaf, not GAIA Core. |
| **Permission Layer** | Browser microphone permission is requested only for an on-screen meter; denying it leaves the visualizer running. No agent/tool permission checks exist. | **Do not adopt as authorization.** GAIA Permission Layer remains the sole policy gate. |
| **Action Host** | No POST/action routes, subprocess execution, tool invocation, or state mutation; the server is a static/read-only host. | **No integration.** It provides no Action Host capability. |
| **Safe Mode** | Mock/demo/shot modes synthesize visual states and support deterministic capture. | **Adopt only as QA/preview pattern**, explicitly separate from GAIA Safe Mode and not a security boundary. |
| **Kill Switch** | No stop, revoke, quarantine, or emergency-disable endpoint. `--no-open` only suppresses browser launch; `thinking_sound:false` only mutes audio. | **No pattern to adopt.** GAIA Kill Switch stays authoritative. |
| **RBAC** | No users, identities, roles, sessions, or access-control checks. | **No pattern to adopt.** |
| **Event Bus** | Minimal external contract: enumerated state plus timestamped waveform and attention/loading signals; stale/missing data decays to a benign display state. | **Strongest adoption:** define a GAIA event/telemetry schema with explicit enum values, freshness/TTL, malformed-input behavior, and read-only subscribers. Prefer GAIA’s existing bus/transport rather than adding this file bus. |
| **Capability Router** | Folder-based face discovery plus optional metadata and a common `AV.init()`/read-only fields contract. | **Adopt as an optional renderer/plugin manifest pattern only.** It is not a capability router and must not grant tools or actions. |

## Concrete patterns GAIA can adopt

1. **Read-only telemetry contract:** publish only the minimum state required by a renderer (`idle/listening/thinking/speaking`, level, waveform, alert/loading), with no UI write-back path.
2. **Freshness and fail-closed display semantics:** timestamp samples, reject stale samples, decay old visual data, and default missing/invalid input to an inert state; never infer permission or action authority from a visual state.
3. **One shared adapter for many views:** normalize once in a common client layer so multiple GAIA views cannot independently disagree about state, smoothing, or usage formatting.
4. **Declarative renderer registration:** require a manifest plus an entry page and expose a narrow read-only view-model API; keep renderer discovery separate from capability/action registration.
5. **Local-only, path-confined optional host:** if GAIA ships a local visualization host, bind to loopback by default, allow only GET/static reads, and enforce resolved-path containment.
6. **Deterministic preview harness:** retain mock/shot modes for UI tests, screenshots, and integration checks, with an explicit label that simulated state is not live authority.
7. **User-config isolation:** keep user configuration outside update-managed code so upgrades do not overwrite local settings or custom views.

## License and reuse decision

**Verified license:** GitHub repository metadata reports `AGPL-3.0`; `LICENSE` is the full GNU Affero General Public License Version 3, and README/source headers state `AGPL-3.0-or-later` with copyright `(C) 2026 Jared Rhodenizer`. The bundled `assets/VT323-OFL.txt` separately states SIL Open Font License 1.1 for VT323.

No code or media is copied into GAIA. AGPL-3.0-or-later is strong copyleft, including source-sharing obligations for covered modified network software; direct incorporation into a differently licensed or closed GAIA component requires a separate legal review/permission. The repository does not provide a clearly separate license notice for `assets/face.png` or `assets/thinking.wav`; their reuse rights are therefore **uncertain** and they should not be copied. The recommendation is pattern-only, hence `PATTERN_ADOPTED`, not `CODE_REUSED_WITH_LICENSE`.

## Sources checked

- README: https://raw.githubusercontent.com/jaredrhod/ai-visualizer/main/README.md
- Setup guide: https://raw.githubusercontent.com/jaredrhod/ai-visualizer/main/ai-visualizer.md
- Troubleshooting: https://raw.githubusercontent.com/jaredrhod/ai-visualizer/main/TROUBLESHOOTING.md
- Server: https://raw.githubusercontent.com/jaredrhod/ai-visualizer/main/server.py
- Shared client core: https://raw.githubusercontent.com/jaredrhod/ai-visualizer/main/core.js
- License: https://raw.githubusercontent.com/jaredrhod/ai-visualizer/main/LICENSE
- Repository metadata/license: https://api.github.com/repos/jaredrhod/ai-visualizer
- Repository tree/revision: https://api.github.com/repos/jaredrhod/ai-visualizer/git/trees/main?recursive=1
