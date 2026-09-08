"""Single-case subprocess boundary for solver execution and verification."""

from __future__ import annotations

import json
import os
import resource
import sys
import time
import traceback

from .constants import MEMORY_LIMIT_BYTES
from .models import BKZInstance, MLWEInstance, MSISInstance, candidate_from_dict, instance_from_dict
from .solvers import run_solver
from .verify import verify_bkz, verify_mlwe, verify_msis


def _limits() -> dict[str, object]:
    applied = []
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
        applied.append("RLIMIT_AS")
    except (ValueError, OSError):
        pass
    affinity = None
    if hasattr(os, "sched_setaffinity"):
        available = sorted(os.sched_getaffinity(0))
        if available:
            affinity = available[0]
            os.sched_setaffinity(0, {affinity})
    return {"rlimits_applied": applied, "cpu_affinity": affinity}


def _peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def classify_result(result: dict) -> str:
    """Classify evidence; a killed process alone does not establish an OOM."""
    if result.get("timeout"):
        return "timeout"
    if result.get("memory_limit") or result.get("peak_rss_bytes", 0) > MEMORY_LIMIT_BYTES:
        return "memory_failure"
    if result.get("error"):
        return "crash"
    if result.get("verification", {}).get("verified"):
        return "success"
    counters = result.get("diagnostic_counters", {})
    if result.get("candidate") is None and any(
        key.endswith("cap_exceeded") or key == "search_space_skipped" for key in counters
    ):
        return "applicability_cap"
    return "invalid_answer" if result.get("candidate") is not None else "no_candidate"


def verify_candidate(instance, candidate_dict):
    """Independent contract decoding and verifier dispatch, also used by the auditor."""
    if candidate_dict is None:
        return {"verified": False, "failure_reason": "solver returned no candidate"}
    try:
        candidate = candidate_from_dict(candidate_dict)
        if isinstance(instance, MLWEInstance):
            return verify_mlwe(instance, candidate)
        if isinstance(instance, MSISInstance):
            return verify_msis(instance, candidate)
        if isinstance(instance, BKZInstance):
            return verify_bkz(instance, candidate)
        raise ValueError("unsupported instance type")
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        return {"verified": False, "failure_reason": f"malformed candidate: {exc}"}


def main() -> int:
    limits = _limits()
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    try:
        request = json.load(sys.stdin)
        instance = instance_from_dict(request["instance"])
        solver_started = time.process_time()
        candidate, parameters, instrumentation = run_solver(
            instance.track, request["solver"], instance, request.get("parameters")
        )
        solver_cpu = time.process_time() - solver_started
        candidate_dict = candidate.to_dict() if candidate is not None else None
        verify_started = time.process_time()
        verification = verify_candidate(instance, json.loads(json.dumps(candidate_dict)))
        verification_cpu = time.process_time() - verify_started
        response = {
            "candidate": candidate_dict,
            "solver_cpu_seconds": solver_cpu,
            "verification_cpu_seconds": verification_cpu,
            "verification": verification,
            "solver_parameters": parameters,
            "phase_cpu_seconds": instrumentation.phases,
            "diagnostic_counters": instrumentation.counters,
            "limits": limits,
            "wall_seconds": time.perf_counter() - started_wall,
            "cpu_seconds": time.process_time() - started_cpu,
            "peak_rss_bytes": _peak_rss_bytes(),
        }
    except MemoryError:
        response = {"error": "memory limit exceeded", "memory_limit": True,
                    "wall_seconds": time.perf_counter() - started_wall,
                    "cpu_seconds": time.process_time() - started_cpu,
                    "peak_rss_bytes": _peak_rss_bytes(), "limits": limits}
    except Exception as exc:  # worker failures are data, not runner crashes
        response = {"error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(limit=8),
                    "wall_seconds": time.perf_counter() - started_wall,
                    "cpu_seconds": time.process_time() - started_cpu,
                    "peak_rss_bytes": _peak_rss_bytes(), "limits": limits}
    response["status"] = classify_result(response)
    json.dump(response, sys.stdout, sort_keys=True, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
