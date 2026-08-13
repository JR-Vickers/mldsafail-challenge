"""Container entrypoint: run the trusted full suite and sign one bounded result."""

from __future__ import annotations

import json
import os
from pathlib import Path

from mldsafail.benchmark.runner import run_benchmark
from mldsafail.evaluator.envelope import sign_envelope


def main() -> int:
    required = {
        name: os.environ[name] for name in (
            "MLDSAFAIL_SOURCE_DIGEST", "MLDSAFAIL_BENCHMARK_VERSION",
            "MLDSAFAIL_EVALUATOR_FINGERPRINT", "MLDSAFAIL_HIDDEN_SUITE_VERSION",
            "MLDSAFAIL_WORKER_CLASS", "MLDSAFAIL_RESULT_KEY_PATH",
        )
    }
    failure_class = None
    try:
        _suites, aggregate, verified = run_benchmark(suite="full", solver_name="lazy")
        score = aggregate["score"] if verified else None
        diagnostics = {
            "total_wall_seconds": aggregate.get("total_wall_seconds"),
            "peak_memory_bytes": aggregate.get("peak_memory_bytes"),
            "solution_quality": aggregate.get("solution_quality"),
        }
        if not verified:
            failure_class = "verification_failed"
    except Exception as exception:
        verified, score, diagnostics, failure_class = False, None, {}, f"worker_error:{type(exception).__name__}"
    payload = {
        "source_digest": required["MLDSAFAIL_SOURCE_DIGEST"],
        "benchmark_version": required["MLDSAFAIL_BENCHMARK_VERSION"],
        "evaluator_fingerprint": required["MLDSAFAIL_EVALUATOR_FINGERPRINT"],
        "hidden_suite_version": required["MLDSAFAIL_HIDDEN_SUITE_VERSION"],
        "worker_class": required["MLDSAFAIL_WORKER_CLASS"],
        "verified": verified, "score": score, "diagnostics": diagnostics, "failure_class": failure_class,
    }
    key = Path(required["MLDSAFAIL_RESULT_KEY_PATH"]).read_bytes()
    print("MLDSAFAIL_RESULT=" + json.dumps(sign_envelope(payload, key), sort_keys=True, separators=(",", ":")))
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
