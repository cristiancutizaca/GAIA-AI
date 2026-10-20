"""Compatibility bridges for the optional-provider registry.

These objects do not create a second runtime. Their health methods delegate to the real lazy providers in ``gaia_platform.real_backends``; execution remains fail-closed until the PlatformRuntime has applied authority and Action Host policy.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from .contracts import Health

def _health(provider: Any) -> Health:
    try:
        raw = provider.health()
        return Health(str(raw.get("status", "UNKNOWN")), "real provider health", raw)
    except Exception as exc:
        return Health("DEPENDENCY_MISSING", type(exc).__name__, {})

class BrowserUseAdapter:
    name="browser-use"; feature="browser"; dependency="browser-use"
    def health(self):
        from gaia_platform.browser_real import BrowserUseBackend
        return _health(BrowserUseBackend())
    async def observe(self): return {"status":"DELEGATE_TO_PLATFORM_RUNTIME","authority":"GAIA Action Host"}
    async def execute(self,*args:Any,**kwargs:Any): raise PermissionError("Browser effects must enter PlatformRuntime and Action Host")

class VoiceV2Adapter:
    name="pipecat-voice-v2"; feature="voice_v2"; dependency="pipecat"
    def health(self):
        from gaia_platform.real_backends import PipecatVoiceBackend
        return _health(PipecatVoiceBackend())
    async def execute(self,*args:Any,**kwargs:Any): raise PermissionError("Voice transport must enter PlatformRuntime")

class Mem0MemoryProvider:
    name="mem0-memory"; feature="mem0"; dependency="mem0ai"
    def health(self):
        from gaia_platform.real_backends import Mem0MemoryProvider as Real
        return _health(Real())
    async def execute(self,*args:Any,**kwargs:Any): raise PermissionError("Memory writes must enter PlatformRuntime authorization")

class OpenHandsCodingWorker:
    name="openhands-coding-worker"; feature="coding_worker"; dependency="openhands-sdk"
    def health(self):
        from gaia_platform.real_backends import OpenHandsCodingWorker as Real
        return _health(Real(Path.cwd() / "data" / "coding-workspaces"))
    async def execute(self,*args:Any,**kwargs:Any): raise PermissionError("Coding effects require approved isolated workspace and Action Host")

class ComputerUseAdapter:
    name="computer-use"; feature="computer_use"; dependency="UI-TARS/Agent-S"
    def health(self):
        from gaia_platform.real_backends import UITARSComputerUseBackend
        return _health(UITARSComputerUseBackend())
    async def execute(self,*args:Any,**kwargs:Any): raise PermissionError("Computer Use requires PlatformRuntime authority and physical GUI")
