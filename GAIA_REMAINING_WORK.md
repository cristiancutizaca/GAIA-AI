# GAIA Remaining Work

| Exact missing capability | Reason / blocker | Files or modules | Dependency | Recommended next action | Priority |
|---|---|---|---|---|---|
| Real browser automation backend | No browser automation service/tool is available in this Sandbox | `gaia_platform/browser_real.py`, capability router | browser package + target browser + physical session | Install and validate Browser Use/Playwright behind existing authority | P4 |
| Realtime voice with VAD and barge-in E2E | Audio device and optional packages/models unavailable | `voice.py`, `gaia_platform/voice.py` | Whisper/Edge TTS or Pipecat/Silero, FFmpeg, microphone | Run audio wizard on target PC | P5 |
| Mem0/Graphiti external backend | No service credentials or dependency is bundled | `memory_v2.py`, `graph_memory.py` | provider install/credentials | Implement adapters only after provider contract and privacy review | P6/P13 |
| OpenHands coding worker | SDK and isolated execution policy not installed | `workers2.py`, coding capability | OpenHands SDK, sandbox runner, approval UI | Integrate as optional worker with GAIA authority adapter | P8 |
| Physical Computer Use / Android | Hardware and real user session required | mobile scaffold, computer capability | target devices and operator | Run physical validation ledger | P15/P17 |
| Distributed workers and automations | Current implementation is local SQLite/asyncio | `workers2.py`, `automation_persistent.py` | durable queue/worker deployment | Add only if target deployment needs it | P9/P10 |
| Target performance baselines | Sandbox is not target hardware | performance report and existing profilers | target PC/GPU/network | Run benchmarks after physical install | P20 |

Everything else in the v1.5 scope is either integrated locally, inherited and tested, or explicitly marked optional/experimental; no scaffold is presented as production-complete.
