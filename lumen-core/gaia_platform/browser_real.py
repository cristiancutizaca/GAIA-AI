from __future__ import annotations
import asyncio, base64, ipaddress, os, platform, re, shutil, urllib.parse, urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from .security import guard_web_content

@dataclass
class BrowserProfile:
    name: str = "temporary"
    allowed_domains: set[str] = field(default_factory=set)
    persistent: bool = False
    allow_private: bool = False
    isolated: bool = True
    user_data_dir: str | None = None
    launch_timeout: float = 45.0

class BrowserSecurityError(PermissionError): pass

class _BrowserSecurity:
    def __init__(self, profile: BrowserProfile): self.profile = profile
    def check_url(self, url: str) -> None:
        p=urllib.parse.urlparse(url)
        if p.scheme not in {"http","https"} or not p.hostname: raise BrowserSecurityError("only allowlisted http/https URL required")
        host=p.hostname.lower().rstrip(".")
        allowed={x.lower().rstrip(".") for x in self.profile.allowed_domains}
        if allowed and not any(host==d or host.endswith("."+d) for d in allowed): raise BrowserSecurityError("domain not allowlisted")
        try: addr=ipaddress.ip_address(host); private=addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
        except ValueError: private=host in {"localhost","metadata.google.internal","instance-data"}
        if private and not self.profile.allow_private: raise BrowserSecurityError("private/loopback address blocked by SSRF policy")
    def content(self,text:str)->dict[str,Any]:
        guarded=guard_web_content(text); raw=str(guarded.get("content","") if isinstance(guarded,dict) else guarded)
        suspicious=bool(re.search(r"(?i)(ignore (all|previous)|system prompt|api key|password|private file|run shell|disable security)",raw))
        return {"content":raw,"trusted":False,"trust":"EXTERNAL_UNTRUSTED","prompt_injection_detected":suspicious}

class HttpBrowserBackend:
    """Lightweight read-only HTTP fallback; it is never labelled Browser Use."""
    def __init__(self,profile:BrowserProfile|None=None):
        self.profile=profile or BrowserProfile(); self.security=_BrowserSecurity(self.profile); self.current=""; self.history=[]; self.content=""; self.tabs=["about:blank"]; self.active=0
    def _check(self,url): self.security.check_url(url)
    async def launch(self): return {"status":"ready","backend":"http-read-only","profile":self.profile.name,"tabs":self.tabs}
    async def navigate(self,url):
        self.security.check_url(url)
        def fetch():
            req=urllib.request.Request(url,headers={"User-Agent":"GAIA/1.7 read-only browser"})
            with urllib.request.urlopen(req,timeout=15) as r:return r.geturl(),r.read(2_000_000).decode("utf-8","replace")
        final,text=await asyncio.to_thread(fetch); self.history.append(self.current); self.current=final; self.content=text; self.tabs[self.active]=final
        return {"url":final,"content":self.security.content(text),"backend":"http-read-only"}
    async def read_page(self): return self.security.content(self.content)
    async def extract(self,query): return {"query":query,"text":self.content[:20000],"trusted":False}
    async def search_page(self,query): return {"query":query,"matches":[x[:500] for x in self.content.splitlines() if query.lower() in x.lower()][:50]}
    async def back(self): return await self.navigate(self.history.pop()) if self.history else {"url":self.current}
    async def forward(self): return {"url":self.current,"status":"no-forward-history"}
    async def refresh(self): return await self.navigate(self.current)
    async def new_tab(self,url="about:blank"): self.tabs.append(url); self.active=len(self.tabs)-1; return await self.navigate(url) if url!="about:blank" else {"url":url}
    async def close_tab(self,index=None):
        if len(self.tabs)==1:return {"status":"closed"}
        del self.tabs[self.active if index is None else index]; self.active=min(self.active,len(self.tabs)-1); return {"tabs":self.tabs}
    async def switch_tab(self,index): self.active=int(index); return {"index":self.active,"url":self.tabs[self.active]}
    async def list_tabs(self): return [{"index":i,"url":u,"active":i==self.active} for i,u in enumerate(self.tabs)]
    async def click(self,*a,**k): raise PermissionError("interactive browser action requires GAIA Action Host")
    async def type(self,*a,**k): raise PermissionError("input requires GAIA Action Host")
    async def select(self,*a,**k): raise PermissionError("input requires GAIA Action Host")
    async def scroll(self,*a,**k): raise PermissionError("interactive browser action requires GAIA Action Host")
    async def upload(self,*a,**k): raise PermissionError("upload requires explicit permission")
    async def download(self,*a,**k): raise PermissionError("download requires explicit permission")
    async def submit(self,*a,**k): raise PermissionError("submit requires explicit permission")
    async def screenshot(self): return {"status":"not_available","detail":"HTTP backend has no rendered screenshot"}
    async def wait(self,seconds=1): await asyncio.sleep(min(float(seconds),30)); return {"status":"waited","seconds":float(seconds)}
    async def cancel(self): return await self.close()
    async def stop(self): return await self.close()
    async def close(self): self.content=""; self.tabs=[]; return {"status":"closed"}

