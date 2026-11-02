"""UI-facing, bounded local operator. No arbitrary shell execution.

One voice or text request produces a durable job with verified read-only steps.
Mutating project steps can only run from explicit operator approval in the CLI;
this UI entry point deliberately refuses such requests.
"""
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))
sys.path.insert(0, str(ROOT / "tools"))
from operator_intent import is_local_diagnostic_request


def describe_task(task: dict) -> str:
    lines = [f"Tarea {task['id'][:18]} · {task['state']}"]
    for step in task.get('steps', []):
        result = step.get('result') or {}
        marker = "✓" if step['state'] == 'SUCCEEDED' else ("×" if step['state'] == 'FAILED' else "·")
        summary = str(result.get('message') or step['state'])[:220]
        lines.append(f"{marker} {step['action']}: {summary}")
        facts = result.get('facts') or {}
        if facts:
            lines.append('    ' + ', '.join(f'{k}={v}' for k,v in facts.items())[:200])
    if task['state'] == 'WAITING_PERMISSION':
        lines.append('Acción protegida: no se ha ejecutado. Usa el operador local con aprobación explícita.')
    if task['state'] in {'FAILED', 'NEEDS_REVIEW'}:
        lines.append('No se ha reintentado a ciegas. Revisa los detalles del paso antes de continuar.')
    return '\n'.join(lines)


def execute_diagnostic(text: str, *, directory: Path = ROOT, db: Path | None = None) -> dict:
    """Only complete read-only plans can be executed from a chat request."""
    if not is_local_diagnostic_request(text):
        raise ValueError('No es una orden de diagnóstico local reconocida.')
    from gaia_operator import Operator, OBSERVE
    op = Operator(directory, db)
    task = op.create(text)
    if any(item['action'] not in OBSERVE for item in task['steps']):
        # No confirmation flow here. Do not leave a runnable job unapproved.
        op.cancel(task['id'])
        raise PermissionError('Las acciones con efectos requieren permiso explícito fuera del chat.')
    complete = op.run(task['id'])
    if complete['state'] not in {'SUCCEEDED', 'FAILED', 'CANCELLED'}:
        complete = op.get(task['id'])
    return {'kind': 'desktop_diagnostic', 'response': describe_task(complete), 'task_id':task['id'],
            'state': complete['state'], 'read_only': True}


def recent_tasks(*, directory: Path = ROOT, db: Path | None = None) -> str:
    from gaia_operator import Operator
    tasks = Operator(directory, db).list()[:10]
    if not tasks:
        return 'No hay tareas recientes.'
    return '\n'.join(f"{x['id'][:18]}: {x['state']} · {x['goal'][:90]}" for x in tasks)
