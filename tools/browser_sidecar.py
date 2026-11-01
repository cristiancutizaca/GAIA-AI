#!/usr/bin/env python3
"""Isolated Browser Use worker for GAIA.

JSON-lines protocol over stdin/stdout. All Browser Use imports and their exact
runtime pins stay inside .venv-browser so they cannot mutate GAIA Core deps.
Security/authority decisions remain in the parent GAIA process.
"""
from __future__ import annotations
import asyncio, contextlib, json, logging, os, platform, shutil, sys
from pathlib import Path
from typing import Any

PROTO_OUT = sys.stdout
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)


def _discover_browser_executable() -> str | None:
    override=os.getenv('GAIA_BROWSER_EXECUTABLE','').strip()
    if override:
        p=Path(override).expanduser()
        if not p.is_file(): raise FileNotFoundError(f'GAIA_BROWSER_EXECUTABLE not found: {p}')
        return str(p.resolve())
    for name in ['chromium','chromium-browser','google-chrome','google-chrome-stable','chrome','msedge']:
        found=shutil.which(name)
        if found:return found
    if platform.system()=='Windows':
        roots=[os.getenv('PROGRAMFILES',''),os.getenv('PROGRAMFILES(X86)',''),os.getenv('LOCALAPPDATA','')]
        rels=[Path('Google/Chrome/Application/chrome.exe'),Path('Microsoft/Edge/Application/msedge.exe'),Path('Chromium/Application/chrome.exe')]
        for base in roots:
            if not base: continue
            for rel in rels:
                p=Path(base)/rel
                if p.is_file(): return str(p)
    return None

