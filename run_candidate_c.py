#!/usr/bin/env python3
"""Run Candidate C on all 9 instances and write results/candidate_c.jsonl."""

from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path

from mldsafail.benchmark.cost_model import OperationMeter
from mldsafail.models import Candidate, ChallengeInstance, VerificationResult
from mldsafail.solver.candidate_c import solve as candidate_c_solve
from mldsafail.trusted.generator import generate_instance
from mldsafail.trusted.verifier import verify

# Configuration
PROFILES = [
    ("small", 4),
    ("medium", 5),
    ("large", 5),
]
SEEDS = [1, 2, 3]
TIME_LIMIT_PER_INSTANCE = 600.0  # seconds

OUTPUT_PATH = Path(__file__).parent / "results" / "candidate_c.jsonl"


def run_one(profile: str, seed: int, k: int) -> dict:
    """Run Candidate C on one instance, return the JSON line dict."""
    # Generate instance
    inst = generate_instance(seed, profile)

    meter = OperationMeter()
    candidate = None
    guesses_tried = 0
    first_hit_index: int | None = None
    wall_start = time.time()
    tracemalloc.start()

    try:
        candidate, guesses_tried, first_hit_index = candidate_c_solve(
            inst, meter, k=k, timeout_sec=TIME_LIMIT_PER_INSTANCE
        )
    except TimeoutError:
        pass  # Will report failure
    except Exception as e:
        pass  # Will report failure
    finally:
        wall_seconds = time.time() - wall_start
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    # Verify
    if candidate is not None:
        result = verify(inst, candidate)
    else:
        result = VerificationResult(False, "solver returned no candidate (timeout or error)")

    snapshot = meter.snapshot()

    line = {
        "candidate_id": "C",
        "profile": profile,
        "seed": seed,
        "instance_id": inst.instance_id,
        "correct": result.valid,
        "failure_reason": None if result.valid else result.reason,
        "shared_cost": {
            "version": "2",
            "weighted_total": snapshot.weighted_total,
            "raw": {
                "additions": snapshot.additions,
                "multiplications": snapshot.multiplications,
                "modular_reductions": snapshot.modular_reductions,
                "basis_updates": snapshot.basis_updates,
                "memory_reads": snapshot.memory_reads,
                "memory_writes": snapshot.memory_writes,
            },
        },
        "wall_seconds": round(wall_seconds, 6) if wall_seconds else None,
        "peak_memory_bytes": peak_memory,
        "extraction_method": "guessing + reduced Gaussian solve",
        "candidate_diagnostics": {
            "k_guessed": k,
            "enumeration_space_size": (2 * inst.eta + 1) ** k,
            "guesses_tried": guesses_tried,
            "reduced_dimension": inst.dimension - k,
            "first_guess_hit_index": first_hit_index,
        },
        "notes": "",
    }
    return line


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for profile, k in PROFILES:
        for seed in SEEDS:
            print(f"[{profile} seed={seed} k={k}] Starting...", flush=True)
            line = run_one(profile, seed, k)
            results.append(line)
            status = "OK" if line["correct"] else "FAIL"
            print(
                f"[{profile} seed={seed} k={k}] {status} | "
                f"cost={line['shared_cost']['weighted_total']} | "
                f"time={line['wall_seconds']}s | "
                f"guesses={line['candidate_diagnostics']['guesses_tried']} | "
                f"hit_idx={line['candidate_diagnostics']['first_guess_hit_index']}",
                flush=True,
            )

    # Write JSONL
    with open(OUTPUT_PATH, "w") as f:
        for line in results:
            f.write(json.dumps(line, separators=(",", ":")) + "\n")

    print(f"\nWrote {len(results)} lines to {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
