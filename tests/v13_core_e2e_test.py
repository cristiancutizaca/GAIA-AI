from __future__ import annotations
import os, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TMP = tempfile.mkdtemp(prefix='gaia-v13-e2e-')
os.environ['LUMEN_DATA_DIR'] = TMP
os.environ['LUMEN_SECRET'] = 'v13-e2e-secret-0001'
os.environ['LUMEN_SAFE_MODE'] = '0'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lumen-core'))
from fastapi.testclient import TestClient
from config import API_SECRET
from main import app

class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body=b'<html><head><title>GAIA E2E Page</title></head><body><h1>Local integration</h1></body></html>'
        self.send_response(200); self.send_header('Content-Type','text/html'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self,*args): pass

server=ThreadingHTTPServer(('127.0.0.1',0),Page); threading.Thread(target=server.serve_forever,daemon=True).start()
headers={'Authorization':f'Bearer {API_SECRET}'}
with TestClient(app) as client:
    r=client.get('/api/platform/status',headers=headers)
    assert r.status_code==200, r.text; assert r.json()['started'] is True; assert 'browser.read' in r.json()['capabilities']
    r=client.get('/api/platform/plan',headers=headers,params={'message':'lee https://example.com'})
    assert r.status_code==200, r.text; assert r.json()['steps'][0]['capability']['capability']=='browser.read'
    r=client.get('/api/skills',headers=headers)
    assert r.status_code==200, r.text; assert any(x['id']=='research' and x['enabled'] for x in r.json())
    r=client.post('/api/diagnostics/export',headers=headers)
    assert r.status_code==200, r.text; assert r.json()['secret_values_emitted'] is False
    r=client.post('/api/chat',headers=headers,json={'message':'Recuerda que mi proyecto de prueba usa PostgreSQL.','session_id':'e2e-memory','device':'pc'})
    assert r.status_code==200, r.text; assert 'Guardé' in r.json()['response']
    r=client.post('/api/chat',headers=headers,json={'message':'¿Qué base de datos usa mi proyecto de prueba?','session_id':'e2e-memory-2','device':'pc'})
    assert r.status_code==200, r.text; assert 'PostgreSQL' in r.json()['response']
    runtime=app.state.platform_runtime
    runtime.browser.profile.allowed_domains={'127.0.0.1'}
    runtime.browser.profile.allow_private=True
    r=client.post('/api/chat',headers=headers,json={'message':f'lee http://127.0.0.1:{server.server_port}/','session_id':'e2e-browser','device':'pc'})
    assert r.status_code==200, r.text; assert 'GAIA E2E Page' in r.json()['response']
    runtime.register_mcp({'name':'local','command':[sys.executable,str(ROOT/'examples'/'mcp_test_server.py')],'enabled':True,'allow_tools':['read']})
    runtime.capabilities._items['mcp.tool']=runtime.capabilities._items['mcp.tool'].__class__('mcp.tool','MCPManager','READ_ONLY',True,'actions_request')
    r=client.post('/api/chat',headers=headers,json={'message':'mcp:local/read','session_id':'e2e-mcp','device':'pc'})
    assert r.status_code==200, r.text; assert 'MCP local/read' in r.json()['response']
    r=client.post('/api/chat',headers=headers,json={'message':'Usa la herramienta local para leer el estado.','session_id':'e2e-mcp-natural','device':'pc'})
    assert r.status_code==200, r.text; assert 'MCP local/read' in r.json()['response']; assert r.json()['active_context']['metadata']['capability']=='mcp.tool'
    runtime.browser.profile.allow_private=False
    try:
        import asyncio
        asyncio.run(runtime.browser.navigate('http://127.0.0.1/'))
        raise AssertionError('SSRF guard did not block loopback')
    except PermissionError: pass
server.shutdown()
print('V13 CORE E2E PASS')
