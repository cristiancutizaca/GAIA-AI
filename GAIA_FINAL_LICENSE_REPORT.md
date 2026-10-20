# GAIA Final License Report

GAIA v1.5 does not copy third-party source into the release. External research is pattern-only unless a license and compatible source reuse are explicitly verified. The release retains the existing project license files and excludes downloaded dependencies, models, credentials and caches.

The external harvest report records each project, verified license, reuse classification and whether code was copied. Current v1.5 implementation has no unverified third-party code copied from PersonalJarvis, OpenManus, Microsoft Agent Framework, smolagents or Jared's projects.

## Verified harvest summary

The ten upstream reviews are archived under `reports/external-harvest/`. All are classified `PATTERN_ADOPTED`; no external source code was copied. Verified current licenses include PersonalJarvis Apache-2.0/NOTICE, OpenManus MIT, Microsoft Agent Framework MIT, smolagents Apache-2.0, fullstack-agent AGPL-3.0-or-later, ai-memory-vault CC BY-SA 4.0, backtalk AGPL-3.0-or-later, ai-visualizer AGPL-3.0-or-later with OFL font note, barehands AGPL-3.0-or-later, Browser Use MIT and Pipecat BSD-2-Clause. Dependency and bundled-asset licenses remain subject to separate review before any future code reuse.


## Real backend dependencies attempted in this run

| Dependency | Version attempted | Repository | License / integration | Copied files | Runtime terms / blocker |
|---|---:|---|---|---|---|
| browser-use | 0.13.10 | github.com/browser-use/browser-use | MIT, lazy real BrowserSession integration | none | Chromium/Playwright and model credentials may be required |
| pipecat-ai | 1.12.0 | github.com/pipecat-ai/pipecat | BSD-2-Clause, lazy real Pipeline integration | none | transport/provider credentials and audio hardware |
| silero-vad | 6.2.3 | github.com/snakers4/silero-vad | MIT, real local model wrapper | none | torch/model/audio fixture required |
| mem0ai | 2.2.1 | github.com/mem0ai/mem0 | Apache-2.0, provider adapter | none | dependency graph conflicts with Browser Use in one global environment; isolated env/config required |
| graphiti-core | 0.30.2 | github.com/getzep/graphiti | Apache-2.0, provider adapter | none | Neo4j and embedding/LLM service required |
| openhands-sdk | 1.52.0 | github.com/OpenHands/software-agent-sdk | MIT, isolated worker adapter | none | compatible SDK/model runtime required |
| ui-tars | 0.5.1 | github.com/bytedance/UI-TARS | optional provider boundary | none | physical GUI/model runtime unavailable in Sandbox |

No third-party source or incompatible AGPL/CC-BY-SA assets were copied into GAIA.
