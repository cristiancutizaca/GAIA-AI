"""Isolated registry: a broken optional plugin cannot stop GAIA Core."""
from __future__ import annotations
import inspect
import logging
from dataclasses import asdict, dataclass
from typing import Any
from .contracts import Health
logger=logging.getLogger("lumen.extensions.registry")

@dataclass
class RegisteredPlugin:
    name: str
    plugin: Any
    enabled: bool = True
    error: str = ""

class PluginRegistry:
    def __init__(self) -> None:
        self._items: dict[str, RegisteredPlugin] = {}
    def register(self, plugin: Any, *, enabled: bool = True) -> None:
        name=str(getattr(plugin,"name",plugin.__class__.__name__)).strip()
        if not name or len(name)>80: raise ValueError("invalid plugin name")
        self._items[name]=RegisteredPlugin(name,plugin,bool(enabled))
    def set_enabled(self,name: str,enabled: bool) -> None:
        if name not in self._items: raise KeyError(name)
        self._items[name].enabled=bool(enabled)
    def get(self,name: str) -> Any | None:
        item=self._items.get(name)
        return item.plugin if item and item.enabled and not item.error else None
    async def health(self) -> list[dict[str, Any]]:
        result=[]
        for item in self._items.values():
            if not item.enabled: result.append({"name":item.name,"status":"DISABLED"}); continue
            if item.error: result.append({"name":item.name,"status":"DEGRADED","detail":item.error}); continue
            try:
                value=item.plugin.health() if hasattr(item.plugin,"health") else Health("OK")
                if inspect.isawaitable(value): value=await value
                if isinstance(value,Health): value=asdict(value)
                result.append({"name":item.name,"status":"OK",**(value if isinstance(value,dict) else {"detail":str(value)})})
            except Exception as exc:
                item.error=f"{type(exc).__name__}: {exc}"[:300]
                logger.warning("optional plugin %s unhealthy: %s",item.name,item.error)
                result.append({"name":item.name,"status":"DEGRADED","detail":item.error})
        return result
    def status(self) -> list[dict[str, Any]]:
        return [{"name":i.name,"enabled":i.enabled,"isolated_error":i.error} for i in self._items.values()]
registry=PluginRegistry()
