"""Convenience assembly for optional v1.1 components; safe with every flag disabled."""
from .adapters import BrowserUseAdapter, ComputerUseAdapter, Mem0MemoryProvider, OpenHandsCodingWorker, VoiceV2Adapter
from .event_bus import EventBus
from .feature_flags import feature_flags
from .mcp_gateway import MCPGateway
from .plugin_registry import registry

def build_foundation():
    items=[(BrowserUseAdapter(),feature_flags.browser),(VoiceV2Adapter(),feature_flags.voice_v2),(Mem0MemoryProvider(),feature_flags.mem0),(OpenHandsCodingWorker(),feature_flags.coding_worker),(ComputerUseAdapter(),feature_flags.computer_use)]
    for plugin,enabled in items: registry.register(plugin,enabled=enabled)
    return {"flags":feature_flags.as_dict(),"event_bus":EventBus(),"mcp":MCPGateway(),"plugins":registry}
