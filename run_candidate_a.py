#!/usr/bin/env python3
"""Harness: run Candidate A solver on all 9 instances and write results/candidate_a.jsonl."""

import json
import os
import sys
import time
import tracemalloc
from pathlib import Path

# Ensure src/ is on the path so `from src.mldsafail.solver.candidate_a import solve` works.
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from mldsafail.trusted.generator import generate_instance
from mldsafail.benchmark.cost_model import OperationMeter
from mldsafail.trusted.verifier import verify
from src.mldsafail.solver.candidate_a import solve

PROFILES = [
    ("small", 8, 97, 2, [1, 2, 3]),
    ("medium", 16, 257, 3, [1, 2, 3]),
    ("large", 24, 769, 4, [1, 2, 3]),
]

OUTPUT_PATH = REPO_ROOT / "results" / "candidate_a.jsonl"
TIMEOUT_SECONDS = 60


def run_one(profile_name: str, seed: int) -> dict:
    """Generate, solve, verify, and return the JSON-line dict for one instance."""
    t0 = time.perf_counter()
    tracemalloc.start()

    inst = None
    result = None
    snap = None
    failure_reason = None

    try:
        inst = generate_instance(seed, profile_name)
        cost = OperationMeter()
        candidate = solve(inst, cost)
        result = verify(inst, candidate)
        snap = cost.snapshot()
    except Exception as exc:
        result = None
        snap = None
        failure_reason = str(exc)
    finally:
        _, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        wall = time.perf_counter() - t0

    # Timeout check
    if wall > TIMEOUT_SECONDS:
        return {
            "candidate_id": "A",
            "profile": profile_name,
            "seed": seed,
            "instance_id": inst.instance_id if inst is not None else "",
            "correct": False,
            "failure_reason": "timeout",
            "shared_cost": None,
            "wall_seconds": wall,
            "peak_memory_bytes": peak_mem,
            "extraction_method": "direct Gaussian elimination with coefficient centering",
            "candidate_diagnostics": {
                "method": "Gaussian elimination with partial pivoting",
                "stages": ["augment", "forward_elim", "back_subst", "center"],
            },
            "notes": "",
        }

    if snap is None or result is None or not result.valid:
        return {
            "candidate_id": "A",
            "profile": profile_name,
            "seed": seed,
            "instance_id": inst.instance_id if inst is not None else "",
            "correct": False,
            "failure_reason": result.reason if (result is not None and result.reason) else (failure_reason or "unknown"),
            "shared_cost": None,
            "wall_seconds": wall,
            "peak_memory_bytes": peak_mem,
            "extraction_method": "direct Gaussian elimination with coefficient centering",
            "candidate_diagnostics": {
                "method": "Gaussian elimination with partial pivoting",
                "stages": ["augment", "forward_elim", "back_subst", "center"],
            },
            "notes": "",
        }

    return {
        "candidate_id": "A",
        "profile": profile_name,
        "seed": seed,
        "instance_id": inst.instance_id,
        "correct": result.valid,
        "failure_reason": None,
        "shared_cost": {
            "version": snap.version,
            "weighted_total": snap.weighted_total,
            "raw": {
                "additions": snap.additions,
                "multiplications": snap.multiplications,
                "modular_reductions": snap.modular_reductions,
                "basis_updates": snap.basis_updates,
                "memory_reads": snap.memory_reads,
                "memory_writes": snap.memory_writes,
            },
        },
        "wall_seconds": wall,
        "peak_memory_bytes": peak_mem,
        "extraction_method": "direct Gaussian elimination with coefficient centering",
        "candidate_diagnostics": {
            "method": "Gaussian elimination with partial pivoting",
            "stages": ["augment", "forward_elim", "back_subst", "center"],
        },
        "notes": "",
    }


def main():
    os.makedirs(REPO_ROOT / "results", exist_ok=True)
    lines = []

    for profile_name, dim, q, eta, seeds in PROFILES:
        for seed in seeds:
            print(f"Running {profile_name} seed={seed} ...", flush=True)
            line = run_one(profile_name, seed)
            lines.append(line)
            status = "OK" if line["correct"] else f"FAIL: {line['failure_reason']}"
            print(f"  -> {status}  wall={line['wall_seconds']:.4f}s  mem={line['peak_memory_bytes']}B", flush=True)

    with OUTPUT_PATH.open("w") as f:
        for line in lines:
            f.write(json.dumps(line, separators=(",", ":")) + "\n")

    print(f"\nWrote {len(lines)} lines to {OUTPUT_PATH}")
    correct = sum(1 for l in lines if l["correct"])
    print(f"Correct: {correct}/{len(lines)}")


if __name__ == "__main__":
    main()
