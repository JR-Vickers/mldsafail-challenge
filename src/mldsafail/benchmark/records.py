"""Append-only experiment storage and reproducibility metadata."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


SCHEMA_VERSION = "1"
DEFAULT_RECORDS_PATH = Path(__file__).resolve().parents[3] / "results" / "experiments.jsonl"


class RecordValidationError(ValueError):
    """An experiment record does not match the supported JSONL schema."""


def validate_record(
    record: dict[str, Any], *, expected_benchmark_version: str | None = None
) -> None:
    """Validate the stable envelope while allowing metrics to evolve inside it."""

    required_types: dict[str, type] = {
        "schema_version": str,
        "benchmark_version": str,
        "experiment_id": str,
        "timestamp": str,
        "agent": str,
        "model": str,
        "hypothesis": str,
        "tags": list,
        "notes": str,
        "correct": bool,
        "aggregate": dict,
        "profiles": dict,
        "suites": dict,
        "environment": dict,
        "integrity": dict,
    }
    if not isinstance(record, dict):
        raise RecordValidationError("record is not an object")
    for field, expected_type in required_types.items():
        if field not in record:
            raise RecordValidationError(f"record is missing {field!r}")
        if not isinstance(record[field], expected_type):
            raise RecordValidationError(f"record field {field!r} has the wrong type")
    if record["schema_version"] != SCHEMA_VERSION:
        raise RecordValidationError(
            f"unsupported schema version {record['schema_version']!r}; expected {SCHEMA_VERSION!r}"
        )
    if not record["benchmark_version"]:
        raise RecordValidationError("benchmark version must not be empty")
    if expected_benchmark_version is not None and record["benchmark_version"] != expected_benchmark_version:
        raise RecordValidationError(
            f"benchmark version {record['benchmark_version']!r} does not match "
            f"{expected_benchmark_version!r}"
        )
    if not all(isinstance(tag, str) and tag for tag in record["tags"]):
        raise RecordValidationError("tags must contain non-empty strings")


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *args], check=True, capture_output=True, text=True,
            cwd=Path(__file__).resolve().parents[3],
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def reproducibility_metadata(command: list[str] | None = None) -> dict[str, Any]:
    lock = Path(__file__).resolve().parents[3] / "uv.lock"
    lock_hash = hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else None
    status = _git("status", "--porcelain")
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(status),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "dependency_lock_sha256": lock_hash,
        "os": platform.platform(),
        "architecture": platform.machine(),
        "command": command if command is not None else sys.argv,
    }


def new_experiment_record(
    *,
    benchmark_version: str,
    suites: dict[str, Any],
    aggregate: dict[str, Any],
    correct: bool,
    profiles: dict[str, Any] | None = None,
    agent: str = "unknown",
    model: str = "unknown",
    hypothesis: str = "baseline benchmark run",
    tags: list[str] | None = None,
    notes: str = "",
    parent_experiment: str | None = None,
    command: list[str] | None = None,
    integrity: dict[str, Any] | None = None,
    failure_reason: str | None = None,
    solver: str = "balanced",
) -> dict[str, Any]:
    now = datetime.now().astimezone()
    record = {
        "schema_version": SCHEMA_VERSION,
        "benchmark_version": benchmark_version,
        "experiment_id": f"{now:%Y%m%dT%H%M%S}-{uuid4().hex[:8]}",
        "timestamp": now.isoformat(),
        "agent": agent,
        "model": model,
        "solver": solver,
        "hypothesis": hypothesis,
        "tags": tags or ["baseline"],
        "notes": notes,
        "parent_experiment": parent_experiment,
        "correct": correct,
        "aggregate": aggregate,
        "profiles": profiles or {},
        "suites": suites,
        "environment": reproducibility_metadata(command),
        "integrity": integrity or {
            "trusted_fingerprint": None,
            "baseline_fingerprint": None,
            "matches_baseline": None,
        },
        "failure_reason": failure_reason,
    }
    validate_record(record)
    return record


def append_record(record: dict[str, Any], path: Path = DEFAULT_RECORDS_PATH) -> None:
    """Append one complete compact JSON object using a single OS write."""

    validate_record(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        written = os.write(descriptor, payload)
        if written != len(payload):
            raise OSError("partial experiment-record write")
    finally:
        os.close(descriptor)


def read_records(
    path: Path = DEFAULT_RECORDS_PATH,
    *,
    strict: bool = False,
    expected_benchmark_version: str | None = None,
) -> list[dict[str, Any]]:
    """Read valid records; tolerate interrupted/corrupt lines unless strict."""

    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            validate_record(value, expected_benchmark_version=expected_benchmark_version)
            records.append(value)
        except (json.JSONDecodeError, RecordValidationError):
            if strict:
                raise RecordValidationError(f"invalid JSONL record at line {number}") from None
    return records
