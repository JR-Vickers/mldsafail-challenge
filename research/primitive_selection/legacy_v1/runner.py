"""Reproducible cohort runner with parent-controlled subprocess limits."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .constants import (
    DEVELOPMENT_SEEDS,
    ETAS,
    MEASURED_RUNS,
    MEMORY_LIMIT_BYTES,
    PROFILES,
    SCHEMA_VERSION,
    STUDY_VERSION,
    WALL_LIMIT_SECONDS,
    WARMUP_RUNS,
)
from .embedding import derive_bkz
from .generator import generate_mlwe, generate_msis
from .models import canonical_json, digest
from .solvers import SOLVERS

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS = ROOT / "research" / "primitive_selection" / "results"


@dataclass(frozen=True)
class Case:
    track: str
    profile: str
    eta: int
    seed: int
    solver: str
    source_track: str | None = None


def validation_seeds(nonce: str, profile: str) -> tuple[int, ...]:
    if not nonce or len(nonce) < 16:
        raise ValueError("reviewer nonce must contain at least 16 characters")
    values = []
    counter = 0
    while len(values) < 20:
        material = f"{STUDY_VERSION}\0validation\0{profile}\0{nonce}\0{counter}".encode()
        value = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
        if value not in values:
            values.append(value)
        counter += 1
    return tuple(values)


def _git_revision() -> tuple[str, bool]:
    injected = os.environ.get("PRIMITIVE_STUDY_GIT_REVISION")
    if injected:
        return injected, os.environ.get("PRIMITIVE_STUDY_GIT_DIRTY", "false").lower() == "true"
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                              capture_output=True, check=False).stdout.strip() or "unknown"
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                                text=True, capture_output=True, check=False).stdout.strip())
    return revision, dirty


def _source_digest() -> str:
    sha = hashlib.sha256()
    for path in sorted((ROOT / "research" / "primitive_selection").glob("*.py")):
        sha.update(path.name.encode() + b"\0" + path.read_bytes())
    return sha.hexdigest()


def _instance(case: Case):
    if case.track == "mlwe":
        return generate_mlwe(case.profile, case.seed, case.eta).public
    if case.track == "msis":
        return generate_msis(case.profile, case.seed, case.eta).public
    source = (generate_mlwe(case.profile, case.seed, case.eta).public if case.source_track == "mlwe"
              else generate_msis(case.profile, case.seed, case.eta).public)
    return derive_bkz(source)


def _invoke(instance, solver: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    request = {"instance": instance.to_dict(), "solver": solver, "parameters": parameters or {}}
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "research.primitive_selection.worker"],
            cwd=ROOT,
            input=canonical_json(request),
            capture_output=True,
            timeout=WALL_LIMIT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"timeout": True, "memory_limit": False, "wall_seconds": time.perf_counter() - started,
                "error": "wall-time limit exceeded"}
    wall = time.perf_counter() - started
    if completed.returncode < 0:
        memory = completed.returncode in (-9, -11)
        return {"timeout": False, "memory_limit": memory, "wall_seconds": wall,
                "error": f"worker terminated by signal {-completed.returncode}"}
    if completed.returncode:
        return {"timeout": False, "memory_limit": False, "wall_seconds": wall,
                "error": completed.stderr.decode(errors="replace")[-2000:]}
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"timeout": False, "memory_limit": False, "wall_seconds": wall,
                "error": "worker returned malformed JSON"}
    result.setdefault("timeout", False)
    result.setdefault("memory_limit", False)
    result["evaluator_wall_seconds"] = wall
    return result


def _aggregate_repetitions(repetitions: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [r for r in repetitions if "cpu_seconds" in r]
    verified = [r for r in successful if r.get("verification", {}).get("verified")]
    median_cpu = statistics.median(r["cpu_seconds"] for r in successful) if successful else None
    median_wall = statistics.median(r["evaluator_wall_seconds"] for r in successful) if successful else None
    return {
        "verification_result": len(verified) == len(repetitions),
        "failure_reason": next((r.get("error") or r.get("verification", {}).get("failure_reason")
                                for r in repetitions if r.get("error") or not r.get("verification", {}).get("verified")), None),
        "median_cpu_seconds": median_cpu,
        "median_wall_seconds": median_wall,
        "peak_rss_bytes": max((r.get("peak_rss_bytes", 0) for r in successful), default=0),
        "timeout": any(r.get("timeout", False) for r in repetitions),
        "memory_limit": any(r.get("memory_limit", False) for r in repetitions),
        "answer_quality": verified[0].get("verification", {}) if verified else {},
        "phase_cpu_seconds": {
            phase: statistics.median(r.get("phase_cpu_seconds", {}).get(phase, 0.0) for r in successful)
            for phase in ("reduction", "enumeration", "surrounding")
        } if successful else {},
        "diagnostic_counters": successful[0].get("diagnostic_counters", {}) if successful else {},
        "solver_parameters": successful[0].get("solver_parameters", {}) if successful else {},
        "repetitions": repetitions,
    }


def cases_for(cohort: str, nonce: str | None = None, smoke: bool = False) -> list[Case]:
    if smoke:
        profiles, etas = ("small",), (1,)
        seed_map = {"small": (0,)}
    elif cohort == "development":
        profiles, etas = tuple(PROFILES), ETAS
        seed_map = {profile: DEVELOPMENT_SEEDS for profile in profiles}
    elif cohort == "validation":
        profiles, etas = tuple(PROFILES), ETAS
        seed_map = {profile: validation_seeds(nonce or "", profile) for profile in profiles}
    else:
        raise ValueError("cohort must be development or validation")
    cases = []
    for profile in profiles:
        for eta in etas:
            for seed in seed_map[profile]:
                for track in ("mlwe", "msis"):
                    cases.extend(Case(track, profile, eta, seed, solver) for solver in SOLVERS[track])
                for source_track in ("mlwe", "msis"):
                    cases.extend(Case("bkz", profile, eta, seed, solver, source_track)
                                 for solver in SOLVERS["bkz"])
    order_rng = random.Random(f"{STUDY_VERSION}:{cohort}:{nonce or 'committed'}:{smoke}")
    order_rng.shuffle(cases)
    return cases


def run(cohort: str, nonce: str | None = None, output: Path | None = None,
        smoke: bool = False, repetitions: int = MEASURED_RUNS) -> Path:
    revision, dirty = _git_revision()
    source_sha = _source_digest()
    output = output or DEFAULT_RESULTS / ("smoke.jsonl" if smoke else f"{cohort}.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "study_version": STUDY_VERSION,
        "git_revision": revision,
        "git_dirty": dirty,
        "container_image_digest": os.environ.get("PRIMITIVE_STUDY_IMAGE_DIGEST", "unavailable"),
        "host": {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
                 "cpu_count": os.cpu_count()},
        "limits": {"wall_seconds": WALL_LIMIT_SECONDS, "memory_bytes": MEMORY_LIMIT_BYTES, "cpu_cores": 1},
        "timing_protocol": {"warmups": WARMUP_RUNS, "measured_repetitions": repetitions,
                            "aggregation": "median process CPU time"},
        "source_digest": source_sha,
    }
    records = []
    all_cases = cases_for(cohort, nonce, smoke)
    for number, case in enumerate(all_cases, 1):
        instance = _instance(case)
        for _ in range(WARMUP_RUNS):
            _invoke(instance, case.solver)
        measured = [_invoke(instance, case.solver) for _ in range(repetitions)]
        aggregate = _aggregate_repetitions(measured)
        record = dict(metadata)
        record.update({
            "recorded_at": datetime.now(UTC).isoformat(), "cohort": "smoke" if smoke else cohort,
            "validation_nonce": nonce if cohort == "validation" else None,
            "track": case.track, "source_track": case.source_track, "profile": case.profile,
            "eta": case.eta, "seed": case.seed, "solver": case.solver,
            "instance_id": instance.instance_id, "input_digest": digest(instance.to_dict()),
            "output_digest": digest([r.get("candidate") for r in measured]),
            **aggregate,
        })
        records.append(record)
        print(f"[{number}/{len(all_cases)}] {case.track}/{case.profile}/eta{case.eta}/{case.solver}: "
              f"{'ok' if aggregate['verification_result'] else aggregate['failure_reason']}", file=sys.stderr)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in records))
    temporary.replace(output)
    return output
