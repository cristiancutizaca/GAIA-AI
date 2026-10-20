from __future__ import annotations
import asyncio, os, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TMP=tempfile.mkdtemp(prefix='gaia-v14-authority-')
os.environ['LUMEN_DATA_DIR']=TMP
os.environ['LUMEN_SECRET']='v14-authority-secret-0001'
os.environ['GAIA_SAFE_MODE']='false'
sys.path.insert(0,str(ROOT/'lumen-core'))
import memory
from authority import authorize, READ_ONLY, LOW_RISK, EXTERNAL_SIDE_EFFECT
from platform_runtime import PlatformRuntime
from gaia_platform.mcp_real import MCPManager, MCPServerConfig
class Master:
    is_master=True
    device_id='pc'
    def allows(self, _): return True
class Denied:
    is_master=False
    device_id='device-a'
    def allows(self, _): return False
memory.init_db()
master=Master(); denied=Denied()
assert authorize(master,capability='browser.read',permission='chat',risk=READ_ONLY).allowed
memory.set_state('gaia_actions_enabled','0')
assert authorize(master,capability='mcp.tool',permission='actions_request',risk=EXTERNAL_SIDE_EFFECT).status=='KILL_SWITCH_BLOCKED'
assert authorize(master,capability='browser.submit',permission='chat',risk=EXTERNAL_SIDE_EFFECT).status=='KILL_SWITCH_BLOCKED'
assert authorize(master,capability='memory.write',permission='memory_write',risk=LOW_RISK).status=='KILL_SWITCH_BLOCKED'
assert authorize(master,capability='browser.read',permission='chat',risk=READ_ONLY).allowed
assert authorize(denied,capability='mcp.tool',permission='actions_request',risk=READ_ONLY).status=='DENIED'
async def direct_mcp_guard():
    manager=MCPManager(); manager.register(MCPServerConfig(name='untrusted',command=(sys.executable,'-c','')))
    try:
        await manager.call('untrusted','write',{})
        raise AssertionError('MCP side effect bypassed GAIA authority')
    except PermissionError as exc:
        assert 'authority' in str(exc)
asyncio.run(direct_mcp_guard())
code="from authority import authorize, EXTERNAL_SIDE_EFFECT; from types import SimpleNamespace; print(authorize(SimpleNamespace(allows=lambda _: True), capability='mcp.tool', permission='actions_request', risk=EXTERNAL_SIDE_EFFECT).status)"
env=os.environ.copy(); env['GAIA_SAFE_MODE']='true'; env['PYTHONPATH']=str(ROOT/'lumen-core'); assert subprocess.check_output([sys.executable,'-c',code],env=env,text=True).strip()=='SAFE_MODE_BLOCKED'
async def runtime_checks():
    rt=PlatformRuntime(Path(TMP)); await rt.start()
    result=await rt.handle_chat('recuerda que no debe escribirse',principal=master,session_id='s',device_id='pc')
    assert result['status']=='KILL_SWITCH_BLOCKED'
    await rt.stop()
asyncio.run(runtime_checks())
print('V14 GLOBAL AUTHORITY TEST PASS')
