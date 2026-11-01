#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from importlib.metadata import version

def emit(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, default=str)); raise SystemExit(code)

def scope(p):
    return {"gaia_owner":p.get("owner", ""), "gaia_namespace":p.get("namespace", ""), "gaia_project":p.get("project", "")}

def main():
    try:
        payload=json.loads(sys.stdin.read() or '{}')
        action=payload.get('action','health')
        if action=='health':
            import mem0
            emit({'status':'AVAILABLE','backend':'mem0ai-sidecar','version':version('mem0ai')})
        from mem0 import Memory
        cfg=payload.get('config') or (json.loads(os.environ['MEM0_CONFIG_JSON']) if os.environ.get('MEM0_CONFIG_JSON') else {})
        if not cfg: emit({'status':'CONFIG_REQUIRED','reason':'MEM0_CONFIG_JSON or explicit local config required'},3)
        memory=Memory.from_config(cfg)
        sc=scope(payload)
        if action=='add': out=memory.add(payload['content'], user_id=payload['owner'], run_id=payload.get('session',''), metadata=sc)
        elif action=='search': out=memory.search(payload['query'], top_k=int(payload.get('limit',8)), filters=sc)
        elif action=='get': out=memory.get(payload['memory_id'])
        elif action=='update': out=memory.update(payload['memory_id'], text=payload['text'], metadata=sc)
        elif action=='delete': out=memory.delete(payload['memory_id'])
        elif action=='get_all': out=memory.get_all(filters=sc, top_k=int(payload.get('limit',1000)))
        else: emit({'status':'ERROR','error':f'unknown action: {action}'},2)
        emit({'status':'SUCCEEDED','result':out})
    except SystemExit: raise
    except Exception as exc: emit({'status':'ERROR','error':type(exc).__name__,'detail':str(exc)},1)
if __name__=='__main__': main()
