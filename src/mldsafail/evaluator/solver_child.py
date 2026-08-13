"""Untrusted solver subprocess protocol. No hidden data or signing keys enter."""

from __future__ import annotations

import json
import sys
import time

from mldsafail.benchmark.cost_model import OperationMeter
from mldsafail.models import ChallengeInstance
from mldsafail.solver.lazy import solve


def _instance(item: dict) -> ChallengeInstance:
    return ChallengeInstance(
        instance_id=str(item["instance_id"]), seed=0, profile=str(item["profile"]),
        dimension=int(item["dimension"]), modulus=int(item["modulus"]), eta=int(item["eta"]),
        matrix=tuple(tuple(int(value) for value in row) for row in item["matrix"]),
        target=tuple(int(value) for value in item["target"]),
    )


def main() -> int:
    request = json.load(sys.stdin)
    results = []
    for item in request["instances"]:
        instance = _instance(item); meter = OperationMeter(); started = time.perf_counter()
        candidate = solve(instance, meter)
        results.append({
            "instance_id": item["instance_id"], "coefficients": list(candidate.coefficients),
            "cost": meter.snapshot().to_dict(), "wall_seconds": time.perf_counter() - started,
        })
    sys.stdout.write(json.dumps({"results": results}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
