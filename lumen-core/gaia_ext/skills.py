"""GAIA-owned skill registry; skills request permissions but cannot elevate them."""
from __future__ import annotations
from dataclasses import dataclass,field
from typing import Any
@dataclass(frozen=True)
class Skill: name:str; description:str; version:str="1"; instructions:str=""; context_requirements:tuple[str,...]=(); tools:tuple[str,...]=(); permissions:tuple[str,...]=(); quality_checks:tuple[str,...]=(); dependencies:tuple[str,...]=()
class SkillRegistry:
    def __init__(self): self._items:dict[str,Skill]={}
    def register(self,skill:Skill):
        if not skill.name or skill.name in self._items: raise ValueError("skill name unavailable")
        self._items[skill.name]=skill
    def get(self,name): return self._items.get(name)
    def list(self): return [{"name":s.name,"version":s.version,"permissions":list(s.permissions),"tools":list(s.tools)} for s in self._items.values()]
skill_registry=SkillRegistry()
