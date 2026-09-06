"""Integrity checks for committed raw study records."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from .constants import DEVELOPMENT_SEEDS, MEASURED_RUNS, SCHEMA_VERSION, STUDY_VERSION
from .models import digest

REQUIRED_FIELDS = {
    "schema_version", "study_version", "git_revision", "container_image_digest", "host",
    "track", "profile", "seed", "eta", "solver", "solver_parameters", "verification_result",
    "failure_reason", "median_wall_seconds", "median_cpu_seconds", "peak_rss_bytes",
    "answer_quality", "timeout", "memory_limit", "diagnostic_counters", "input_digest",
    "output_digest", "source_digest", "repetitions",
}


def audit(paths: list[Path]) -> dict[str, int]:
    counts = {"records": 0, "verified": 0, "timeouts": 0, "memory_limits": 0}
    for path in paths:
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            record = json.loads(line)
            missing = REQUIRED_FIELDS - record.keys()
            if missing:
                raise ValueError(f"{path}:{line_number}: missing fields {sorted(missing)}")
            if record["schema_version"] != SCHEMA_VERSION or record["study_version"] != STUDY_VERSION:
                raise ValueError(f"{path}:{line_number}: unsupported version")
            repetitions = record["repetitions"]
            if len(repetitions) != MEASURED_RUNS:
                raise ValueError(f"{path}:{line_number}: expected {MEASURED_RUNS} repetitions")
            cpu_values = [r["cpu_seconds"] for r in repetitions if "cpu_seconds" in r]
            expected_cpu = statistics.median(cpu_values) if cpu_values else None
            if record["median_cpu_seconds"] != expected_cpu:
                raise ValueError(f"{path}:{line_number}: median CPU mismatch")
            if record["output_digest"] != digest([r.get("candidate") for r in repetitions]):
                raise ValueError(f"{path}:{line_number}: output digest mismatch")
            if record["cohort"] == "development" and record["seed"] not in DEVELOPMENT_SEEDS:
                raise ValueError(f"{path}:{line_number}: uncommitted development seed")
            if record["cohort"] == "validation" and not record.get("validation_nonce"):
                raise ValueError(f"{path}:{line_number}: validation nonce missing")
            counts["records"] += 1
            counts["verified"] += bool(record["verification_result"])
            counts["timeouts"] += bool(record["timeout"])
            counts["memory_limits"] += bool(record["memory_limit"])
    if not counts["records"]:
        raise ValueError("no result records found")
    return counts
