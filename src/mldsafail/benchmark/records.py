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
) -> dict[str, Any]:
    now = datetime.now().astimezone()
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_version": benchmark_version,
        "experiment_id": f"{now:%Y%m%dT%H%M%S}-{uuid4().hex[:8]}",
        "timestamp": now.isoformat(),
        "agent": agent,
        "model": model,
        "hypothesis": hypothesis,
        "tags": tags or ["baseline"],
        "notes": notes,
        "parent_experiment": parent_experiment,
        "correct": correct,
        "aggregate": aggregate,
        "profiles": profiles or {},
        "suites": suites,
        "environment": reproducibility_metadata(command),
    }


def append_record(record: dict[str, Any], path: Path = DEFAULT_RECORDS_PATH) -> None:
    """Append one complete compact JSON object using a single OS write."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        written = os.write(descriptor, payload)
        if written != len(payload):
            raise OSError("partial experiment-record write")
    finally:
        os.close(descriptor)


def read_records(path: Path = DEFAULT_RECORDS_PATH, *, strict: bool = False) -> list[dict[str, Any]]:
    """Read valid records; tolerate interrupted/corrupt lines unless strict."""

    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("record is not an object")
            records.append(value)
        except (json.JSONDecodeError, ValueError):
            if strict:
                raise ValueError(f"invalid JSONL record at line {number}") from None
    return records
