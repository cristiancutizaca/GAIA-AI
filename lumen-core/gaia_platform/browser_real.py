from __future__ import annotations
import asyncio, base64, ipaddress, re, urllib.parse, urllib.request
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

class BrowserUseBackend(HttpBrowserBackend):
    """Browser Use actor API adapter (BrowserSession + actor.Page/Element), not Playwright API."""
    def __init__(self,profile=None): super().__init__(profile); self.session=None; self.page=None; self.backend_name="browser-use"; self._pages={}
    def health(self):
        try:
            import browser_use
            return {"status":"AVAILABLE","backend":"browser-use","version":getattr(browser_use,"__version__","unknown"),"api":"BrowserSession/actor.Page"}
        except Exception as exc:return {"status":"DEPENDENCY_MISSING","dependency":"browser-use","error":type(exc).__name__}
    async def launch(self):
        try:
            from browser_use import BrowserSession
            kwargs={"headless":True,"keep_alive":False,"is_local":True,"cloud_browser":False,"use_cloud":False,"executable_path":"/usr/bin/chromium","allowed_domains":sorted(self.profile.allowed_domains) or None,"enable_default_extensions":False}
            if self.profile.persistent and self.profile.user_data_dir: kwargs["user_data_dir"]=str(Path(self.profile.user_data_dir).resolve())
            self.session=BrowserSession(**kwargs); await asyncio.wait_for(self.session.start(),timeout=self.profile.launch_timeout); self.page=await self.session.get_current_page()
            if self.page is None: self.page=await self.session.new_page()
            self._pages[str(getattr(self.page,"_target_id",id(self.page)))]=self.page
            return {"status":"ready","backend":"browser-use","profile":self.profile.name,"tabs":await self.list_tabs()}
        except asyncio.TimeoutError as exc:
            await self.close(); raise TimeoutError(f"Browser Use launch exceeded {self.profile.launch_timeout}s; install Chromium and retry") from exc
        except Exception as exc:
            await self.close(); raise RuntimeError(f"Browser Use launch failed: {type(exc).__name__}: {exc}") from exc
    def _require(self):
        if not self.session or not self.page: raise RuntimeError("Browser Use session is not launched")
    async def navigate(self,url): self.security.check_url(url); self._require(); await self.page.goto(url); self.current=await self.page.get_url(); return {"url":self.current,"content":await self.read_page(),"backend":"browser-use"}
    async def read_page(self):
        self._require(); text=await self.page.evaluate("() => document.body ? document.body.innerText : ''"); html=await self.page.evaluate("() => document.documentElement ? document.documentElement.outerHTML : ''"); self.content=html; data=self.security.content(str(text)); data["dom"]=str(html)[:200000]; return data
    async def extract(self,query): self._require(); text=await self.page.evaluate("() => document.body ? document.body.innerText : ''"); return {"query":query,"text":str(text)[:20000],"trusted":False,"trust":"EXTERNAL_UNTRUSTED"}
    async def query(self,selector): self._require(); els=await self.page.get_elements_by_css_selector(selector); return {"selector":selector,"count":len(els),"elements":[await e.get_basic_info() for e in els]}
    async def _element(self, selector):
        els = await self.page.get_elements_by_css_selector(selector)
        if not els: raise LookupError(f"Browser Use selector matched no element: {selector}")
        return els[0]
    async def click(self,selector,**kwargs):
        self._require(); await (await self._element(selector)).click(**kwargs)
        return {"status":"clicked","selector":selector}
    async def type(self,selector,text,**kwargs):
        self._require(); await (await self._element(selector)).fill(str(text), clear=kwargs.pop("clear",True))
        return {"status":"typed","selector":selector}
    async def select(self,selector,value):
        self._require(); await (await self._element(selector)).select_option(value)
        return {"status":"selected","selector":selector,"value":value}
    async def scroll(self,amount=600): self._require(); await self.page.evaluate("(y) => window.scrollBy(0, y)",amount); return {"status":"scrolled","amount":amount}
    async def upload(self,selector,path):
        self._require(); raise RuntimeError("Browser Use actor upload requires an upstream file-input API not exposed by this installed version")
    async def download(self,*args,**kwargs): self._require(); return {"status":"use-browser-downloads","files":[str(x) for x in getattr(self.session,"downloaded_files",[]) or []]}
    async def submit(self,selector): self._require(); return await self.click(selector)
    async def back(self): self._require(); await self.page.go_back(); return {"url":await self.page.get_url()}
    async def forward(self): self._require(); await self.page.go_forward(); return {"url":await self.page.get_url()}
    async def refresh(self): self._require(); await self.page.reload(); return {"url":await self.page.get_url()}
    async def new_tab(self,url="about:blank"):
        self._require(); page=await self.session.new_page(url); self.page=page; self._pages[str(getattr(page,"_target_id",id(page)))]=page; return {"url":await page.get_url()}
    async def close_tab(self,index=None):
        self._require(); tabs=await self.session.get_tabs(); target=tabs[index if index is not None else len(tabs)-1]; await self.session.close_page(target.target_id); self.page=await self.session.get_current_page(); return {"tabs":await self.list_tabs()}
    async def switch_tab(self,index):
        self._require(); pages=await self.session.get_pages(); self.page=pages[int(index)]; return {"index":int(index),"url":await self.page.get_url()}
    async def list_tabs(self):
        if not self.session:return []
        tabs=await self.session.get_tabs(); return [{"index":i,"target_id":str(t.target_id),"url":str(t.url),"title":str(t.title)} for i,t in enumerate(tabs)]
    async def screenshot(self,path=None):
        self._require(); target=path or str(Path.cwd()/"gaia-browser-screenshot.png"); data=await self.session.take_screenshot(path=target); return {"status":"saved","path":target,"bytes":len(data)}
    async def wait(self,seconds=1): await asyncio.sleep(min(float(seconds),30)); return {"status":"waited","seconds":float(seconds)}
    async def stop(self):
        if self.session:
            try: await self.session.stop()
            finally: self.session=None; self.page=None; self._pages.clear()
        return {"status":"stopped","backend":"browser-use"}
    async def close(self): return await self.stop()
    async def cancel(self): return await self.stop()
