"""GAIA v1.1 optional extension foundation; RC6 remains the authority."""
from .contracts import (
    AgentWorker, BrowserProvider, ComputerUseProvider, MemoryProvider, ModelProvider,
    Plugin, RealtimeTransport, VisualizerConsumer, VoiceProvider,
)
from .feature_flags import FeatureFlags, feature_flags
from .plugin_registry import PluginRegistry, registry

__all__ = ["AgentWorker", "BrowserProvider", "ComputerUseProvider", "FeatureFlags", "MemoryProvider", "ModelProvider", "Plugin", "PluginRegistry", "RealtimeTransport", "VisualizerConsumer", "VoiceProvider", "feature_flags", "registry"]
