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


def main() -> int:
    limits = _limits()
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    try:
        request = json.load(sys.stdin)
        instance = instance_from_dict(request["instance"])
        candidate, parameters, instrumentation = run_solver(
            instance.track, request["solver"], instance, request.get("parameters")
        )
        if candidate is None:
            verification = {"verified": False, "failure_reason": "solver returned no candidate"}
            candidate_dict = None
        else:
            # Round-trip through the tagged public contract before verification.
            candidate_dict = candidate.to_dict()
            candidate = candidate_from_dict(json.loads(json.dumps(candidate_dict)))
            if isinstance(instance, MLWEInstance):
                verification = verify_mlwe(instance, candidate)
            elif isinstance(instance, MSISInstance):
                verification = verify_msis(instance, candidate)
            elif isinstance(instance, BKZInstance):
                verification = verify_bkz(instance, candidate)
            else:  # pragma: no cover
                raise TypeError("unsupported instance type")
        response = {
            "candidate": candidate_dict,
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
    json.dump(response, sys.stdout, sort_keys=True, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
