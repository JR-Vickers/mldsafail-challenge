"""Command-line entry point for deterministic toy benchmark suites.

The default runs visible public seeds. ``--suite full`` runs the same profiles
over public seeds and then the separately stored hidden seeds.  An explicit
``--seed`` is a diagnostic custom run and requires ``--profile``.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from mldsafail import __version__
from mldsafail.benchmark.metrics import aggregate_profile, measure_profile
from mldsafail.benchmark.records import DEFAULT_RECORDS_PATH, append_record, new_experiment_record
from mldsafail.benchmark.suites import load_seed_suite, selected_suites
from mldsafail.models import InstanceMetrics, ProfileMetrics
from mldsafail.solver import solve
from mldsafail.solver.lazy import solve as lazy_solve


UNSCORED_AGGREGATE = {
    "total_wall_seconds": None,
    "median_instance_seconds": None,
    "peak_memory_bytes": None,
    "abstract_cost": None,
    "solution_quality": None,
}


def _trusted_functions():
    # Imports remain at the trusted boundary and make the separation obvious.
    from mldsafail.trusted.generator import generate_instance
    from mldsafail.trusted.verifier import verify

    return generate_instance, verify


def _profile_payload(metrics: ProfileMetrics) -> dict[str, Any]:
    return asdict(metrics)


def _aggregate(profiles: list[ProfileMetrics]) -> dict[str, Any]:
    instances = [item for profile in profiles for item in profile.instances]
    correct = bool(profiles) and all(profile.correct for profile in profiles)
    qualities = [item.solution_quality for item in instances if item.solution_quality is not None]
    # Correctness gates every scored field. Timing is still present inside each
    # instance for diagnosing failures, but an invalid run cannot be ranked.
    if not correct:
        return dict(UNSCORED_AGGREGATE)
    return {
        "total_wall_seconds": sum(item.wall_seconds for item in instances),
        "median_instance_seconds": statistics.median(item.wall_seconds for item in instances),
        "peak_memory_bytes": max((item.peak_memory_bytes for item in instances), default=0),
        "abstract_cost": sum(int(item.cost["total"]) for item in instances),
        "solution_quality": int(statistics.median(qualities)) if qualities else 0,
    }


def _combined_profiles(suite_results: dict[str, dict[str, ProfileMetrics]]) -> dict[str, Any]:
    grouped: dict[str, list[InstanceMetrics]] = {}
    for profiles in suite_results.values():
        for name, result in profiles.items():
            grouped.setdefault(name, []).extend(result.instances)
    return {
        name: _profile_payload(aggregate_profile(name, instances))
        for name, instances in grouped.items()
    }


def run_benchmark(
    *,
    suite: str = "public",
    profile: str | None = None,
    seed: int | None = None,
    solver_name: str = "balanced",
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Run selected instances and return suites, aggregate, correctness."""

    if seed is not None and profile is None:
        raise ValueError("--seed requires --profile")
    generate_instance, verify = _trusted_functions()
    solver = {"balanced": solve, "lazy": lazy_solve}.get(solver_name)
    if solver is None:
        raise ValueError(f"unknown solver: {solver_name}")
    selections = ("custom",) if seed is not None else selected_suites(suite)
    results: dict[str, dict[str, ProfileMetrics]] = {}
    for suite_name in selections:
        mapping = {profile: (seed,)} if seed is not None else load_seed_suite(suite_name, profile)
        results[suite_name] = {}
        for profile_name, seeds in mapping.items():
            instances = [generate_instance(seed=value, profile=profile_name) for value in seeds]
            results[suite_name][profile_name] = measure_profile(
                profile_name, instances, solve, verify
            )

    all_profiles = [value for profiles in results.values() for value in profiles.values()]
    aggregate = _aggregate(all_profiles)
    serializable = {
        suite_name: {name: _profile_payload(value) for name, value in profiles.items()}
        for suite_name, profiles in results.items()
    }
    correct = bool(all_profiles) and all(item.correct for item in all_profiles)
    return serializable, aggregate, correct


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("toy-small", "toy-medium", "toy-large"))
    parser.add_argument(
        "--solver", choices=("balanced", "lazy"), default="balanced",
        help="balanced (default) or experimental lazy-reduction solver",
    )
    parser.add_argument("--seed", type=int, help="diagnostic seed; requires --profile")
    parser.add_argument(
        "--suite", choices=("public", "hidden", "full"), default="public",
        help="public (default), hidden only, or full (public followed by hidden)",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_RECORDS_PATH)
    parser.add_argument("--no-record", action="store_true", help="print without appending JSONL")
    parser.add_argument("--agent", default=os.environ.get("MLDSAFAIL_AGENT", "unknown"))
    parser.add_argument("--model", default=os.environ.get("MLDSAFAIL_MODEL", "unknown"))
    parser.add_argument("--hypothesis", default="baseline benchmark run")
    parser.add_argument("--tag", action="append", dest="tags")
    parser.add_argument("--notes", default="")
    parser.add_argument("--parent-experiment")
    parser.add_argument(
        "--baseline-fingerprint",
        help="expected trusted-input fingerprint; a mismatch is recorded as an invalid run",
    )
    return parser


