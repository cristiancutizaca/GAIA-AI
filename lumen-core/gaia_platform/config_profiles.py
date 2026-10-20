from __future__ import annotations
PROFILES={"minimal":{"mcp":False,"browser":False,"voice_v2":False,"mem0":False,"graph_memory":False,"coding_worker":False,"computer_use":False,"visualizer":False,"realtime_transport":False},"standard":{"mcp":True,"browser":False,"voice_v2":False,"mem0":False,"graph_memory":False,"coding_worker":False,"computer_use":False,"visualizer":True,"realtime_transport":False},"full":{"mcp":True,"browser":True,"voice_v2":True,"mem0":True,"graph_memory":False,"coding_worker":True,"computer_use":False,"visualizer":True,"realtime_transport":False},"development":{"mcp":True,"browser":True,"voice_v2":True,"mem0":True,"graph_memory":True,"coding_worker":True,"computer_use":False,"visualizer":True,"realtime_transport":False}}
def get(name):
 if name not in PROFILES: raise KeyError(name)
 return dict(PROFILES[name])
