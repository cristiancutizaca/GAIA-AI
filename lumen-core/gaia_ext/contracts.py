"""Stable contracts for optional GAIA extensions. No contract grants authority."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol

@dataclass(frozen=True)
class Health:
    status: str
    detail: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

class Plugin(Protocol):
    name: str
    version: str
    def health(self) -> Health: ...

class ModelProvider(Protocol):
    name: str
    async def complete(self, messages: list[dict[str, str]], **options: Any) -> str: ...

class MemoryProvider(Protocol):
    name: str
    async def search(self, query: str, *, owner: str, namespace: str, limit: int = 8) -> list[dict[str, Any]]: ...

class VoiceProvider(Protocol):
    name: str
    async def transcribe(self, audio: bytes, **options: Any) -> str: ...
    async def synthesize(self, text: str, **options: Any) -> bytes: ...

class BrowserProvider(Protocol):
    name: str
    async def observe(self) -> dict[str, Any]: ...
    async def execute(self, action: str, arguments: dict[str, Any], *, permission_token: str | None = None) -> dict[str, Any]: ...

class ComputerUseProvider(BrowserProvider, Protocol):
    async def verify(self, expected: dict[str, Any]) -> dict[str, Any]: ...

class AgentWorker(Protocol):
    name: str
    async def run(self, job: dict[str, Any]) -> dict[str, Any]: ...

class RealtimeTransport(Protocol):
    name: str
    async def publish(self, event: dict[str, Any]) -> bool: ...
    async def close(self) -> None: ...

class VisualizerConsumer(Protocol):
    name: str
    async def consume(self, event: dict[str, Any]) -> None: ...
