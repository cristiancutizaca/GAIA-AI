#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from importlib.metadata import version
from pathlib import Path

def emit(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, default=str)); raise SystemExit(code)

def main():
    try:
        p=json.loads(sys.stdin.read() or '{}')
        if p.get('action','run')=='health':
            import openhands.sdk, openhands.tools
            emit({'status':'AVAILABLE','backend':'openhands-sdk-sidecar','version':version('openhands-sdk')})
        from pydantic import SecretStr
        from openhands.sdk import Agent, Conversation, LLM, Tool
        from openhands.tools.file_editor import FileEditorTool
        from openhands.tools.terminal import TerminalTool
        repo=Path(p['repo']).resolve()
        model=p.get('model') or os.getenv('OPENHANDS_MODEL','')
        api_key=p.get('api_key') or os.getenv('OPENHANDS_API_KEY','') or os.getenv('OPENAI_API_KEY','')
        base_url=p.get('base_url') or os.getenv('OPENHANDS_BASE_URL','') or None
        if not model: emit({'status':'CONFIG_REQUIRED','reason':'OPENHANDS_MODEL is required'},3)
        if not api_key and model.startswith(('ollama/','openai/')):
            api_key='ollama' if model.startswith('ollama/') else ''
        if not api_key: emit({'status':'CONFIG_REQUIRED','reason':'OPENHANDS_API_KEY/OPENAI_API_KEY is required for this model'},3)
        llm_kwargs={'usage_id':'gaia-coding','model':model,'api_key':SecretStr(api_key)}
        if base_url: llm_kwargs['base_url']=base_url
        llm=LLM(**llm_kwargs)
        tools=[Tool(name=TerminalTool.name),Tool(name=FileEditorTool.name)]
        agent=Agent(llm=llm,tools=tools)
        conv=Conversation(agent=agent,workspace=str(repo))
        conv.send_message(p['task'])
        conv.run()
        state=getattr(conv,'state',None)
        status=str(getattr(state,'execution_status','completed')) if state is not None else 'completed'
        events=getattr(state,'events',[]) if state is not None else []
        summary=[{'type':type(e).__name__,'source':str(getattr(e,'source',''))} for e in list(events or [])[-100:]]
        emit({'status':'COMPLETED','execution_status':status,'events':summary,'sdk_version':version('openhands-sdk')})
    except SystemExit: raise
    except Exception as exc: emit({'status':'ERROR','error':type(exc).__name__,'detail':str(exc)},1)
if __name__=='__main__': main()
