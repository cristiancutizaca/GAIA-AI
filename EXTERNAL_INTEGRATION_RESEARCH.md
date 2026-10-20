# External integration research — v1.1

Investigación realizada el 2026-10-04 sobre los repositorios indicados. La regla de decisión fue: **GAIA Core sigue siendo autoridad; externos solo adapter/provider/worker/reference**.

| Área | Estado/API observado | Licencia observada | Decisión v1.1 |
|---|---|---|---|
| PersonalJarvis | Runtime local headless, REST/OpenAPI y MCP; API activa pero sin LTS estable | Apache-2.0 actual; releases antiguas MIT | Referencia + futuro adapter HTTP/MCP aislado |
| OpenManus | CLI/agent async, Browser Use/MCP y herramientas shell/Python; main cambiante | MIT | No embebido; worker externo fijado a commit, si se implementa |
| Microsoft Agent Framework | APIs Python/.NET, middleware, tools, workflows y streaming; cambios breaking/previews | MIT | Provider/worker opcional, nunca orquestador GAIA |
| smolagents | CodeAgent/ToolCallingAgent y múltiples extras/modelos; API experimental | Apache-2.0 | Solo worker sandboxed; ToolCalling antes que CodeAgent |
| mcp-use | MCP Python alpha 1.7.1 y TypeScript 2.7.3; APIs distintas y dependencias amplias | MIT | Gateway propio primero; extra separado si se necesita |
| Browser Use | Python 0.13.10, Agent/BrowserSession, perfiles, dominios, Cloud REST | MIT | Adapter/stub; perfil efímero, allowlist y aprobación |
| Pipecat + Silero VAD | VAD ONNX streaming con frames 8/16 kHz; Pipecat pipeline | BSD-2-Clause + MIT | Extra opcional; Voice Legacy sigue default |
| Mem0 + Graphiti | Mem0 2.0.18 y Graphiti 0.30.2; memoria/episodios temporales con servicios externos | Apache-2.0 | Stub/provider; SQLite y ownership GAIA siguen canónicos |
| OpenHands SDK | Agent/Conversation/Workspace, Agent Server HTTP/WebSocket y workspaces remotos | MIT | Worker aislado, workspace temporal y revisión antes de apply |
| UI-TARS + Agent-S | Computer Use por pantalla; Agent-S puede ejecutar Python/Bash en entorno local | Apache-2.0 | Contract/stub; disabled; nunca control directo |
| LiveKit Agents | AgentServer/AgentSession, STT/LLM/TTS, MCP/RPC | Apache-2.0; modelos pueden tener licencia separada | Worker realtime futuro, no bus central |
| Jared visualizers | Fullstack-agent AGPL; visualizador/sistema compuesto, no API estable | AGPL-3.0-or-later y sublicencias por revisar | Solo referencia o sink separado; no copiar |

## Patrones reutilizados

- Contratos pequeños y estables, DTOs propios y lazy loading.
- Workers separados con timeout, cancelación, límites de CPU/memoria/red y filesystem temporal.
- Allowlist de herramientas/dominios/servidores, scopes mínimos, auditoría y redacción.
- `dry-run`/preview, confirmación explícita para side effects y rollback.
- Eventos normalizados para observabilidad, sin secretos ni autoridad.
- Versiones fijadas, SBOM/escaneo y pruebas de contrato antes de activar extras.

## Riesgos comunes

Prompt injection y contenido web no confiable; ejecución de shell/Python; acceso a cookies, pantalla, audio o archivos; envío de datos a LLM/cloud; telemetría; dependencias nativas y supply chain; APIs sin LTS; licencias de modelos/dependencias; coste y loops sin límites.

## Fuentes principales

- https://github.com/PersonalJarvis/PersonalJarvis
- https://github.com/FoundationAgents/OpenManus
- https://github.com/microsoft/agent-framework
- https://github.com/huggingface/smolagents
- https://github.com/mcp-use/mcp-use
- https://github.com/browser-use/browser-use
- https://github.com/pipecat-ai/pipecat
- https://github.com/snakers4/silero-vad
- https://github.com/mem0ai/mem0
- https://github.com/getzep/graphiti
- https://github.com/OpenHands/software-agent-sdk
- https://github.com/bytedance/UI-TARS-desktop
- https://github.com/simular-ai/Agent-S
- https://github.com/livekit/agents
- https://github.com/jaredrhod/fullstack-agent

No se copió código fuente externo en esta release.
