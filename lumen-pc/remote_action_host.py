from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from action_host import ActionHost
from desktop_context import get_desktop_context
from preflight import preflight_contract


class RemoteActionHostError(RuntimeError):
    pass


class RemoteActionHost:
    """Background consumer for Core-approved actions targeting pc-main.

    The host never interprets free text. It only transforms the already structured
    pending intent into the same ActionHost contract used by the local PC GUI.
    """

    def __init__(
        self,
        *,
        core_url: str | None = None,
        token: str | None = None,
        device_id: str | None = None,
        project_dir: Path | None = None,
        poll_seconds: float | None = None,
        heartbeat_seconds: float | None = None,
        client: httpx.Client | None = None,
        action_host: ActionHost | None = None,
    ) -> None:
        self.core_url = (core_url or os.getenv("LUMEN_CORE_URL", "http://127.0.0.1:8090")).rstrip("/")
        self.token = str(token or os.getenv("GAIA_REMOTE_HOST_TOKEN", "")).strip()
        self.device_id = str(device_id or os.getenv("GAIA_PC_DEVICE_ID", "pc-main")).strip() or "pc-main"
        self.poll_seconds = max(1.0, float(poll_seconds or os.getenv("GAIA_REMOTE_HOST_POLL_SECONDS", "2.0")))
        self.heartbeat_seconds = max(5.0, float(heartbeat_seconds or os.getenv("GAIA_REMOTE_HOST_HEARTBEAT_SECONDS", "15.0")))
        self.client = client or httpx.Client(timeout=httpx.Timeout(20.0, connect=5.0))
        self.owns_client = client is None
        self.action_host = action_host or ActionHost(project_dir or Path.cwd())
        self.stop_event = threading.Event()
        self._close_lock = threading.Lock()
        self._closed = False
        self.busy = False
        self.last_error = ""
        self.last_seen = 0.0
        self._last_heartbeat = 0.0
        self.last_preflight: dict[str, Any] = {}

    @property
    def headers(self) -> dict[str, str]:
        if not self.token:
            raise RemoteActionHostError("GAIA_REMOTE_HOST_TOKEN no está configurado; el host permanece offline.")
        return {"Authorization": f"Bearer {self.token}", "X-GAIA-Host-Device": self.device_id}

    def close(self) -> None:
        self.stop_event.set()
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            if self.owns_client:
                self.client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self.client.request(method, f"{self.core_url}{path}", headers=self.headers, **kwargs)
        response.raise_for_status()
        return response

    def heartbeat(self, *, busy: bool | None = None) -> dict:
        if busy is not None:
            self.busy = bool(busy)
        response = self._request("POST", "/api/action-host/heartbeat", json={"device_id": self.device_id, "host_version": self.action_host.public_capabilities().get("host_version", "1.0.0-rc6-pc"), "busy": self.busy})
        self.last_seen = time.monotonic()
        self.last_error = ""
        self._last_heartbeat = self.last_seen
        return response.json()

    def pending(self) -> list[dict]:
        response = self._request("GET", "/api/actions/pending")
        actions = response.json().get("actions", [])
        return [item for item in actions if str(item.get("target_host") or item.get("execution_host") or item.get("device") or "") == self.device_id]

    def claim(self, action_id: str, session_id: str) -> dict:
        return self._request("POST", "/api/actions/claim", json={"action_id": action_id, "session_id": session_id}).json()

    def _contract(self, item: dict) -> dict:
        raw = item.get("intent") if isinstance(item.get("intent"), dict) else {}
        action_id = str(item.get("action_id") or "")
        session_id = str(item.get("session_id") or "")
        if raw.get("type") == "plan" or isinstance(raw.get("actions"), list):
            actions = []
            for action in raw.get("actions", []):
                if not isinstance(action, dict):
                    continue
                normalized = dict(action)
                normalized.setdefault("type", "action")
                actions.append(normalized)
            return {"kind": "plan", "confirmation_required": False, "action_id": action_id, "session_id": session_id, "plan": {"type": "plan", "plan_id": action_id, "actions": actions, "risk_level": int(raw.get("risk_level", 0)), "confidence": float(raw.get("confidence", 0.99)), "source": raw.get("source", "remote")}, "device": item.get("requesting_device") or item.get("device"), "requesting_device": item.get("requesting_device") or item.get("device"), "target_host": item.get("target_host") or item.get("execution_host") or self.device_id}
        action = dict(raw)
        action.setdefault("type", "action")
        return {"kind": "action", "confirmation_required": False, "action_id": action_id, "session_id": session_id, "action": action, "device": item.get("requesting_device") or item.get("device"), "requesting_device": item.get("requesting_device") or item.get("device"), "target_host": item.get("target_host") or item.get("execution_host") or self.device_id}

    def complete(self, item: dict, verified) -> dict:
        payload = verified.as_payload() if hasattr(verified, "as_payload") else verified.as_dict()
        data = dict(payload.get("data") or {})
        data.update({"execution_verified": bool(payload.get("execution_verified")), "host_version": payload.get("host_version"), "audit_digest": payload.get("audit_digest"), "verified_result": payload})
        return self._request("POST", "/api/actions/complete", json={"action_id": item["action_id"], "session_id": item["session_id"], "device": self.device_id, "success": bool(payload.get("success")), "message": str(payload.get("message") or "Acción completada."), "data": data}).json()

    def execute_item(self, item: dict) -> dict:
        self.busy = True
        self.heartbeat(busy=True)
        try:
            self.claim(str(item["action_id"]), str(item["session_id"]))
            contract = self._contract(item)
            # The remote host resolves its own current context; the Core/Android
            # request is never allowed to assert a foreground identity.
            context = get_desktop_context(level="FOREGROUND", force_refresh=True)
            self._attach_contextual_target(contract, context)
            self.last_preflight = preflight_contract(self.action_host.engine, contract, device=self.device_id)
            # ActionHost repeats the same read-only preflight at the execution
            # boundary; this second check closes the race before any effect.
            verified = self.action_host.execute(contract, confirmed=True)
            result = self.complete(item, verified)
            self.last_error = ""
            return result
        finally:
            self.busy = False
            try:
                self.heartbeat(busy=False)
            except Exception as exc:
                self.last_error = str(exc)[:300]

    def _attach_contextual_target(self, contract: dict, context: dict[str, Any]) -> None:
        """Fill only absent contextual window fields from this host snapshot."""
        snapshot_window = context.get("active_window") if isinstance(context, dict) else None
        if not isinstance(snapshot_window, dict):
            return
        target = {key: snapshot_window.get(key) for key in ("window_id", "pid", "process", "process_executable", "title", "bounds") if snapshot_window.get(key) not in (None, "")}
        def update_action(action: dict) -> None:
            args = action.get("args") if isinstance(action.get("args"), dict) else {}
            name = str(action.get("name") or action.get("action") or "")
            if name in {"uia_inspect_window", "uia_list_controls", "uia_get_focused_control", "screen_capture_window", "uia_focus_control", "uia_invoke_control", "uia_set_value"}:
                args.setdefault("window_id", str(snapshot_window.get("window_id") or ""))
                if name.startswith("uia_") or name == "screen_capture_window":
                    args.setdefault("expected_target", target)
            action["args"] = args
        plan = contract.get("plan") if isinstance(contract.get("plan"), dict) else None
        if plan and isinstance(plan.get("actions"), list):
            for action in plan["actions"]:
                if isinstance(action, dict):
                    update_action(action)
        elif isinstance(contract.get("action"), dict):
            update_action(contract["action"])

    def run_once(self) -> dict:
        self.heartbeat(busy=self.busy)
        actions = self.pending()
        completed = []
        for item in actions:
            if self.stop_event.is_set():
                break
            try:
                completed.append(self.execute_item(item))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {404, 409}:
                    continue
                self.last_error = f"HTTP {exc.response.status_code}"
            except Exception as exc:
                self.last_error = str(exc)[:300]
        return {"status": "online", "device_id": self.device_id, "pending_seen": len(actions), "completed": completed, "busy": self.busy, "last_error": self.last_error}

    def run_forever(self) -> None:
        try:
            self.heartbeat(busy=False)
            while not self.stop_event.is_set():
                started = time.monotonic()
                try:
                    self.run_once()
                except Exception as exc:
                    self.last_error = str(exc)[:300]
                    self.stop_event.wait(min(self.poll_seconds * 3, 15.0))
                    continue
                elapsed = time.monotonic() - started
                self.stop_event.wait(max(0.1, self.poll_seconds - elapsed))
        finally:
            try:
                self.heartbeat(busy=False)
            except Exception:
                pass
            self.close()


def main() -> int:
    host = RemoteActionHost()
    try:
        host.run_forever()
    except KeyboardInterrupt:
        host.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
