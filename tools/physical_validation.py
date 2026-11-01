#!/usr/bin/env python3
"""Operator-confirmed physical validation ledger for the current GAIA release.

This tool is intentionally conservative: it never infers physical PASS from
imports, mocks, Linux/sandbox execution, or source inspection. Reports must be
stored outside the project tree so release archives never absorb private
operator evidence by accident.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "lumen-core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))
from gaia_version import PRODUCT_VERSION, RELEASE  # noqa: E402

STATUSES = frozenset({"PASS", "FAIL", "PENDING", "NOT_MEASURED", "BLOCKED", "SKIP"})
REPORT_KIND = "gaia_v2_physical_validation"
CHECKS = (
    ("windows_runtime", "Windows 11 + Python 3.11 clean runtime", "Validate on the target Windows installation, not the build sandbox."),
    ("clean_install", "Clean Full/Full-Computer installation", "Run Setup-GAIA.ps1 in a clean environment and record the dependency/model result."),
    ("resident_launcher", "Resident launcher starts Core before Desktop", "Log in/start GAIA and confirm Core health gate precedes the Desktop shell."),
    ("tray", "System tray icon and menu", "Confirm one visible GAIA tray icon and functional menu actions."),
    ("orb", "Orb show/hide and state rendering", "Confirm wake/interaction shows the Orb and session timeout hides it in wake-only mode."),
    ("no_focus", "Orb does not steal foreground focus", "Trigger the Orb while typing in another application and verify focus remains there."),
    ("quick_hotkey", "Global Quick Command hotkey", "With another application focused, press the configured Quick Command hotkey and confirm it opens."),
    ("ptt_hotkey", "Global push-to-talk hotkey", "Use the configured PTT hotkey and confirm captured speech reaches GAIA."),
    ("microphone", "Physical microphone input", "Enumerate/select the microphone and record a bounded voice turn."),
    ("speaker", "Physical speaker/audio output", "Play a GAIA TTS response through the selected output device."),
    ("gaia_wake", "Actual 'Gaia' wake phrase", "Use the real custom Gaia wake model and confirm several operator-spoken detections."),
    ("wake_false_positive", "Wake false-positive check", "Speak ordinary phrases including 'Jarvis' and record any incorrect wake events."),
    ("silero_vad", "Silero speech endpointing", "Confirm speech start/end detection on the physical microphone without fixed-duration clipping."),
    ("stt_spanish", "Spanish local STT", "Speak a short Spanish fixture and record transcript accuracy/latency."),
    ("tts_spanish", "Spanish local TTS", "Generate and hear a Spanish Piper response using the configured voice."),
    ("barge_in", "Physical barge-in", "Interrupt GAIA while it is speaking; confirm playback stops and the new utterance is accepted."),
    ("conversation_session", "Multi-turn voice session", "After one wake, complete at least two turns without repeating the wake phrase, then verify timeout returns to sleeping."),
    ("browser_use", "Browser Use local interaction", "Run the deterministic local page flow: navigate/read/click/type/submit/screenshot/close."),
    ("openhands", "OpenHands isolated coding task", "Run a bounded broken-repository repair and verify diff/tests/source preservation."),
    ("computer_uia", "Windows UI Automation provider", "Perform a harmless deterministic UIA read/invoke/value action on a test application."),
    ("computer_pyautogui", "PyAutoGUI fallback", "Perform a harmless coordinate fallback action after explicit operator approval."),
    ("safe_mode", "Safe Mode physical behavior", "Enable Safe Mode and verify interactive side effects are denied while diagnostics remain available."),
    ("kill_switch", "Kill Switch physical behavior", "Activate Kill Switch during a harmless cancellable action and confirm new side effects are blocked."),
    ("restart", "Restart GAIA restarts supervised Core + Desktop", "Use the tray restart action and verify a healthy new Core/Desktop cycle without duplicate tray icons."),
    ("startup_login", "Start at Windows login", "Reboot/log in and verify one resident GAIA instance starts without manual uvicorn/terminal commands."),
    ("clean_exit", "Clean resident shutdown", "Exit from the tray and verify Core, voice capture, event client and child workers terminate cleanly."),
    ("multi_monitor", "Multi-monitor Orb placement/persistence", "Move/configure the Orb on the target monitor, restart GAIA and confirm placement persists."),
    ("ollama", "Ollama and selected local LLM", "Confirm the configured Ollama endpoint/model responds to a bounded local inference."),
    ("gpu", "GPU observation/acceleration profile", "Record the detected GPU and selected CPU/AMD/NVIDIA profile without tuning hardware."),
    ("android_pairing", "Android companion pairing", "If Android is in scope, pair a physical device and verify revocable authenticated communication; otherwise SKIP."),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def external(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        return resolved
    raise ValueError("Los reportes físicos deben permanecer fuera del árbol del proyecto")


def redact(value: str) -> str:
    value = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)(?:LUMEN_SECRET|password|token|api[_ -]?key)\s*[:=]\s*[^\s,;]+", "[REDACTED]", value)
    return value


def evidence_summary(path: Path | None) -> str:
    if path is None:
        return ""
    evidence = external(path)
    if not evidence.is_file():
        raise ValueError("evidence-file no existe")
    data = evidence.read_bytes()
    return f"provided=true;bytes={len(data)};sha256={hashlib.sha256(data).hexdigest()}"


def blank_check(check_id: str, description: str, method: str) -> dict:
    return {
        "id": check_id,
        "description": description,
        "method": method,
        "status": "PENDING",
        "evidence": "",
        "timestamp": utc_now(),
        "operator_confirmed": False,
        "environment": {"os": platform.system(), "python": platform.python_version()},
        "limitations": "Physical result must be confirmed on the operator target machine.",
        "data_redacted": True,
        "notes": "",
    }


def new_report() -> dict:
    return {
        "report": REPORT_KIND,
        "product_version": PRODUCT_VERSION,
        "release": RELEASE,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "closed_at": None,
        "operator_confirmed": False,
        "sandbox_measurements": False,
        "checks": [blank_check(*check) for check in CHECKS],
        "history": [],
        "summary": {status: 0 for status in sorted(STATUSES)},
        "release_authorization": "NO_FINAL_RELEASE_AUTHORIZATION",
        "warning": "PASS requires explicit human confirmation and evidence. This ledger never promotes an RC by itself.",
    }


def update_summary(report: dict) -> None:
    summary = {status: 0 for status in sorted(STATUSES)}
    for item in report.get("checks", []):
        status = str(item.get("status", "PENDING"))
        summary[status] = summary.get(status, 0) + 1
    report["summary"] = summary
    report["operator_confirmed"] = all(bool(item.get("operator_confirmed")) for item in report.get("checks", []) if item.get("status") != "SKIP")
    unresolved = any(summary.get(status, 0) for status in ("FAIL", "PENDING", "BLOCKED", "NOT_MEASURED"))
    report["release_authorization"] = "NO_FINAL_RELEASE_AUTHORIZATION" if unresolved else "OPERATOR_REVIEW_REQUIRED"


def save_report(path: Path, report: dict) -> None:
    path = external(path)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def markdown(report: dict) -> str:
    lines = [
        f"# GAIA {report.get('release', RELEASE)} physical validation session",
        "",
        "> Operator ledger only. Sandbox tests, imports and source inspection do not establish physical PASS.",
        "",
        f"Product version: `{report.get('product_version', PRODUCT_VERSION)}`  ",
        f"Release: `{report.get('release', RELEASE)}`  ",
        f"Created UTC: `{report.get('created_at', '')}`  ",
        f"Updated UTC: `{report.get('updated_at', '')}`  ",
        f"Operator confirmed applicable checks: `{report.get('operator_confirmed', False)}`  ",
        f"Release authorization: **{report.get('release_authorization', 'NO_FINAL_RELEASE_AUTHORIZATION')}**",
        "",
        "| ID | Description | Method | Status | Evidence | Operator confirmed | Limitations | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in report.get("checks", []):
        def cell(value: object) -> str:
            return redact(str(value or "")).replace("|", "\\|").replace("\n", " ")
        lines.append("| " + " | ".join([
            f"`{cell(item.get('id'))}`", cell(item.get("description")), cell(item.get("method")),
            f"**{cell(item.get('status'))}**", cell(item.get("evidence")), cell(item.get("operator_confirmed")),
            cell(item.get("limitations")), cell(item.get("notes")),
        ]) + " |")
    lines += ["", "## Summary", "", "| Status | Count |", "|---|---:|"]
    for status in sorted(STATUSES):
        lines.append(f"| `{status}` | {int(report.get('summary', {}).get(status, 0))} |")
    lines += [
        "",
        "Keep this report outside the project/release ZIP. Attach only redacted evidence summaries; never copy secrets, private databases, raw conversations, signing keys or unrestricted audio into the release.",
        "",
        "Closing a session does not by itself promote the software to FINAL; release promotion still requires the automated software gate and operator review.",
        "",
    ]
    return "\n".join(lines)


def write_markdown(report_path: Path, report: dict) -> Path:
    md_path = external(report_path.with_suffix(".md"))
    md_path.write_text(markdown(report), encoding="utf-8")
    return md_path


def load_report(path: Path) -> tuple[Path, dict]:
    path = external(path)
    if not path.is_file():
        raise ValueError("report no existe")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"report inválido: {type(error).__name__}") from error
    if report.get("report") != REPORT_KIND:
        raise ValueError("report no corresponde al validador físico actual de GAIA")
    if not isinstance(report.get("checks"), list):
        raise ValueError("checks inválidos")
    return path, report


def _valid_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _markdown_counts(md_path: Path, release: str) -> dict[str, int]:
    if not md_path.is_file():
        raise ValueError("Markdown companion missing")
    text = md_path.read_text(encoding="utf-8")
    if f"Release: `{release}`" not in text:
        raise ValueError("Markdown release mismatch")
    counts: dict[str, int] = {}
    for status in sorted(STATUSES):
        match = re.search(rf"\| `{re.escape(status)}` \| (\d+) \|", text)
        if not match:
            raise ValueError(f"Markdown summary missing {status}")
        counts[status] = int(match.group(1))
    return counts


def _validation_errors(path: Path, report: dict) -> list[str]:
    errors: list[str] = []
    if report.get("product_version") != PRODUCT_VERSION:
        errors.append("VERSION_MISMATCH")
    if report.get("release") != RELEASE:
        errors.append("RELEASE_MISMATCH")
    checks = report.get("checks")
    if not isinstance(checks, list):
        return ["CHECKS_INVALID"]
    ids = [item.get("id") for item in checks if isinstance(item, dict)]
    required_ids = [item[0] for item in CHECKS]
    if len(ids) != len(set(ids)):
        errors.append("CHECK_IDS_NOT_UNIQUE")
    if set(ids) != set(required_ids) or len(ids) != len(required_ids):
        errors.append("CHECK_IDS_MISMATCH")
    calculated = {status: 0 for status in sorted(STATUSES)}
    for item in checks:
        if not isinstance(item, dict):
            errors.append("CHECK_NOT_OBJECT")
            continue
        status = item.get("status")
        if status not in STATUSES:
            errors.append(f"INVALID_STATUS:{status}")
        else:
            calculated[status] += 1
        if not _valid_timestamp(item.get("timestamp")):
            errors.append(f"INVALID_TIMESTAMP:{item.get('id')}")
        if status == "PASS":
            if not item.get("evidence"):
                errors.append(f"PASS_WITHOUT_EVIDENCE:{item.get('id')}")
            if item.get("operator_confirmed") is not True:
                errors.append(f"PASS_WITHOUT_CONFIRMATION:{item.get('id')}")
            if not item.get("method"):
                errors.append(f"PASS_WITHOUT_METHOD:{item.get('id')}")
    summary = report.get("summary")
    if not isinstance(summary, dict) or any(summary.get(status) != calculated[status] for status in sorted(STATUSES)):
        errors.append("REPORT_INCONSISTENT:SUMMARY")
    elif sum(int(summary.get(status, 0)) for status in sorted(STATUSES)) != len(checks):
        errors.append("REPORT_INCONSISTENT:TOTAL")
    expected_confirmed = all(item.get("operator_confirmed") is True for item in checks if item.get("status") != "SKIP")
    if report.get("operator_confirmed") is not expected_confirmed:
        errors.append("REPORT_INCONSISTENT:OPERATOR_CONFIRMATION")
    expected_auth = "NO_FINAL_RELEASE_AUTHORIZATION" if any(calculated.get(status, 0) for status in ("FAIL", "PENDING", "BLOCKED", "NOT_MEASURED")) else "OPERATOR_REVIEW_REQUIRED"
    if report.get("release_authorization") != expected_auth:
        errors.append("REPORT_INCONSISTENT:AUTHORIZATION")
    if report.get("closed_at") is not None and not _valid_timestamp(report.get("closed_at")):
        errors.append("INVALID_CLOSED_AT")
    history = report.get("history")
    if not isinstance(history, list):
        errors.append("HISTORY_INVALID")
    else:
        for entry in history:
            if not isinstance(entry, dict) or not _valid_timestamp(entry.get("timestamp")):
                errors.append("HISTORY_TIMESTAMP_INVALID")
    try:
        md_counts = _markdown_counts(path.with_suffix(".md"), str(report.get("release", "")))
        if summary != md_counts:
            errors.append("REPORT_INCONSISTENT:MARKDOWN")
    except (OSError, ValueError) as error:
        errors.append(f"MARKDOWN_INVALID:{error}")
    return errors


def cmd_new(args: argparse.Namespace) -> int:
    directory = external(args.output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = directory / f"physical_validation_GAIA_{PRODUCT_VERSION}_{stamp}.json"
    if json_path.exists():
        raise ValueError("la sesión timestamped ya existe; reintenta con otro segundo")
    report = new_report()
    update_summary(report)
    save_report(json_path, report)
    md_path = write_markdown(json_path, report)
    print(json.dumps({"status": "PENDING", "json": str(json_path), "markdown": str(md_path), "checks": len(report["checks"]), "operator_confirmed": False, "release": RELEASE}, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    path, report = load_report(args.report)
    print(json.dumps({"report": path.name, "release": report.get("release"), "summary": report.get("summary", {}), "release_authorization": report.get("release_authorization"), "closed_at": report.get("closed_at")}, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path, report = load_report(args.report)
    errors = _validation_errors(path, report)
    repairable = all(error.startswith("REPORT_INCONSISTENT:SUMMARY") or error.startswith("REPORT_INCONSISTENT:TOTAL") or error.startswith("REPORT_INCONSISTENT:MARKDOWN") for error in errors)
    if errors and args.repair_summary and repairable:
        if report.get("closed_at"):
            raise ValueError("closed report cannot be repaired")
        report.setdefault("history", []).append({"timestamp": utc_now(), "event": "repair_summary", "automatic": True, "previous_summary": dict(report.get("summary", {}))})
        update_summary(report)
        report["updated_at"] = utc_now()
        save_report(path, report)
        write_markdown(path, report)
        errors = _validation_errors(path, report)
        if errors:
            raise ValueError("REPORT_INCONSISTENT after repair: " + ",".join(errors))
        print(json.dumps({"status": "REPAIRED", "report": str(path), "history_entries": len(report["history"])}, ensure_ascii=False, sort_keys=True))
        return 0
    if errors:
        raise ValueError("REPORT_INCONSISTENT: " + ",".join(errors))
    print(json.dumps({"status": "PASS", "report": str(path), "release": report.get("release"), "checks": len(report["checks"]), "summary": report["summary"], "read_only": True}, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    path, report = load_report(args.report)
    if report.get("closed_at"):
        raise ValueError("sesión finalizada; no se sobrescribe evidencia cerrada")
    status = args.status.upper()
    if status not in STATUSES:
        raise ValueError(f"status inválido: {status}")
    if status == "PASS" and not args.operator_confirmed:
        raise ValueError("PASS requiere --operator-confirmed")
    if status == "PASS" and not args.evidence_file:
        raise ValueError("PASS requiere --evidence-file")
    check = next((item for item in report["checks"] if item.get("id") == args.check), None)
    if check is None:
        raise ValueError(f"check desconocido: {args.check}")
    report.setdefault("history", []).append({"timestamp": utc_now(), "check": check["id"], "previous": dict(check)})
    check.update({
        "status": status,
        "evidence": evidence_summary(args.evidence_file),
        "timestamp": utc_now(),
        "operator_confirmed": bool(args.operator_confirmed),
        "environment": {"os": platform.system(), "python": platform.python_version(), "operator_environment": redact(args.environment)},
        "limitations": redact(args.limitations),
        "data_redacted": True,
        "notes": redact(args.notes),
        "method": redact(args.method) if args.method else check.get("method", ""),
    })
    report["updated_at"] = utc_now()
    update_summary(report)
    save_report(path, report)
    md_path = write_markdown(path, report)
    print(json.dumps({"status": status, "json": str(path), "markdown": str(md_path), "history_entries": len(report["history"]), "release_authorization": report["release_authorization"]}, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    path, report = load_report(args.report)
    if report.get("closed_at"):
        raise ValueError("la sesión ya fue finalizada; no se sobrescribe evidencia cerrada")
    report["updated_at"] = utc_now()
    report["closed_at"] = utc_now()
    update_summary(report)
    save_report(path, report)
    md_path = write_markdown(path, report)
    print(json.dumps({"status": "CLOSED", "json": str(path), "markdown": str(md_path), "summary": report["summary"], "release_authorization": report["release_authorization"]}, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Guided GAIA {RELEASE} physical validation ledger")
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new", help="create a new PENDING session")
    new.add_argument("--output-dir", type=Path, required=True)
    new.set_defaults(handler=cmd_new)
    show = sub.add_parser("show", help="show summary without mutation")
    show.add_argument("--report", type=Path, required=True)
    show.set_defaults(handler=cmd_show)
    validate = sub.add_parser("validate", help="validate report integrity without mutation")
    validate.add_argument("--report", type=Path, required=True)
    validate.add_argument("--repair-summary", action="store_true")
    validate.set_defaults(handler=cmd_validate)
    record = sub.add_parser("record", help="record one human-confirmed observation")
    record.add_argument("--report", type=Path, required=True)
    record.add_argument("--check", required=True)
    record.add_argument("--status", required=True)
    record.add_argument("--evidence-file", type=Path)
    record.add_argument("--operator-confirmed", action="store_true")
    record.add_argument("--method", default="")
    record.add_argument("--environment", default="operator target")
    record.add_argument("--limitations", default="")
    record.add_argument("--notes", default="")
    record.set_defaults(handler=cmd_record)
    finalize = sub.add_parser("finalize", help="close a session without promoting a release")
    finalize.add_argument("--report", type=Path, required=True)
    finalize.set_defaults(handler=cmd_finalize)
    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