def _integrity_status(baseline_fingerprint: str | None) -> dict[str, Any]:
    from mldsafail.benchmark.integrity import compute_trusted_fingerprint

    current = compute_trusted_fingerprint()
    return {
        "trusted_fingerprint": current,
        "baseline_fingerprint": baseline_fingerprint,
        "matches_baseline": None if baseline_fingerprint is None else current == baseline_fingerprint,
    }


def _profile_failure_reason(suites: dict[str, Any]) -> str | None:
    failures = [
        instance.get("failure_reason")
        for profiles in suites.values()
        for profile in profiles.values()
        for instance in profile.get("instances", [])
        if instance.get("failure_reason")
    ]
    return "; ".join(dict.fromkeys(failures)) if failures else None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.seed is not None and args.profile is None:
        parser.error("--seed requires --profile")
    if args.seed is not None and args.suite != "public":
        parser.error("--seed cannot be combined with --suite hidden or --suite full")
    suites: dict[str, Any] = {}
    aggregate = dict(UNSCORED_AGGREGATE)
    correct = False
    failure_reason: str | None = None
    try:
        integrity = _integrity_status(args.baseline_fingerprint)
        if integrity["matches_baseline"] is False:
            failure_reason = "trusted-input fingerprint does not match the supplied baseline"
        else:
            suites, aggregate, correct = run_benchmark(
                suite=args.suite, profile=args.profile, seed=args.seed,
                solver_name=args.solver,
            )
            failure_reason = _profile_failure_reason(suites) if not correct else None
    except Exception as exc:
        # Generation, integrity, or benchmark infrastructure failures should be
        # auditable records. argparse errors remain usage errors and never write.
        integrity = {
            "trusted_fingerprint": None,
            "baseline_fingerprint": args.baseline_fingerprint,
            "matches_baseline": None,
        }
        failure_reason = f"{type(exc).__name__}: {exc}"
    # Provide a profile-centric compatibility view alongside suite provenance.
    hydrated: dict[str, dict[str, ProfileMetrics]] = {}
    for suite_name, profiles in suites.items():
        hydrated[suite_name] = {}
        for name, payload in profiles.items():
            instances = [InstanceMetrics(**item) for item in payload["instances"]]
            hydrated[suite_name][name] = ProfileMetrics(**(payload | {"instances": instances}))
    profiles = _combined_profiles(hydrated)
    record = new_experiment_record(
        benchmark_version=__version__,
        suites=suites,
        profiles=profiles,
        aggregate=aggregate,
        correct=correct,
        agent=args.agent,
        model=args.model,
        hypothesis=args.hypothesis,
        tags=args.tags,
        notes=args.notes,
        parent_experiment=args.parent_experiment,
        command=[sys.executable, "-m", "mldsafail.benchmark.runner", *(argv or sys.argv[1:])],
        integrity=integrity,
        failure_reason=failure_reason,
        solver=args.solver,
    )
    if not args.no_record:
        append_record(record, args.output)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if correct else 1


if __name__ == "__main__":
    raise SystemExit(main())