class Worker:
    def __init__(self): self.session=None; self.page=None
    async def launch(self, p:dict[str,Any]):
        with contextlib.redirect_stdout(sys.stderr):
            from browser_use import BrowserSession
        kwargs={
            'headless':bool(p.get('headless',True)), 'keep_alive':False,
            'is_local':True, 'cloud_browser':False, 'use_cloud':False,
            'allowed_domains':p.get('allowed_domains') or None,
            'enable_default_extensions':False,
        }
        executable=p.get('executable_path') or _discover_browser_executable()
        if executable: kwargs['executable_path']=executable
        if p.get('persistent') and p.get('user_data_dir'): kwargs['user_data_dir']=str(Path(p['user_data_dir']).resolve())
        self.session=BrowserSession(**kwargs)
        with contextlib.redirect_stdout(sys.stderr):
            await asyncio.wait_for(self.session.start(), timeout=float(p.get('launch_timeout',45.0)))
            self.page=await self.session.get_current_page()
            if self.page is None:self.page=await self.session.new_page()
        return {'status':'ready','backend':'browser-use-sidecar','tabs':await self.list_tabs({})}
    def _req(self):
        if not self.session or not self.page: raise RuntimeError('Browser Use session is not launched')
    async def _snapshot(self):
        self._req()
        with contextlib.redirect_stdout(sys.stderr):
            text=await self.page.evaluate("() => document.body ? document.body.innerText : ''")
            html=await self.page.evaluate("() => document.documentElement ? document.documentElement.outerHTML : ''")
            url=await self.page.get_url()
        return {'url':str(url),'text':str(text),'html':str(html)[:200000]}
    async def navigate(self,p): self._req(); await self.page.goto(str(p['url'])); return await self._snapshot()
    async def read_page(self,p): return await self._snapshot()
    async def extract(self,p): d=await self._snapshot(); return {'query':str(p.get('query','')),'text':d['text'][:20000],'url':d['url']}
    async def query(self,p):
        self._req(); sel=str(p['selector']); els=await self.page.get_elements_by_css_selector(sel)
        return {'selector':sel,'count':len(els),'elements':[await e.get_basic_info() for e in els]}
    async def _el(self,selector):
        self._req(); els=await self.page.get_elements_by_css_selector(str(selector))
        if not els: raise LookupError(f'Browser Use selector matched no element: {selector}')
        return els[0]
    async def click(self,p): await (await self._el(p['selector'])).click(**dict(p.get('kwargs') or {})); return {'status':'clicked','selector':p['selector']}
    async def type(self,p):
        kw=dict(p.get('kwargs') or {}); clear=kw.pop('clear',True); await (await self._el(p['selector'])).fill(str(p.get('text','')),clear=clear)
        return {'status':'typed','selector':p['selector']}
    async def select(self,p): await (await self._el(p['selector'])).select_option(p.get('value')); return {'status':'selected','selector':p['selector'],'value':p.get('value')}
    async def scroll(self,p): self._req(); amount=float(p.get('amount',600)); await self.page.evaluate('(y) => window.scrollBy(0, y)',amount); return {'status':'scrolled','amount':amount}
    async def upload(self,p): raise RuntimeError('Browser Use actor upload API not exposed by this pinned worker')
    async def download(self,p): self._req(); return {'status':'use-browser-downloads','files':[str(x) for x in getattr(self.session,'downloaded_files',[]) or []]}
    async def submit(self,p): return await self.click({'selector':p['selector'],'kwargs':{}})
    async def back(self,p): self._req(); await self.page.go_back(); return {'url':await self.page.get_url()}
    async def forward(self,p): self._req(); await self.page.go_forward(); return {'url':await self.page.get_url()}
    async def refresh(self,p): self._req(); await self.page.reload(); return {'url':await self.page.get_url()}
    async def new_tab(self,p):
        self._req(); self.page=await self.session.new_page(str(p.get('url','about:blank'))); return {'url':await self.page.get_url()}
    async def close_tab(self,p):
        self._req(); tabs=await self.session.get_tabs(); idx=p.get('index'); target=tabs[int(idx) if idx is not None else len(tabs)-1]; await self.session.close_page(target.target_id); self.page=await self.session.get_current_page(); return {'tabs':await self.list_tabs({})}
    async def switch_tab(self,p): self._req(); pages=await self.session.get_pages(); self.page=pages[int(p['index'])]; return {'index':int(p['index']),'url':await self.page.get_url()}
    async def list_tabs(self,p):
        if not self.session:return []
        tabs=await self.session.get_tabs(); return [{'index':i,'target_id':str(t.target_id),'url':str(t.url),'title':str(t.title)} for i,t in enumerate(tabs)]
    async def screenshot(self,p): self._req(); target=str(p.get('path') or (Path.cwd()/'gaia-browser-screenshot.png')); data=await self.session.take_screenshot(path=target); return {'status':'saved','path':target,'bytes':len(data)}
    async def wait(self,p): seconds=min(float(p.get('seconds',1)),30); await asyncio.sleep(seconds); return {'status':'waited','seconds':seconds}
    async def stop(self,p):
        if self.session:
            try: await self.session.stop()
            finally:self.session=None;self.page=None
        return {'status':'stopped','backend':'browser-use-sidecar'}
    async def health(self,p):
        with contextlib.redirect_stdout(sys.stderr):
            import browser_use, playwright
        return {'status':'AVAILABLE','backend':'browser-use-sidecar','version':getattr(browser_use,'__version__','unknown'),'playwright':bool(playwright)}

async def main():
    w=Worker(); loop=asyncio.get_running_loop()
    while True:
        line=await loop.run_in_executor(None,sys.stdin.readline)
        if not line: break
        try:
            req=json.loads(line); rid=req.get('id'); method=str(req.get('method','')); params=req.get('params') or {}
            fn=getattr(w,method,None)
            if fn is None: raise ValueError(f'unknown method: {method}')
            with contextlib.redirect_stdout(sys.stderr): result=await fn(params)
            out={'id':rid,'ok':True,'result':result}
        except Exception as exc:
            out={'id':req.get('id') if 'req' in locals() and isinstance(req,dict) else None,'ok':False,'error':f'{type(exc).__name__}: {exc}'}
        PROTO_OUT.write(json.dumps(out,ensure_ascii=False)+'\n'); PROTO_OUT.flush()
        if isinstance(req,dict) and req.get('method')=='stop': break

if __name__=='__main__': asyncio.run(main())