def _discover_browser_executable() -> str | None:
    """Return an explicit local browser only when one is clearly available.

    Browser Use is allowed to manage its own browser when this returns None. The
    environment override always wins.
    """
    override=os.getenv("GAIA_BROWSER_EXECUTABLE","").strip()
    if override:
        path=Path(override).expanduser()
        if not path.is_file(): raise FileNotFoundError(f"GAIA_BROWSER_EXECUTABLE not found: {path}")
        return str(path.resolve())
    names=["chromium","chromium-browser","google-chrome","google-chrome-stable","chrome","msedge"]
    for name in names:
        found=shutil.which(name)
        if found:return found
    if platform.system()=="Windows":
        roots=[os.getenv("PROGRAMFILES", ""),os.getenv("PROGRAMFILES(X86)", ""),os.getenv("LOCALAPPDATA", "")]
        rels=[Path("Google/Chrome/Application/chrome.exe"),Path("Microsoft/Edge/Application/msedge.exe"),Path("Chromium/Application/chrome.exe")]
        for root in roots:
            if not root:continue
            for rel in rels:
                candidate=Path(root)/rel
                if candidate.is_file():return str(candidate)
    return None

class _BrowserSidecarClient:
    def __init__(self): self.proc=None; self._seq=0; self._lock=asyncio.Lock()
    @staticmethod
    def paths():
        root=Path(__file__).resolve().parents[2]
        py=root/'.venv-browser'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        worker=root/'tools'/'browser_sidecar.py'
        return root,py,worker
    async def start(self):
        if self.proc and self.proc.returncode is None:return
        root,py,worker=self.paths()
        if not py.is_file(): raise RuntimeError(f'Browser sidecar missing: {py}')
        if not worker.is_file(): raise RuntimeError(f'Browser sidecar worker missing: {worker}')
        self.proc=await asyncio.create_subprocess_exec(str(py),str(worker),cwd=str(root),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
    async def call(self,method:str,params:dict[str,Any]|None=None,timeout:float=60.0):
        await self.start()
        async with self._lock:
            self._seq+=1; rid=self._seq
            payload=(__import__('json').dumps({'id':rid,'method':method,'params':params or {}},ensure_ascii=False)+'\n').encode()
            assert self.proc and self.proc.stdin and self.proc.stdout
            self.proc.stdin.write(payload); await self.proc.stdin.drain()
            line=await asyncio.wait_for(self.proc.stdout.readline(),timeout=timeout)
            if not line: raise RuntimeError('Browser sidecar exited without response')
            data=__import__('json').loads(line.decode('utf-8','replace'))
            if data.get('id')!=rid: raise RuntimeError('Browser sidecar protocol desynchronized')
            if not data.get('ok'): raise RuntimeError(str(data.get('error','browser sidecar failed')))
            return data.get('result')
    async def close(self):
        if self.proc and self.proc.returncode is None:
            try: await self.call('stop',{},timeout=20)
            except Exception: self.proc.terminate()
            try: await asyncio.wait_for(self.proc.wait(),timeout=5)
            except Exception:
                self.proc.kill(); await self.proc.wait()
        self.proc=None

class BrowserUseBackend(HttpBrowserBackend):
    """Browser Use provider executed in the isolated ``.venv-browser`` sidecar.

    GAIA Core keeps URL validation, authority and content trust handling. Only the
    dependency-heavy Browser Use runtime crosses the JSON-lines worker boundary.
    """
    def __init__(self,profile=None):
        super().__init__(profile); self.backend_name='browser-use-sidecar'; self._client=_BrowserSidecarClient(); self.session=None; self.page=None
    def health(self):
        root,py,worker=self._client.paths()
        if not py.is_file(): return {'status':'DEPENDENCY_MISSING','dependency':'browser-use','sidecar':str(py)}
        try:
            import subprocess
            code="import browser_use,playwright; print(getattr(browser_use,'__version__','unknown'))"
            r=subprocess.run([str(py),'-c',code],capture_output=True,text=True,timeout=15)
            if r.returncode==0:return {'status':'AVAILABLE','backend':'browser-use-sidecar','version':r.stdout.strip() or 'unknown','api':'isolated JSON worker'}
            return {'status':'DEPENDENCY_MISSING','dependency':'browser-use','error':(r.stderr or r.stdout).strip()[-500:]}
        except Exception as exc:return {'status':'DEPENDENCY_MISSING','dependency':'browser-use','error':type(exc).__name__}
    async def launch(self):
        try:
            result=await self._client.call('launch',{'headless':True,'allowed_domains':sorted(self.profile.allowed_domains),'persistent':self.profile.persistent,'user_data_dir':self.profile.user_data_dir,'launch_timeout':self.profile.launch_timeout,'executable_path':_discover_browser_executable()},timeout=self.profile.launch_timeout+15)
            self.session=True; self.page=True; return {'status':'ready','backend':'browser-use-sidecar','profile':self.profile.name,'tabs':result.get('tabs',[])}
        except asyncio.TimeoutError as exc:
            await self.close(); raise TimeoutError(f'Browser Use launch exceeded {self.profile.launch_timeout}s') from exc
        except Exception as exc:
            await self.close(); raise RuntimeError(f'Browser Use sidecar launch failed: {type(exc).__name__}: {exc}') from exc
    def _require(self):
        if not self.session: raise RuntimeError('Browser Use sidecar is not launched')
    async def navigate(self,url):
        self.security.check_url(url); self._require(); raw=await self._client.call('navigate',{'url':url}); self.current=str(raw.get('url',url)); self.content=str(raw.get('html',''))
        data=self.security.content(str(raw.get('text',''))); data['dom']=self.content[:200000]
        return {'url':self.current,'content':data,'backend':'browser-use-sidecar'}
    async def read_page(self):
        self._require(); raw=await self._client.call('read_page',{}); self.current=str(raw.get('url',self.current)); self.content=str(raw.get('html','')); data=self.security.content(str(raw.get('text',''))); data['dom']=self.content[:200000]; return data
    async def extract(self,query): self._require(); raw=await self._client.call('extract',{'query':query}); return {'query':query,'text':str(raw.get('text',''))[:20000],'trusted':False,'trust':'EXTERNAL_UNTRUSTED'}
    async def query(self,selector): self._require(); return await self._client.call('query',{'selector':selector})
    async def click(self,selector,**kwargs): self._require(); return await self._client.call('click',{'selector':selector,'kwargs':kwargs})
    async def type(self,selector,text,**kwargs): self._require(); return await self._client.call('type',{'selector':selector,'text':str(text),'kwargs':kwargs})
    async def select(self,selector,value): self._require(); return await self._client.call('select',{'selector':selector,'value':value})
    async def scroll(self,amount=600): self._require(); return await self._client.call('scroll',{'amount':amount})
    async def upload(self,selector,path): self._require(); return await self._client.call('upload',{'selector':selector,'path':str(path)})
    async def download(self,*args,**kwargs): self._require(); return await self._client.call('download',{})
    async def submit(self,selector): self._require(); return await self._client.call('submit',{'selector':selector})
    async def back(self): self._require(); return await self._client.call('back',{})
    async def forward(self): self._require(); return await self._client.call('forward',{})
    async def refresh(self): self._require(); return await self._client.call('refresh',{})
    async def new_tab(self,url='about:blank'): self._require(); return await self._client.call('new_tab',{'url':url})
    async def close_tab(self,index=None): self._require(); return await self._client.call('close_tab',{'index':index})
    async def switch_tab(self,index): self._require(); return await self._client.call('switch_tab',{'index':int(index)})
    async def list_tabs(self): return [] if not self.session else await self._client.call('list_tabs',{})
    async def screenshot(self,path=None): self._require(); return await self._client.call('screenshot',{'path':path})
    async def wait(self,seconds=1): self._require(); return await self._client.call('wait',{'seconds':seconds})
    async def stop(self):
        await self._client.close(); self.session=None; self.page=None; return {'status':'stopped','backend':'browser-use-sidecar'}
    async def close(self): return await self.stop()
    async def cancel(self): return await self.stop()

