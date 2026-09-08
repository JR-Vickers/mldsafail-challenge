"""Reconstruct cases and independently verify every stored answer and aggregate."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from . import runner
from .models import digest
from .worker import classify_result, verify_candidate

CASE_FIELDS = ("track", "profile", "eta", "seed", "solver", "source_track")
PROVENANCE_FIELDS = ("schema_version", "study_version", "git_revision", "git_dirty", "container_image_digest",
                     "host", "source_digest", "limits", "timing_protocol", "cohort", "validation_nonce")
V2_FIELDS = ("run_id", "configuration_digest", "dependency_digest")


def _key(value):
    return tuple(value.get(field) for field in CASE_FIELDS)


def _equal(actual, expected, description):
    if actual != expected:
        raise ValueError(f"{description} mismatch")


def _metrics(repetition):
    for field in ("cpu_seconds", "wall_seconds", "evaluator_wall_seconds", "solver_cpu_seconds",
                  "verification_cpu_seconds", "peak_rss_bytes"):
        if field in repetition:
            value = repetition[field]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid {field}")
    if type(repetition.get("peak_rss_bytes", 0)) is not int:
        raise ValueError("invalid peak_rss_bytes")
    for value in repetition.get("phase_cpu_seconds", {}).values():
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("invalid phase timing")
    if sum(repetition.get("phase_cpu_seconds", {}).values()) > repetition.get("cpu_seconds", 0) + 1e-6:
        raise ValueError("phase CPU exceeds complete measured CPU")


def _legacy_modules():
    from .legacy_v1 import models, runner as old_runner, verify
    return old_runner, models, verify


def _legacy_verify(instance, candidate, models, verify):
    if candidate is None:
        return {"verified": False, "failure_reason": "solver returned no candidate"}
    parsed = models.candidate_from_dict(candidate)
    return {"mlwe": verify.verify_mlwe, "msis": verify.verify_msis, "bkz": verify.verify_bkz}[instance.track](instance, parsed)


def _check_grid(records, expected):
    actual_keys = [_key(record) for record in records]
    duplicates = [key for key, count in Counter(actual_keys).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate cases: {duplicates[:3]}")
    expected_keys = {_key(asdict(case)) for case in expected}
    if set(actual_keys) != expected_keys:
        raise ValueError(f"case grid mismatch: {len(expected_keys - set(actual_keys))} missing, "
                         f"{len(set(actual_keys) - expected_keys)} unexpected (solver/profile/seed/eta/source)")


def _audit_file(path: Path):
    if path.name.endswith(".partial"):
        raise ValueError("partial runs are excluded from final analysis")
    records = [json.loads(line) for line in path.read_text().splitlines() if line]
    if not records:
        raise ValueError("no result records found")
    first = records[0]
    legacy = first.get("schema_version") == "1" and first.get("study_version") == "primitive-selection-v1"
    if legacy:
        engine, old_models, old_verify = _legacy_modules()
        cohort = first.get("cohort")
        if cohort not in ("development", "validation"):
            raise ValueError("legacy smoke/partial records cannot constitute a final cohort")
        expected = engine.cases_for(cohort, first.get("validation_nonce"))
        aggregate = engine._aggregate_repetitions
        sha = hashlib.sha256()
        for source in sorted((runner.PACKAGE / "legacy_v1").glob("*.py")):
            sha.update(source.name.encode() + b"\0" + source.read_bytes())
        _equal(first.get("source_digest"), sha.hexdigest(), "legacy archived source digest")
        identity = f"legacy:{first.get('study_version')}:{cohort}:{first.get('git_revision')}"
    else:
        engine = runner
        if first.get("schema_version") != runner.RESULT_SCHEMA_VERSION or first.get("study_version") != runner.STUDY_VERSION:
            raise ValueError("unsupported result version")
        mp = runner.manifest_path(path)
        if not mp.exists():
            raise ValueError("v2 cohort manifest missing")
        manifest = json.loads(mp.read_text())
        if manifest.get("state") != "complete":
            raise ValueError("partial runs are excluded from final analysis")
        _equal(manifest.get("records_sha256"), runner.file_digest(path), "cohort file digest")
        config = runner.configuration()
        _equal(manifest.get("configuration"), config, "configuration")
        _equal(manifest.get("configuration_digest"), digest(config), "configuration digest")
        deps = manifest.get("dependency_provenance", {})
        _equal(manifest.get("dependency_digest"), digest(deps), "dependency digest")
        _equal(deps.get("requirements_sha256"), runner.file_digest(runner.PACKAGE / "requirements.txt"), "dependency pins")
        _equal(deps.get("dockerfile_sha256"), runner.file_digest(runner.PACKAGE / "Dockerfile"), "container recipe")
        for package, version in deps.get("packages", {}).items():
            if version.get("installed") != version.get("required"):
                raise ValueError(f"unpinned dependency: {package}")
        _equal(manifest.get("source_digest"), runner._source_digest(), "source digest")
        cohort = manifest["cohort"]
        smoke = cohort == "smoke"
        expected = runner.cases_for("development" if smoke else cohort, manifest.get("validation_nonce"), smoke)
        _equal(manifest.get("expected_cases"), [asdict(case) for case in expected], "expected randomized grid")
        for count in ("expected_case_count", "completed_case_count"):
            _equal(manifest.get(count), len(expected), count)
        for field in PROVENANCE_FIELDS + V2_FIELDS:
            _equal(first.get(field), manifest.get(field), f"manifest {field}")
        if cohort == "validation":
            frozen, reviewer = manifest.get("freeze", {}), manifest.get("reviewer_nonce", {})
            _equal(frozen.get("source_digest"), manifest["source_digest"], "freeze source")
            _equal(frozen.get("configuration"), config, "freeze configuration")
            _equal(frozen.get("dependency_provenance"), deps, "freeze dependencies")
            _equal(reviewer.get("nonce"), manifest["validation_nonce"], "reviewer nonce")
            _equal(reviewer.get("freeze_sha256"), manifest.get("freeze_sha256"), "reviewer freeze reference")
            if manifest["git_dirty"] or manifest["container_image_digest"] == "unavailable":
                raise ValueError("validation requires clean container evidence")
        aggregate = runner._aggregate_repetitions
        identity = manifest["run_id"]
    _check_grid(records, expected)
    if not re.fullmatch(r"[0-9a-f]{40}", first.get("git_revision", "")):
        raise ValueError("invalid source revision")
    cache, instances = {}, {}
    counts = Counter(records=0, verified=0, timeouts=0, memory_limits=0)
    for index, record in enumerate(records, 1):
        try:
            for field in PROVENANCE_FIELDS + (() if legacy else V2_FIELDS):
                _equal(record.get(field), first.get(field), f"consistent {field}")
            case = engine.Case(**{field: record.get(field) for field in CASE_FIELDS})
            if not legacy:
                _equal(record.get("case_index"), index, "case order index")
                _equal(asdict(case), asdict(expected[index - 1]), "randomized case order")
            instance_key = (case.track, case.profile, case.eta, case.seed, case.source_track)
            if instance_key not in instances:
                instances[instance_key] = engine._instance(case)
            instance = instances[instance_key]
            _equal(record.get("instance_id"), instance.instance_id, "regenerated instance id")
            _equal(record.get("input_digest"), digest(instance.to_dict()), "input digest")
            measured = record.get("repetitions", [])
            _equal(len(measured), 3, "measured repetition count")
            _equal(record.get("output_digest"), digest([r.get("candidate") for r in measured]), "output digest")
            warmups = record.get("warmups", [])
            if not legacy:
                _equal(len(warmups), 1, "warmup count")
                _equal(record.get("warmup_output_digest"), digest([r.get("candidate") for r in warmups]), "warmup output digest")
            for repetition in warmups + measured:
                _metrics(repetition)
                if "candidate" in repetition:
                    candidate = repetition["candidate"]
                    cache_key = (record["input_digest"], digest(candidate))
                    if cache_key not in cache:
                        cache[cache_key] = (_legacy_verify(instance, candidate, old_models, old_verify) if legacy
                                            else verify_candidate(instance, candidate))
                    _equal(repetition.get("verification"), cache[cache_key], "independent candidate verification/quality")
                elif repetition.get("verification", {}).get("verified"):
                    raise ValueError("success without stored candidate")
                if not legacy:
                    _equal(repetition.get("status"), classify_result(repetition), "repetition status")
                if "solver_parameters" in repetition:
                    params = dict(engine.DEFAULT_PARAMETERS[case.solver]) if not legacy else None
                    if legacy:
                        from .legacy_v1.solvers import DEFAULT_PARAMETERS as old_params
                        params = dict(old_params[case.solver])
                    if case.track == "bkz" and case.solver == "progressive-bkz":
                        params["max_basis_dimension"] = 160
                    _equal(repetition["solver_parameters"], params, "solver settings")
            for field, value in aggregate(measured).items():
                _equal(record.get(field), value, f"aggregate {field}")
            counts["records"] += 1
            counts["verified"] += bool(record["verification_result"])
            counts["timeouts"] += bool(record["timeout"])
            counts["memory_limits"] += bool(record["memory_limit"])
            statuses = {classify_result(r) for r in measured}
            counts[statuses.pop() if len(statuses) == 1 else "mixed"] += 1
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{path}:{index}: {exc}") from exc
    return identity, records, counts


def audited_records(paths: list[Path]):
    result, identities = [], set()
    for path in paths:
        identity, records, _ = _audit_file(path)
        if identity in identities:
            raise ValueError("duplicate run identity across inputs")
        identities.add(identity)
        result.extend(records)
    if not result:
        raise ValueError("no result records found")
    return result


def audit(paths: list[Path]) -> dict[str, int]:
    total, identities = Counter(), set()
    for path in paths:
        identity, _, counts = _audit_file(path)
        if identity in identities:
            raise ValueError("duplicate run identity across inputs")
        identities.add(identity)
        total.update(counts)
    if not total["records"]:
        raise ValueError("no result records found")
    return dict(total)
