"""Untrusted solver subprocess protocol. No hidden data or signing keys enter."""

from __future__ import annotations

import json
import sys
import time

from mldsafail.benchmark.cost_model import OperationMeter
from mldsafail.models import ChallengeInstance
from mldsafail.solver.lazy import solve as lazy_solve
from mldsafail.solver.candidate_b import solve as lattice_solve

SOLVERS = {
    "lazy": lazy_solve,
    "candidate_b": lattice_solve,
    "lattice": lattice_solve,
}

def _select_solver(solver_name: str):
    """Return the solver function for the given name, defaulting to lazy."""
    return SOLVERS.get(solver_name, lazy_solve)


def _instance(item: dict) -> ChallengeInstance:
    return ChallengeInstance(
        instance_id=str(item["instance_id"]), seed=0, profile=str(item["profile"]),
        dimension=int(item["dimension"]), modulus=int(item["modulus"]), eta=int(item["eta"]),
        matrix=tuple(tuple(int(value) for value in row) for row in item["matrix"]),
        target=tuple(int(value) for value in item["target"]),
    )


def main() -> int:
    request = json.load(sys.stdin)
    solver_name = request.get("solver", "lazy")
    solver = _select_solver(solver_name)
    results = []
    for item in request["instances"]:
        instance = _instance(item); meter = OperationMeter(); started = time.perf_counter()
        candidate = solver(instance, meter)
        results.append({
            "instance_id": item["instance_id"], "coefficients": list(candidate.coefficients),
            "cost": meter.snapshot().to_dict(), "wall_seconds": time.perf_counter() - started,
        })
    sys.stdout.write(json.dumps({"results": results, "solver": solver_name}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
