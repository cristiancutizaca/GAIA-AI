from __future__ import annotations
import asyncio, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lumen-core')); sys.path.insert(0,str(ROOT/'lumen-pc')); sys.path.insert(0,str(ROOT/'tools'))

def test_browser_use_contract_uses_actor_page_api():
    from gaia_platform.browser_real import BrowserUseBackend
    b=BrowserUseBackend()
    assert b.health()["backend"] == "browser-use"
    assert hasattr(b, "_element") and hasattr(b, "query")

def test_http_fallback_is_fail_closed_for_effects():
    from gaia_platform.browser_real import HttpBrowserBackend
    async def run():
        b=HttpBrowserBackend()
        try: await b.click("#x")
        except PermissionError: return
        assert False
    asyncio.run(run())

def test_mem0_scope_uses_filters_and_top_k():
    from gaia_platform.real_backends import Mem0MemoryProvider
    p=Mem0MemoryProvider()
    class Fake:
        def search(self,*args,**kwargs): self.kw=kwargs; return []
    f=Fake(); p.memory=f
    p.search("hello", owner="alice", namespace="device:pc", limit=3)
    assert f.kw["top_k"]==3 and f.kw["filters"]["gaia_owner"]=="alice" and f.kw["filters"]["gaia_namespace"]=="device:pc"

def test_graphiti_group_scope_is_stable_and_distinct():
    from gaia_platform.real_backends import GraphitiMemoryProvider
    a=GraphitiMemoryProvider.group_id("alice","p","n"); b=GraphitiMemoryProvider.group_id("bob","p","n")
    assert a != b and a.startswith("gaia-")

def test_pipecat_provider_is_lazy_and_has_interrupt():
    from gaia_platform.real_backends import PipecatVoiceBackend
    p=PipecatVoiceBackend(); assert p.health()["backend"]=="pipecat"
    result=asyncio.run(p.interrupt("test")); assert result["status"]=="INTERRUPTED"

def test_wakeword_health_is_local_and_does_not_claim_cloud():
    from wake_word import WakeWordListener
    h=WakeWordListener().health(); assert h["local"] is True and "cloud" not in str(h).lower()

def test_desktop_shell_is_client_only():
    from desktop_shell import DesktopShell
    h=DesktopShell().health(); assert h["authority"]=="GAIA Core"

def test_startup_command_is_user_scoped():
    import gaia_startup
    assert "lumen-pc" in gaia_startup.command() and "sudo" not in gaia_startup.command().lower()
