# Third-party licenses

| Project | Repository | License/version | Usage in this release | Copied/modified files |
|---|---|---|---|---|
| PersonalJarvis | github.com/PersonalJarvis/PersonalJarvis | To verify upstream | architectural reference | none |
| OpenManus | github.com/FoundationAgents/OpenManus | To verify upstream | architectural reference | none |
| Microsoft Agent Framework | github.com/microsoft/agent-framework | To verify upstream | architectural reference | none |
| smolagents | github.com/huggingface/smolagents | To verify upstream | architectural reference | none |
| mcp-use | github.com/mcp-use/mcp-use | To verify upstream | optional future dependency | none |
| Browser Use | github.com/browser-use/browser-use | To verify upstream | optional future dependency | none |
| Pipecat / Silero VAD | upstream repositories | To verify upstream | optional future dependency | none |
| Mem0 / Graphiti | upstream repositories | To verify upstream | optional future dependency | none |
| OpenHands SDK | github.com/OpenHands/software-agent-sdk | To verify upstream | optional future dependency | none |
| UI-TARS / Agent-S / LiveKit | upstream repositories | To verify upstream | future adapters | none |
| Jared visualizers | github.com/jaredrhod/* | AGPL-sensitive; verify | reference only | none |

Before distribution, record exact installed version and license for every enabled optional dependency.

## Research-confirmed notes

- PersonalJarvis current main was observed as Apache-2.0; historical releases up to 1.6.0 were reported as MIT. Pin the release and preserve the matching NOTICE.
- OpenManus, Microsoft Agent Framework and LiveKit Agents were observed as MIT, MIT and Apache-2.0 respectively.
- smolagents was observed as Apache-2.0; Browser Use as MIT; Pipecat as BSD-2-Clause; Silero VAD as MIT.
- Mem0, Graphiti and OpenHands Software Agent SDK were observed as Apache-2.0, Apache-2.0 and MIT respectively.
- UI-TARS Desktop and Agent-S were observed as Apache-2.0. Jared fullstack-agent is AGPL-3.0-or-later and is not copied into this release.

These observations apply to the reviewed repository snapshots, not to every transitive dependency, model or service. Re-run legal/SBOM review before enabling an optional extra.
