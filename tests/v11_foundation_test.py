from __future__ import annotations
import asyncio, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lumen-core'))
from gaia_ext.feature_flags import FeatureFlags
from gaia_ext.plugin_registry import PluginRegistry
from gaia_ext.event_bus import EventBus, GaiaEvent
from gaia_ext.contracts import Health
from gaia_ext.mcp_gateway import MCPGateway, MCPToolAdapter

assert FeatureFlags().all_disabled()
class Broken:
    name='broken'
    def health(self): raise RuntimeError('expected isolated failure')
async def main():
    r=PluginRegistry(); r.register(Broken()); h=await r.health(); assert h[0]['status']=='DEGRADED'
    bus=EventBus(); seen=[]; bus.subscribe('test',lambda e: seen.append(e))
    await bus.start(); assert bus.publish(GaiaEvent.create('WAITING_PERMISSION',source='test',session_id='s',metadata={'token':'hidden','ok':1})); await asyncio.sleep(.02); await bus.stop()
    assert seen and seen[0].metadata['token']=='[REDACTED]'
    called=[]
    g=MCPGateway(allowlist={'default:read'},permission_check=lambda **_:True)
    g.register(MCPToolAdapter('read','safe','READ_ONLY',lambda args: called.append(args) or {'value':1})); g.connect()
    out=await g.call('default:read',{'x':1}); assert out['ok'] and called
    g.register(MCPToolAdapter('write','side effect','EXTERNAL_SIDE_EFFECT',lambda _: {'ok':1}))
    try: await g.call('default:write',{},confirmed=True)
    except PermissionError: pass
    else: raise AssertionError('allowlist bypass')
asyncio.run(main())
print('V11 FOUNDATION TEST OK')
