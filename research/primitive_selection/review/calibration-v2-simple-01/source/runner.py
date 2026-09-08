"""Versioned cohorts with immutable run identities and parent-controlled limits."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .constants import (DEVELOPMENT_SEEDS, ETAS, MEASURED_RUNS, MEMORY_LIMIT_BYTES,
                        PROFILES, SCHEMA_VERSION, STUDY_VERSION, WALL_LIMIT_SECONDS, WARMUP_RUNS)
from .embedding import derive_bkz
from .generator import generate_mlwe, generate_msis
from .models import canonical_json, digest
from .solvers import DEFAULT_PARAMETERS, SOLVERS
from .worker import classify_result

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
DEFAULT_RESULTS = PACKAGE / "results"
RESULT_SCHEMA_VERSION = "2"


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
    paths = list(PACKAGE.glob("*.py")) + list((PACKAGE / "schemas").glob("*.json"))
    paths += [PACKAGE / name for name in ("Dockerfile", "requirements.txt", "primitive-study", "rebuild-check.sh")]
    for path in sorted(paths):
        sha.update(path.relative_to(PACKAGE).as_posix().encode() + b"\0" + path.read_bytes())
    return sha.hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configuration() -> dict[str, Any]:
    # Include every default, including per-track overrides inside run_solver in the source digest.
    return json.loads(canonical_json({
        "study_version": STUDY_VERSION, "payload_schema_version": SCHEMA_VERSION,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "profiles": PROFILES, "etas": ETAS, "development_seeds": DEVELOPMENT_SEEDS,
        "portfolio": {track: list(solvers) for track, solvers in SOLVERS.items()},
        "solver_parameters": DEFAULT_PARAMETERS,
        "limits": {"wall_seconds": WALL_LIMIT_SECONDS, "memory_bytes": MEMORY_LIMIT_BYTES, "cpu_cores": 1},
        "timing_protocol": {"warmups": WARMUP_RUNS, "measured_repetitions": MEASURED_RUNS,
                            "aggregation": "median successful measured process CPU time",
                            "processes": "fresh subprocess for every warmup and measured repetition",
                            "case_order": "deterministic cohort/nonce-domain-separated shuffle"},
    }))


def dependency_provenance() -> dict[str, Any]:
    versions = {}
    for line in (PACKAGE / "requirements.txt").read_text().splitlines():
        if "==" not in line or line.lstrip().startswith("#"):
            continue
        name, pin = line.strip().split("==", 1)
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = "missing"
        versions[name] = {"required": pin, "installed": installed}
    return {"requirements_sha256": file_digest(PACKAGE / "requirements.txt"),
            "dockerfile_sha256": file_digest(PACKAGE / "Dockerfile"),
            "python": platform.python_version(), "packages": versions}


def _instance(case: Case):
    if case.track == "mlwe":
        return generate_mlwe(case.profile, case.seed, case.eta).public
    if case.track == "msis":
        return generate_msis(case.profile, case.seed, case.eta).public
    if case.track != "bkz" or case.source_track not in ("mlwe", "msis"):
        raise ValueError("invalid derived track")
    source = (generate_mlwe(case.profile, case.seed, case.eta).public if case.source_track == "mlwe"
              else generate_msis(case.profile, case.seed, case.eta).public)
    return derive_bkz(source)


def _invoke(instance, solver: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    request = {"instance": instance.to_dict(), "solver": solver, "parameters": parameters or {}}
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "research.primitive_selection.worker"], cwd=ROOT,
            input=canonical_json(request), capture_output=True, timeout=WALL_LIMIT_SECONDS, check=False,
            env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PYTHONHASHSEED": "0"},
        )
    except subprocess.TimeoutExpired as exc:
        return {"status": "timeout", "timeout": True, "memory_limit": False,
                "evaluator_wall_seconds": time.perf_counter() - started,
                "partial_stdout": (exc.stdout or b"").decode(errors="replace")[-2000:],
                "partial_stderr": (exc.stderr or b"").decode(errors="replace")[-2000:],
                "error": "wall-time limit exceeded"}
    wall = time.perf_counter() - started
    if completed.returncode:
        return {"status": "crash", "timeout": False, "memory_limit": False,
                "evaluator_wall_seconds": wall, "returncode": completed.returncode,
                "error": (f"worker terminated by signal {-completed.returncode}" if completed.returncode < 0
                          else completed.stderr.decode(errors="replace")[-2000:])}
    try:
        result = json.loads(completed.stdout)
        if not isinstance(result, dict):
            raise ValueError("response is not an object")
    except (ValueError, UnicodeDecodeError):
        return {"status": "crash", "timeout": False, "memory_limit": False,
                "evaluator_wall_seconds": wall, "error": "worker returned malformed JSON"}
    result.setdefault("timeout", False)
    result.setdefault("memory_limit", False)
    result["evaluator_wall_seconds"] = wall
    result["status"] = classify_result(result)
    return result


def _aggregate_repetitions(repetitions: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [r for r in repetitions if classify_result(r) == "success"]
    statuses = [classify_result(r) for r in repetitions]
    return {
        "verification_result": bool(repetitions) and len(successful) == len(repetitions),
        "status": statuses[0] if len(set(statuses)) == 1 else "mixed",
        "status_counts": {status: statuses.count(status) for status in sorted(set(statuses))},
        "failure_reason": next((r.get("error") or r.get("verification", {}).get("failure_reason")
                                or classify_result(r) for r in repetitions if classify_result(r) != "success"), None),
        "median_cpu_seconds": statistics.median(r["cpu_seconds"] for r in successful) if successful else None,
        "median_wall_seconds": statistics.median(r["evaluator_wall_seconds"] for r in successful) if successful else None,
        "peak_rss_bytes": max((r.get("peak_rss_bytes", 0) for r in repetitions), default=0),
        "timeout": "timeout" in statuses, "memory_limit": "memory_failure" in statuses,
        "answer_quality": successful[0]["verification"] if successful else {},
        "phase_cpu_seconds": {
            phase: statistics.median(r.get("phase_cpu_seconds", {}).get(phase, 0.0) for r in successful)
            for phase in ("reduction", "enumeration", "surrounding")
        } if successful else {},
        "diagnostic_counters": repetitions[0].get("diagnostic_counters", {}) if repetitions else {},
        "solver_parameters": next((r["solver_parameters"] for r in repetitions if "solver_parameters" in r), {}),
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
                    cases.extend(Case("bkz", profile, eta, seed, solver, source_track) for solver in SOLVERS["bkz"])
    random.Random(f"{STUDY_VERSION}:{cohort}:{nonce or 'committed'}:{smoke}").shuffle(cases)
    return cases


def manifest_path(output: Path) -> Path:
    return output.with_suffix(output.suffix + ".manifest.json")


def _write_json(path: Path, value: dict[str, Any], *, exclusive: bool = False) -> None:
    with path.open("x" if exclusive else "w") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def check_freeze(freeze: Path, nonce_record: Path, nonce: str) -> dict[str, Any]:
    frozen = json.loads(freeze.read_text())
    reviewer = json.loads(nonce_record.read_text())
    if frozen.get("source_digest") != _source_digest() or frozen.get("configuration") != configuration():
        raise ValueError("frozen source/configuration differs from running study")
    if frozen.get("dependency_provenance") != dependency_provenance():
        raise ValueError("frozen dependencies differ from running study")
    if not frozen.get("selection_criteria") or not frozen.get("ranking_rule"):
        raise ValueError("freeze must specify selection criteria and ranking rule")
    if frozen.get("expected_case_counts") != {"development": len(cases_for("development")),
                                               "validation": len(cases_for("validation", nonce))}:
        raise ValueError("freeze case counts differ from running study")
    if reviewer.get("nonce") != nonce or reviewer.get("freeze_sha256") != file_digest(freeze):
        raise ValueError("reviewer nonce does not reference this freeze")
    if not reviewer.get("reviewer_model") or not reviewer.get("reviewer_session"):
        raise ValueError("reviewer nonce must record model/session")
    if datetime.fromisoformat(reviewer["created_at"]) <= datetime.fromisoformat(frozen["created_at"]):
        raise ValueError("reviewer nonce must be created after freeze")
    revision = reviewer.get("freeze_commit", "")
    if len(revision) != 40:
        raise ValueError("reviewer nonce must reference committed freeze")
    # Outside git (container), compare the archived freeze digest and injected committed revision.
    if (ROOT / ".git").exists():
        relative = freeze.resolve().relative_to(ROOT).as_posix()
        committed = subprocess.run(["git", "show", f"{revision}:{relative}"], cwd=ROOT, capture_output=True, check=False)
        if committed.returncode or hashlib.sha256(committed.stdout).hexdigest() != file_digest(freeze):
            raise ValueError("freeze is not identical to referenced committed artifact")
    elif _git_revision()[0] != revision:
        raise ValueError("validation image must identify the freeze commit")
    return {"freeze_sha256": file_digest(freeze), "freeze": frozen, "reviewer_nonce": reviewer}


def run(cohort: str, nonce: str | None = None, output: Path | None = None,
        smoke: bool = False, repetitions: int = MEASURED_RUNS,
        freeze: Path | None = None, nonce_record: Path | None = None) -> Path:
    if repetitions != MEASURED_RUNS:
        raise ValueError("all cohorts require exactly three measured repetitions")
    freeze_info = {}
    if cohort == "validation":
        if smoke or freeze is None or nonce_record is None:
            raise ValueError("validation requires a committed freeze and reviewer nonce record")
        freeze_info = check_freeze(freeze, nonce_record, nonce or "")
    revision, dirty = _git_revision()
    if cohort == "validation" and dirty:
        raise ValueError("validation requires clean committed sources")
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex}"
    output = output or DEFAULT_RESULTS / "runs" / run_id / f"{'smoke' if smoke else cohort}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    if output.exists() or partial.exists() or manifest_path(output).exists():
        raise FileExistsError(f"refusing to overwrite run evidence: {output}")
    config, dependencies = configuration(), dependency_provenance()
    metadata = {
        "schema_version": RESULT_SCHEMA_VERSION, "study_version": STUDY_VERSION,
        "run_id": run_id, "git_revision": revision, "git_dirty": dirty,
        "container_image_digest": os.environ.get("PRIMITIVE_STUDY_IMAGE_DIGEST", "unavailable"),
        "host": {"platform": platform.platform(), "machine": platform.machine(),
                 "python": platform.python_version(), "cpu_count": os.cpu_count()},
        "limits": config["limits"], "timing_protocol": config["timing_protocol"],
        "source_digest": _source_digest(), "configuration_digest": digest(config),
        "dependency_digest": digest(dependencies),
        "cohort": "smoke" if smoke else cohort, "validation_nonce": nonce if cohort == "validation" else None,
    }
    all_cases = cases_for(cohort, nonce, smoke)
    manifest = {**metadata, "state": "partial", "created_at": datetime.now(UTC).isoformat(),
                "configuration": config, "dependency_provenance": dependencies,
                "expected_cases": [asdict(case) for case in all_cases], "expected_case_count": len(all_cases),
                "completed_case_count": 0, **freeze_info}
    _write_json(manifest_path(output), manifest, exclusive=True)
    try:
        with partial.open("x") as handle:
            for number, case in enumerate(all_cases, 1):
                instance = _instance(case)
                warmups = [_invoke(instance, case.solver) for _ in range(WARMUP_RUNS)]
                measured = [_invoke(instance, case.solver) for _ in range(repetitions)]
                aggregate = _aggregate_repetitions(measured)
                record = {**metadata, "recorded_at": datetime.now(UTC).isoformat(), "case_index": number,
                          **asdict(case), "instance_id": instance.instance_id,
                          "input_digest": digest(instance.to_dict()), "warmups": warmups,
                          "output_digest": digest([r.get("candidate") for r in measured]),
                          "warmup_output_digest": digest([r.get("candidate") for r in warmups]), **aggregate}
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                manifest["completed_case_count"] = number
                print(f"[{number}/{len(all_cases)}] {case.track}/{case.profile}/eta{case.eta}/{case.solver}: "
                      f"{aggregate['status']}", file=sys.stderr)
        partial.rename(output)
        manifest.update({"state": "complete", "completed_at": datetime.now(UTC).isoformat(),
                         "records_sha256": file_digest(output)})
    except BaseException as exc:
        manifest.update({"interrupted_at": datetime.now(UTC).isoformat(), "interruption": type(exc).__name__})
        raise
    finally:
        _write_json(manifest_path(output), manifest)
    return output
