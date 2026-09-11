"""Trusted cooperative timing adapter. This image contains no evaluator state."""
from __future__ import annotations

import importlib.util
import json
import os
import resource
import sys
import time

from .constants import MEMORY_LIMIT_BYTES, MAX_SERIALIZED_BYTES
from .models import instance_from_dict
from .solvers import run_solver
from .verify import verify_candidate


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    cpu = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpu})
    return {"rlimits_applied": ["RLIMIT_AS"], "cpu_affinity": cpu}


def main():
    applied = limits()
    # As in the frozen worker, adapter imports precede the clock. Contestant
    # loading and lazy mathematical imports are part of complete solver CPU.
    wall, cpu = time.perf_counter(), time.process_time()
    response = {}
    try:
        request = json.loads(sys.stdin.buffer.read(MAX_SERIALIZED_BYTES + 1))
        instance = instance_from_dict(request["instance"])
        started = time.process_time()
        if request["solver"] == "contestant":
            spec = importlib.util.spec_from_file_location("contestant", "/solver/solver.py")
            module = importlib.util.module_from_spec(spec)
            sys.path.insert(0, "/solver")
            spec.loader.exec_module(module)
            candidate = module.solve(json.loads(json.dumps(instance.to_dict())))
            params, phases, counters = {}, {}, {}
        else:
            candidate, params, instrumentation = run_solver(request["solver"], instance)
            candidate = None if candidate is None else candidate.to_dict()
            phases, counters = instrumentation.phases, instrumentation.counters
        solver_cpu = time.process_time() - started
        started = time.process_time()
        try:
            candidate = json.loads(json.dumps(candidate, allow_nan=False))
        except (TypeError, ValueError, OverflowError):
            candidate = {"invalid_unserializable_candidate": True}
        verification = verify_candidate(instance, candidate)
        response = {"candidate": candidate, "verification": verification,
                    "solver_cpu_seconds": solver_cpu,
                    "verification_cpu_seconds": time.process_time() - started,
                    "solver_parameters": params, "phase_cpu_seconds": phases,
                    "diagnostic_counters": counters}
    except MemoryError:
        response = {"error": "memory limit exceeded", "memory_limit": True}
    except Exception as exc:
        response = {"error": f"{type(exc).__name__}: {str(exc)[:2000]}"}
    response.update(limits=applied, wall_seconds=time.perf_counter() - wall,
                    cpu_seconds=time.process_time() - cpu,
                    peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    # Final serialization is outside the clock. The parent bounds the stream.
    sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
