"""Persistencia bounded y parametrizada para Event Engine v0.9.0."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid
from typing import Any

import memory


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any, default: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return json.dumps(default, ensure_ascii=False, separators=(",", ":"))


def _loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _row_dict(row: Any) -> dict[str, Any]:
    item = dict(row)
    for key in ("trigger_json", "conditions_json", "steps_json", "required_capabilities_json", "spec_json", "result_json", "payload_json"):
        if key in item:
            item[key[:-5] if key.endswith("_json") else key] = _loads(item.pop(key), [] if key in {"conditions_json", "steps_json", "required_capabilities_json"} else {})
    for key in ("enabled", "read", "dismissed", "sensitive"):
        if key in item:
            item[key] = bool(item[key])
    return item


def save_rule(rule: dict[str, Any], *, owner_device: str, enabled: bool = False) -> dict[str, Any]:
    memory.init_db()
    rule_id = str(rule.get("rule_id") or f"rule_{uuid.uuid4().hex}")[:80]
    name = str(rule.get("name") or "Regla sin nombre").strip()[:160]
    trigger = rule.get("trigger") if isinstance(rule.get("trigger"), dict) else {}
    conditions = rule.get("conditions") if isinstance(rule.get("conditions"), list) else []
    steps = rule.get("steps") if isinstance(rule.get("steps"), list) else []
    routine_id = str(rule.get("routine_id") or "")[:80] or None
    cooldown = min(86400, max(5, int(rule.get("cooldown_seconds", 300))))
    run_limit = min(1000, max(0, int(rule.get("run_limit", 0))))
    quiet = str(rule.get("quiet_hour_policy") or "skip").lower()
    if quiet not in {"skip", "notify_only", "defer"}:
        quiet = "skip"
    now = _now()
    with memory.get_db() as conn:
        conn.execute("""INSERT INTO automation_rules(rule_id,name,owner_device,enabled,trigger_json,conditions_json,routine_id,steps_json,cooldown_seconds,quiet_hour_policy,run_limit,schema_version,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?,?)
            ON CONFLICT(rule_id) DO UPDATE SET name=excluded.name,owner_device=excluded.owner_device,enabled=excluded.enabled,trigger_json=excluded.trigger_json,conditions_json=excluded.conditions_json,routine_id=excluded.routine_id,steps_json=excluded.steps_json,cooldown_seconds=excluded.cooldown_seconds,quiet_hour_policy=excluded.quiet_hour_policy,run_limit=excluded.run_limit,updated_at=excluded.updated_at""",
            (rule_id, name, str(owner_device)[:80], int(enabled), _json(trigger, {}), _json(conditions, []), routine_id, _json(steps, []), cooldown, quiet, run_limit, now, now))
    return get_rule(rule_id) or {"rule_id": rule_id, "name": name, "owner_device": owner_device, "enabled": bool(enabled)}


def get_rule(rule_id: str) -> dict[str, Any] | None:
    memory.init_db()
    with memory.get_db() as conn:
        row = conn.execute("SELECT * FROM automation_rules WHERE rule_id=?", (str(rule_id)[:80],)).fetchone()
    return _row_dict(row) if row else None


def list_rules(owner_device: str | None = None, *, include_disabled: bool = True) -> list[dict[str, Any]]:
    memory.init_db()
    query = "SELECT * FROM automation_rules"
    params: list[Any] = []
    clauses: list[str] = []
    if owner_device:
        clauses.append("owner_device=?")
        params.append(str(owner_device)[:80])
    if not include_disabled:
        clauses.append("enabled=1")
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY updated_at DESC LIMIT 200"
    with memory.get_db() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [_row_dict(row) for row in rows]


def list_rules_for_event(event_type: str, *, include_disabled: bool = False) -> list[dict[str, Any]]:
    """Return only rules targeted at an event or rules without an event filter.

    JSON1 is available in the supported SQLite builds. A conservative fallback
    retains the v0.8 full bounded scan if a platform omits the extension.
    """
    memory.init_db()
    query = "SELECT * FROM automation_rules WHERE (json_extract(trigger_json, '$.event_type')=? OR json_extract(trigger_json, '$.event_type') IS NULL)"
    params: list[Any] = [str(event_type)[:100]]
    if not include_disabled:
        query = query.replace(" WHERE ", " WHERE enabled=1 AND ")
    query += " ORDER BY updated_at DESC LIMIT 200"
    try:
        with memory.get_db() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
    except Exception:
        return list_rules(include_disabled=include_disabled)
    return [_row_dict(row) for row in rows]


def set_rule_enabled(rule_id: str, enabled: bool, *, owner_device: str | None = None) -> bool:
    memory.init_db()
    query = "UPDATE automation_rules SET enabled=?, updated_at=? WHERE rule_id=?"
    params: list[Any] = [int(enabled), _now(), str(rule_id)[:80]]
    if owner_device:
        query += " AND owner_device=?"
        params.append(str(owner_device)[:80])
    with memory.get_db() as conn:
        cur = conn.execute(query, tuple(params))
    return cur.rowcount == 1


def save_routine(routine: dict[str, Any], *, owner_device: str, enabled: bool = False) -> dict[str, Any]:
    memory.init_db()
    routine_id = str(routine.get("routine_id") or f"routine_{uuid.uuid4().hex}")[:80]
    name = str(routine.get("name") or "Rutina sin nombre").strip()[:160]
    steps = routine.get("steps") if isinstance(routine.get("steps"), list) else []
    if not 1 <= len(steps) <= 5:
        raise ValueError("Una rutina debe tener entre 1 y 5 steps.")
    caps = sorted({str(step.get("action") or step.get("capability") or "")[:100] for step in steps if isinstance(step, dict) and (step.get("action") or step.get("capability"))})
    max_risk = min(4, max(0, int(routine.get("max_risk", 0))))
    failure = str(routine.get("failure_policy") or "stop").lower()
    if failure not in {"stop", "continue_notify"}:
        failure = "stop"
    now = _now()
    with memory.get_db() as conn:
        conn.execute("""INSERT INTO routines(routine_id,name,owner_device,steps_json,required_capabilities_json,max_risk,failure_policy,enabled,schema_version,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?, ?,1,?,?)
            ON CONFLICT(routine_id) DO UPDATE SET name=excluded.name,owner_device=excluded.owner_device,steps_json=excluded.steps_json,required_capabilities_json=excluded.required_capabilities_json,max_risk=excluded.max_risk,failure_policy=excluded.failure_policy,enabled=excluded.enabled,updated_at=excluded.updated_at""",
            (routine_id, name, str(owner_device)[:80], _json(steps, []), _json(caps, []), max_risk, failure, int(enabled), now, now))
    return get_routine(routine_id) or {"routine_id": routine_id, "name": name, "owner_device": owner_device, "steps": steps}


def get_routine(routine_id: str) -> dict[str, Any] | None:
    memory.init_db()
    with memory.get_db() as conn:
        row = conn.execute("SELECT * FROM routines WHERE routine_id=?", (str(routine_id)[:80],)).fetchone()
    return _row_dict(row) if row else None


def list_routines(owner_device: str | None = None, *, include_disabled: bool = True) -> list[dict[str, Any]]:
    memory.init_db()
    query = "SELECT * FROM routines"
    params: list[Any] = []
    clauses: list[str] = []
    if owner_device:
        clauses.append("owner_device=?")
        params.append(str(owner_device)[:80])
    if not include_disabled:
        clauses.append("enabled=1")
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY updated_at DESC LIMIT 100"
    with memory.get_db() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [_row_dict(row) for row in rows]


def set_routine_enabled(routine_id: str, enabled: bool, *, owner_device: str | None = None) -> bool:
    memory.init_db()
    query = "UPDATE routines SET enabled=?, updated_at=? WHERE routine_id=?"
    params: list[Any] = [int(enabled), _now(), str(routine_id)[:80]]
    if owner_device:
        query += " AND owner_device=?"
        params.append(str(owner_device)[:80])
    with memory.get_db() as conn:
        cur = conn.execute(query, tuple(params))
    return cur.rowcount == 1


def save_schedule(schedule: dict[str, Any], *, owner_device: str, enabled: bool = False) -> dict[str, Any]:
    memory.init_db()
    schedule_id = str(schedule.get("schedule_id") or f"schedule_{uuid.uuid4().hex}")[:80]
    name = str(schedule.get("name") or "Schedule sin nombre").strip()[:160]
    schedule_type = str(schedule.get("schedule_type") or "ONE_TIME").upper()
    if schedule_type not in {"ONE_TIME", "DAILY", "WEEKDAYS", "WEEKLY", "INTERVAL"}:
        raise ValueError("schedule_type inválido")
    missed = str(schedule.get("missed_policy") or "SKIP").upper()
    if missed not in {"SKIP", "RUN_ONCE", "ASK"}:
        raise ValueError("missed_policy inválido")
    timezone_name = str(schedule.get("timezone") or "UTC")[:64]
    spec = schedule.get("spec") if isinstance(schedule.get("spec"), dict) else {}
    routine_id = str(schedule.get("routine_id") or "")[:80] or None
    rule_id = str(schedule.get("rule_id") or "")[:80] or None
    next_due = str(schedule.get("next_due_at") or "")[:64] or None
    max_daily = min(1000, max(1, int(schedule.get("max_runs_per_day", 10))))
    now = _now()
    with memory.get_db() as conn:
        conn.execute("""INSERT INTO schedules(schedule_id,name,owner_device,schedule_type,timezone,spec_json,missed_policy,routine_id,rule_id,enabled,next_due_at,max_runs_per_day,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(schedule_id) DO UPDATE SET name=excluded.name,owner_device=excluded.owner_device,schedule_type=excluded.schedule_type,timezone=excluded.timezone,spec_json=excluded.spec_json,missed_policy=excluded.missed_policy,routine_id=excluded.routine_id,rule_id=excluded.rule_id,enabled=excluded.enabled,next_due_at=excluded.next_due_at,max_runs_per_day=excluded.max_runs_per_day,updated_at=excluded.updated_at""",
            (schedule_id, name, str(owner_device)[:80], schedule_type, timezone_name, _json(spec, {}), missed, routine_id, rule_id, int(enabled), next_due, max_daily, now, now))
    return get_schedule(schedule_id) or {"schedule_id": schedule_id, "name": name, "owner_device": owner_device}


def get_schedule(schedule_id: str) -> dict[str, Any] | None:
    memory.init_db()
    with memory.get_db() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE schedule_id=?", (str(schedule_id)[:80],)).fetchone()
    return _row_dict(row) if row else None


def list_schedules(owner_device: str | None = None, *, include_disabled: bool = True, due_before: str | None = None) -> list[dict[str, Any]]:
    memory.init_db()
    query = "SELECT * FROM schedules"
    params: list[Any] = []
    clauses: list[str] = []
    if owner_device:
        clauses.append("owner_device=?")
        params.append(str(owner_device)[:80])
    if not include_disabled:
        clauses.append("enabled=1")
    if due_before:
        clauses.append("next_due_at IS NOT NULL AND next_due_at<=?")
        params.append(str(due_before)[:64])
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY next_due_at ASC LIMIT 200"
    with memory.get_db() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [_row_dict(row) for row in rows]


def set_schedule_enabled(schedule_id: str, enabled: bool, *, owner_device: str | None = None) -> bool:
    memory.init_db()
    query = "UPDATE schedules SET enabled=?, updated_at=? WHERE schedule_id=?"
    params: list[Any] = [int(enabled), _now(), str(schedule_id)[:80]]
    if owner_device:
        query += " AND owner_device=?"
        params.append(str(owner_device)[:80])
    with memory.get_db() as conn:
        cur = conn.execute(query, tuple(params))
    return cur.rowcount == 1


def claim_due_schedule(schedule_id: str, *, now: str) -> dict[str, Any] | None:
    """Atomically reserve one due schedule; duplicate workers cannot both claim it."""
    memory.init_db()
    run_id = f"run_{uuid.uuid4().hex}"
    with memory.get_db() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE schedule_id=? AND enabled=1 AND next_due_at IS NOT NULL AND next_due_at<=?", (str(schedule_id)[:80], now)).fetchone()
        if not row:
            return None
        cur = conn.execute("UPDATE schedules SET last_due_at=?, run_count=run_count+1, next_due_at=NULL, updated_at=? WHERE schedule_id=? AND enabled=1 AND next_due_at=?", (now, now, row["schedule_id"], row["next_due_at"]))
        if cur.rowcount != 1:
            return None
        conn.execute("INSERT INTO automation_runs(run_id,schedule_id,rule_id,routine_id,dedup_key,chain_id,status,started_at,created_at) VALUES (?,?,?,?,?,?,?,?,?)", (run_id, row["schedule_id"], row["rule_id"], row["routine_id"], f"schedule:{row['schedule_id']}:{row['next_due_at']}", run_id, "pending", now, now))
    claimed = dict(row)
    claimed["run_id"] = run_id
    claimed["spec"] = _loads(claimed.pop("spec_json", "{}"), {})
    claimed["enabled"] = bool(claimed.get("enabled"))
    return claimed


def finish_run(run_id: str, status: str, result: dict[str, Any] | None = None) -> bool:
    memory.init_db()
    allowed = {"completed", "queued", "skipped", "failed", "needs_confirmation"}
    status = status if status in allowed else "failed"
    with memory.get_db() as conn:
        cur = conn.execute("UPDATE automation_runs SET status=?, result_json=?, finished_at=? WHERE run_id=? AND status IN ('pending','running','queued')", (status, _json(result or {}, {}), _now(), str(run_id)[:80]))
    return cur.rowcount == 1


def record_event(event: dict[str, Any], *, retention_days: int = 7) -> bool:
    memory.init_db()
    with memory.get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO automation_event_log(event_id,event_type,source,source_id,host,device,timestamp,payload_json,severity,dedup_key,chain_id,chain_depth,expires_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (str(event.get("event_id", ""))[:80], str(event.get("event_type", ""))[:100], str(event.get("source", ""))[:80], str(event.get("source_id", ""))[:80], str(event.get("host", ""))[:80], str(event.get("device", ""))[:80], str(event.get("timestamp") or _now())[:64], _json(event.get("payload") if isinstance(event.get("payload"), dict) else {}, {}), str(event.get("severity", "info"))[:16], str(event.get("dedup_key", ""))[:160], str(event.get("chain_id", ""))[:80], int(event.get("chain_depth", 0)), event.get("expires_at")))
        conn.execute("DELETE FROM automation_event_log WHERE timestamp < datetime('now', ?)", (f"-{max(1, int(retention_days))} days",))
    return True


def add_notification(*, title: str, message: str, severity: str = "info", source: str = "automation", device_scope: str = "", sensitive: bool = False, expires_at: str | None = None) -> dict[str, Any]:
    memory.init_db()
    notification_id = f"notification_{uuid.uuid4().hex}"
    with memory.get_db() as conn:
        conn.execute("INSERT INTO notifications(notification_id,title,message,severity,source,device_scope,sensitive,expires_at) VALUES (?,?,?,?,?,?,?,?)", (notification_id, str(title)[:200], str(message)[:4000], str(severity)[:16], str(source)[:80], str(device_scope)[:80], int(sensitive), expires_at))
    return get_notification(notification_id) or {"notification_id": notification_id, "title": title, "message": message}


def get_notification(notification_id: str) -> dict[str, Any] | None:
    memory.init_db()
    with memory.get_db() as conn:
        row = conn.execute("SELECT * FROM notifications WHERE notification_id=?", (str(notification_id)[:100],)).fetchone()
    return _row_dict(row) if row else None


def list_notifications(device_scope: str | None = None, *, include_dismissed: bool = False) -> list[dict[str, Any]]:
    memory.init_db()
    query = "SELECT * FROM notifications WHERE (expires_at IS NULL OR expires_at>?)"
    params: list[Any] = [_now()]
    if device_scope:
        query += " AND (device_scope='' OR device_scope=?)"
        params.append(str(device_scope)[:80])
    if not include_dismissed:
        query += " AND dismissed=0"
    query += " ORDER BY timestamp DESC LIMIT 200"
    with memory.get_db() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [_row_dict(row) for row in rows]


def mark_notification(notification_id: str, *, read: bool | None = None, dismissed: bool | None = None) -> bool:
    changes: list[str] = []
    values: list[Any] = []
    if read is not None:
        changes.append("read=?")
        values.append(int(read))
    if dismissed is not None:
        changes.append("dismissed=?")
        values.append(int(dismissed))
    if not changes:
        return False
    values.append(str(notification_id)[:100])
    memory.init_db()
    with memory.get_db() as conn:
        cur = conn.execute(f"UPDATE notifications SET {', '.join(changes)} WHERE notification_id=?", tuple(values))
    return cur.rowcount == 1


def set_schedule_next_due(schedule_id: str, next_due_at: str | None) -> bool:
    memory.init_db()
    with memory.get_db() as conn:
        cur = conn.execute("UPDATE schedules SET next_due_at=?, updated_at=? WHERE schedule_id=?", (next_due_at, _now(), str(schedule_id)[:80]))
    return cur.rowcount == 1
