# GAIA plugin system

`PluginRegistry` registers, enables/disables and health-checks plugins. Exceptions are isolated as `DEGRADED`; a plugin cannot stop Core. Plugins report health but do not receive GAIA permissions automatically.

Contracts: `ModelProvider`, `MemoryProvider`, `VoiceProvider`, `BrowserProvider`, `ComputerUseProvider`, `AgentWorker`, `RealtimeTransport`, `VisualizerConsumer`.
