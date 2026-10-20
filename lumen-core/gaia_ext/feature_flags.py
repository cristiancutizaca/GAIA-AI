"""Central, fail-closed feature flags for v1.1 optional capabilities."""
from __future__ import annotations
import os
from dataclasses import dataclass, fields

def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, "true" if default else "false").strip().lower() in {"1", "true", "yes", "on", "si", "sí"}

@dataclass(frozen=True)
class FeatureFlags:
    mcp: bool = False
    browser: bool = False
    voice_v2: bool = False
    vad: bool = False
    mem0: bool = False
    coding_worker: bool = False
    computer_use: bool = False
    graph_memory: bool = False
    visualizer: bool = False
    realtime_transport: bool = False

    @classmethod
    def from_env(cls) -> "FeatureFlags":
        return cls(**{f.name: _bool("GAIA_FEATURE_" + f.name.upper(), False) for f in fields(cls)})

    def as_dict(self) -> dict[str, bool]:
        return {f.name: bool(getattr(self, f.name)) for f in fields(self)}

    def all_disabled(self) -> bool:
        return not any(self.as_dict().values())

feature_flags = FeatureFlags.from_env()
