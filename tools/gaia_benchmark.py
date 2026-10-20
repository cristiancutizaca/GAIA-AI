#!/usr/bin/env python3
"""Bounded RC6 benchmark; read-only with respect to host services and hardware."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))


def _sample():
    from resource_governor import HardwareSnapshot
    return HardwareSnapshot(8, 48000, "not_detected", False, True, "benchmark", 45.0, 10.0, 30.0, 256.0)


def _stats(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, int(len(ordered) * 0.95) - 1))
    return {
        "mean_ms": round(statistics.mean(values), 3),
        "median_ms": round(statistics.median(values), 3),
        "p95_ms": round(ordered[p95_index], 3),
        "max_ms": round(max(values), 3),
        "total_ms": round(sum(values), 3),
    }


def run(count: int, iterations: int) -> dict:
    count = min(2000, max(1, int(count)))
    iterations = min(200, max(1, int(iterations)))
    with tempfile.TemporaryDirectory(prefix="gaia_rc6_benchmark_") as temp:
        data_dir = Path(temp)
        os.environ.update({
            "LUMEN_DATA_DIR": str(data_dir),
            "GAIA_MEMORY_DB": str(data_dir / "memory.db"),
            "LUMEN_LLM_BACKEND": "mock",
            "LUMEN_SECRET": "test-rc6-benchmark-secret",
            "GAIA_SAFE_MODE": "true",
        })
        import advanced_memory
        import memory
        from resource_governor import ResourceGovernor

        memory.init_db()
        advanced_memory.init_db()
        context = memory.MemoryAccessContext(
            principal_id="benchmark-device", device_id="benchmark-device", session_id="benchmark-session",
            capabilities=frozenset({"memory_read", "memory_write"}), request_id="benchmark", source_channel="benchmark",
            is_master=False,
        )
        save_durations: list[float] = []
        for index in range(count):
            started = time.perf_counter()
            advanced_memory.save_item(
                memory_key=f"rc6.benchmark.{index}", kind="semantic", category="benchmark",
                content=f"bounded benchmark retrieval phrase {index}", source_type="USER_EXPLICIT",
                source_ref="benchmark", scope="device", device_id="benchmark-device", user_confirmed=True,
                access_context=context,
            )
            save_durations.append((time.perf_counter() - started) * 1000.0)

        retrieve_durations: list[float] = []
        result_count = 0
        for _ in range(iterations):
            started = time.perf_counter()
            result = advanced_memory.retrieve(
                "benchmark retrieval", scope="device", device_id="benchmark-device", limit=8,
                max_chars=2000, access_context=context,
            )
            retrieve_durations.append((time.perf_counter() - started) * 1000.0)
            result_count += len(result.get("items") or [])

        governor = ResourceGovernor("laptop_balanced", sample_provider=_sample)
        governor_durations: list[float] = []
        policies = []
        for _ in range(iterations):
            started = time.perf_counter()
            policies.append(governor.observe())
            governor_durations.append((time.perf_counter() - started) * 1000.0)
        gov_status = governor.status()
        return {
            "benchmark": "gaia_rc6_bounded",
            "status": "PASS",
            "environment": {
                "python": platform.python_version(),
                "os": platform.system(),
                "os_release": platform.release(),
                "architecture": platform.machine(),
                "virtualenv_active": sys.prefix != sys.base_prefix,
            },
            "fixture": {
                "memory_items": count,
                "retrieval_iterations": iterations,
                "temporary_sqlite": True,
            },
            "fixture_details": {
                "governor_iterations": iterations,
                "synthetic_content": True,
                "project_paths_in_evidence": False,
            },
            "read_only_host": True,
            "ollama_started": False,
            "model_downloaded": False,
            "hardware_mutated": False,
            "side_effects": {
                "read_only_host": True,
                "ollama_started": False,
                "model_downloaded": False,
                "hardware_mutated": False,
                "services_started": False,
            },
            "memory": {
                "save": _stats(save_durations),
                "retrieve": _stats(retrieve_durations),
                "retrieve_results_total": result_count,
            },
            "governor": {
                "iterations": iterations,
                "observe": _stats(governor_durations),
                "transitions": gov_status["transitions"],
                "policy_profile": policies[-1]["profile"],
                "defer_consolidation": bool(policies[-1]["defer_consolidation"]),
                "read_only": gov_status["read_only"],
            },
        }


def markdown(result: dict) -> str:
    fixture = result["fixture"]
    memory = result["memory"]
    governor = result["governor"]
    lines = [
        "# GAIA-AI RC6 bounded benchmark",
        "",
        "> Sandbox benchmark only. It uses temporary SQLite fixtures and never starts Ollama, downloads models, mutates hardware, or claims physical target performance.",
        "",
        f"Environment: Python `{result['environment']['python']}`, OS `{result['environment']['os']}`, architecture `{result['environment']['architecture']}`.",
        "",
        "| Measurement | Mean ms | Median ms | p95 ms | Max ms | Total ms |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, values in (("Memory save", memory["save"]), ("Memory retrieve", memory["retrieve"]), ("Governor observe", governor["observe"])):
        lines.append(f"| {label} | {values['mean_ms']} | {values['median_ms']} | {values['p95_ms']} | {values['max_ms']} | {values['total_ms']} |")
    lines += [
        "",
        "| Fixture / side effect | Value |",
        "|---|---:|",
        f"| Memory items | {fixture['memory_items']} |",
        f"| Retrieval iterations | {fixture['retrieval_iterations']} |",
        f"| Governor iterations | {governor['iterations']} |",
        f"| Retrieval results total | {memory['retrieve_results_total']} |",
        f"| Governor transitions | {governor['transitions']} |",
        f"| Governor profile | `{governor['policy_profile']}` |",
        f"| Read-only host | {result['side_effects']['read_only_host']} |",
        f"| Ollama started / model downloaded | {result['side_effects']['ollama_started']} / {result['side_effects']['model_downloaded']} |",
        f"| Hardware mutated / services started | {result['side_effects']['hardware_mutated']} / {result['side_effects']['services_started']} |",
        f"| Status | **{result['status']}** |",
        "",
        "A slower or faster result on another machine is not automatically a regression or improvement. Compare RC5 and RC6 only with the same environment and configuration. GPU/VRAM, Ollama/Qwen, Windows, Android, audio, LAN/TLS, battery, and thermal results remain PENDING / NOT MEASURED until physical validation.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded, read-only GAIA RC6 benchmark")
    parser.add_argument("--count", type=int, default=200, help="temporary memory items, bounded to 2000")
    parser.add_argument("--iterations", type=int, default=30, help="retrieval/policy iterations, bounded to 200")
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.count, args.iterations)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_out.write_text(markdown(result), encoding="utf-8")
    print(json.dumps({"status": result["status"], "json": str(args.json_out), "markdown": str(args.markdown_out), "read_only_host": True, "project_paths_in_evidence": False}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
