from __future__ import annotations
import re
SECRET_KEYS=("password","secret","token","api_key","apikey","cookie","authorization","private_key")
def redact(value):
    if isinstance(value,dict): return {str(k):("[REDACTED]" if any(x in str(k).lower() for x in SECRET_KEYS) else redact(v)) for k,v in value.items()}
    if isinstance(value,list): return [redact(v) for v in value[:100]]
    text=str(value)
    for pattern in (r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+",r"(?i)(sk-[A-Za-z0-9_-]{10,})",r"(?i)(gh[pousr]_[A-Za-z0-9_]{10,})"):
        text=re.sub(pattern,lambda m:(m.group(1)+"[REDACTED]") if m.lastindex else "[REDACTED]",text)
    return text[:8192]
def web_content_is_untrusted(text:str)->bool:
    patterns=("ignore previous instructions","send secrets","download and execute","copy api key","reveal password")
    low=text.lower(); return any(p in low for p in patterns)
def guard_web_content(text:str)->dict:
    return {"content":redact(text),"trusted":False,"prompt_injection_suspected":web_content_is_untrusted(text),"authority":"WEB_CONTENT_ONLY"}
