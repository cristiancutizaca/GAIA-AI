from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import re, uuid

PLAN_STATES = frozenset({'PENDING','PLANNING','WAITING_PERMISSION','READY','RUNNING','SUCCEEDED','FAILED','CANCELLED','INTERRUPTED','SKIPPED'})

@dataclass
class PlanDependency:
    task_id: str
    depends_on: str
    condition: str = 'success'

@dataclass
class CapabilityRequest:
    capability: str
    provider: str = ''
    risk: str = 'READ_ONLY'
    resource_scope: str = ''
    permission: str = 'chat'
    confirmed: bool = False

@dataclass
class RiskAssessment:
    level: str = 'READ_ONLY'
    reasons: list[str] = field(default_factory=list)
    external_content: bool = False

@dataclass
class PermissionRequirement:
    capability: str
    decision: str = 'DENY_BY_DEFAULT'
    duration: str = 'once'
    scope: str = ''

@dataclass
class WorkerAssignment:
    worker: str = 'core'
    budget_steps: int = 1
    timeout_seconds: float = 30.0

@dataclass
class SuccessCriteria:
    checks: list[str] = field(default_factory=list)

@dataclass
class RetryPolicy:
    max_retries: int = 1
    backoff_seconds: float = 0.5
    fallback: str = 'abort_unsafe'

@dataclass
class PlanStep:
    id: str
    description: str
    capability: CapabilityRequest | None = None
    skill: str = 'system_diagnostics'
    dependencies: list[PlanDependency] = field(default_factory=list)
    worker: WorkerAssignment = field(default_factory=WorkerAssignment)
    success: SuccessCriteria = field(default_factory=SuccessCriteria)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    state: str = 'PENDING'
    result: dict[str, Any] | None = None
    error: str = ''

@dataclass
class Plan:
    id: str
    goal: str
    steps: list[PlanStep]
    state: str = 'PLANNING'
    risk: RiskAssessment = field(default_factory=RiskAssessment)
    created_at: str = ''
    retries: int = 0

# Backward-compatible alias used by earlier tests.
PlanTask = PlanStep

class Planner:
    """Small deterministic planner; model routing can replace its classifier without changing contracts."""
    def create(self, goal, task_specs):
        tasks=[]
        for spec in task_specs:
            tasks.append(PlanStep('task_'+uuid.uuid4().hex, spec.get('description',''), capability=None, skill=spec.get('worker','research'), worker=WorkerAssignment(spec.get('worker','research')), state='PENDING'))
        return Plan('plan_'+uuid.uuid4().hex, goal, tasks, state='READY')
    def serialize(self, plan): return asdict(plan)
    def plan(self, message: str, *, mcp_configs: dict[str, Any] | None = None) -> Plan:
        text=str(message).strip(); low=text.casefold(); step_id='step_'+uuid.uuid4().hex
        capability=None; skill='system_diagnostics'; description='Conversational response'; risk='READ_ONLY'; permission='chat'; scope='conversation'; checks=['response_available']
        url= re.search(r'\bhttps?://[^\s]+|\b(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s]*)?', text, re.I)
        if re.search(r'\b(recuerda|remember|guarda|save)\b', low):
            capability=CapabilityRequest('memory.write','MemoryV2Store','LOW_RISK','memory:owner','memory_write',True); skill='memory_management'; description='Guardar una memoria explícita'; risk='LOW_RISK'; permission='memory_write'; scope='memory:owner'; checks=['memory_id']
        elif re.search(r'\b(?:qué|que|what)\b.*\b(?:recuerd|memory|base de datos|database|proyecto)\b', low) or 'what do you remember' in low:
            capability=CapabilityRequest('memory.read','MemoryV2Store','READ_ONLY','memory:owner','memory_read'); skill='memory_management'; description='Consultar memoria relevante'; checks=['results_scoped']
        elif url and re.search(r'\b(?:abre|abrir|lee|leer|busca|buscar|open|read|search)\b', low):
            capability=CapabilityRequest('browser.read','HttpBrowserBackend','READ_ONLY','web:read','chat'); skill='browser_research'; description='Leer una página web sin mutación'; scope='web:read'; checks=['untrusted_content_label']
        elif mcp_configs and re.search(r'\b(?:herramienta|tool|mcp|servidor|server|lee|read|consulta|query|busca|search)\b', low):
            for server,cfg in mcp_configs.items():
                tools=sorted(getattr(cfg,'allow_tools',()) or ())
                tool=next((t for t in tools if any(x in t.casefold() for x in ('read','list','get','search','status','health','inspect'))), None)
                if tool:
                    capability=CapabilityRequest('mcp.tool','MCPManager','READ_ONLY',f'mcp:{server}/{tool}','actions_request'); skill='research'; description=f'Usar herramienta MCP {server}/{tool}'; scope=f'mcp:{server}/{tool}'; checks=['tool_result_redacted']; break
        if capability is not None and risk=='READ_ONLY': risk=capability.risk
        if capability is not None and risk != 'READ_ONLY':
            state='WAITING_PERMISSION'
        else: state='READY'
        step=PlanStep(step_id,description,capability=capability,skill=skill,worker=WorkerAssignment('core'),success=SuccessCriteria(checks),state=state)
        return Plan('plan_'+uuid.uuid4().hex,text,[step],state=state,risk=RiskAssessment(risk, [description], external_content=capability is not None and capability.capability=='browser.read'))
