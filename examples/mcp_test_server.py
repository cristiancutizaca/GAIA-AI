import json,sys
for line in sys.stdin:
 r=json.loads(line); m=r.get("method"); result={"capabilities":{"tools":{}}} if m=="initialize" else ({"tools":[{"name":"read","description":"safe test tool"}]} if m=="tools/list" else {"content":[{"type":"text","text":"ok"}]} if m=="tools/call" else {})
 print(json.dumps({"jsonrpc":"2.0","id":r.get("id"),"result":result}),flush=True)
