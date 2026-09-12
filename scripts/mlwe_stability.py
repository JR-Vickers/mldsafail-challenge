"""Observational repeat-execution study for one frozen MLWE private epoch."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Any

from mldsafail.benchmark_v050 import cli as frozen_cli
from mldsafail.benchmark_v050 import evidence as ev
from mldsafail.benchmark_v050.execution import environment
from mldsafail.benchmark_v050.scoring import CHALLENGE_CELLS, case_cost

STUDY_VERSION = "mlwe-measurement-stability-v1"
ROLES = ("native", "adapter", "candidate")
CYCLES = 10
RUNS = CYCLES * len(ROLES)
EXECUTIONS_PER_RUN = 100 * 4
EPOCH_EXECUTIONS = 100 * 3 * 4
TOTAL_EXECUTIONS = EPOCH_EXECUTIONS + RUNS * EXECUTIONS_PER_RUN
SENSITIVE_KEYS = frozenset({
    "nonce", "secret", "secrets", "seed", "seeds", "candidate", "candidates",
    "stdout", "stderr", "stream", "streams", "records", "measurements", "host",
    "host_id", "path", "paths", "private_root", "case", "cases",
})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_files(source: Path) -> dict[str, dict[str, Any]]:
    """Use the frozen snapshot validation without writing an evidence snapshot."""
    from scripts.mlwe_pilot import source_files as pilot_source_files
    return pilot_source_files(source)


def source_digest(source: Path) -> str:
    return ev.sha(source_files(source))


def role_order(cycle: int) -> tuple[str, str, str]:
    if not 1 <= cycle <= CYCLES:
        raise ValueError("cycle is outside the predeclared cohort")
    offset = (cycle - 1) % len(ROLES)
    return ROLES[offset:] + ROLES[:offset]


def run_name(cycle: int, role: str) -> str:
    if role not in ROLES:
        raise ValueError("unknown study role")
    return f"cycle-{cycle:02d}-{role}"


def _public_environment(env: dict[str, Any]) -> dict[str, Any]:
    artifacts = env["artifacts"]
    return {"image_id": env["image_id"], "trusted_fingerprint": env["trusted_fingerprint"],
            "artifact_digest": ev.sha(artifacts), "architecture": artifacts["architecture"],
            "python": artifacts["python"], "packages": artifacts["packages"]}


def _write_incomplete(root: Path, exc: BaseException) -> None:
    marker = root / "INCOMPLETE.json"
    if not marker.exists():
        ev.write(marker, {"study_version": STUDY_VERSION, "complete": False,
                          "finished_utc": utc_now(),
                          "failure": f"{type(exc).__name__}: {exc}"})


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.private_root.exists():
        raise ValueError("private evidence root already exists; cohorts never resume")
    expected = {"adapter": args.adapter_digest, "candidate": args.candidate_digest}
    actual = {role: source_digest(getattr(args, f"{role}_dir")) for role in expected}
    if actual != expected:
        raise ValueError("contestant source identity mismatch before study")
    root = ev.directory(args.private_root)
    try:
        ev.write(root / "study.json", {"study_version": STUDY_VERSION, "complete": False,
                 "created_utc": utc_now(), "cycles": CYCLES, "roles": list(ROLES),
                 "role_order": [list(role_order(cycle)) for cycle in range(1, CYCLES + 1)],
                 "adapter_source_digest": expected["adapter"],
                 "candidate_source_digest": expected["candidate"],
                 "expected_total_executions": TOTAL_EXECUTIONS})
        frozen_cli.create_epoch(root / "epoch")
        epoch_manifest, _ = ev.audit_epoch(root / "epoch")
        expected_env = epoch_manifest["environment"]
        ev.directory(root / "runs")
        for cycle in range(1, CYCLES + 1):
            for role in role_order(cycle):
                if environment() != expected_env:
                    raise ValueError("execution environment changed during study")
                output = root / "runs" / run_name(cycle, role)
                if role == "native":
                    frozen_cli.evaluate(output, epoch_manifest["cases"], expected_env,
                                        "primal-lll", epoch_manifest)
                else:
                    source = getattr(args, f"{role}_dir")
                    if source_digest(source) != expected[role]:
                        raise ValueError(f"{role} source identity changed during study")
                    frozen_cli.evaluate(output, epoch_manifest["cases"], expected_env,
                                        "contestant", epoch_manifest, source)
        result = analyze_root(root, expected["adapter"], expected["candidate"])
        ev.write(root / "COMPLETE_STUDY.json", {"study_version": STUDY_VERSION,
                 "complete": True, "finished_utc": utc_now(), "analysis_sha256": ev.sha(result)})
        return result
    except BaseException as exc:
        _write_incomplete(root, exc)
        raise


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    return numerator / denominator if numerator is not None and denominator not in (None, 0) else None


def _geomean(values: list[float]) -> float | None:
    return math.exp(statistics.fmean(math.log(value) for value in values)) if values else None


def _cell_ratio(reference: list[dict[str, Any]], measured: list[dict[str, Any]],
                profile: str, eta: int) -> float:
    index = {row["instance_id"]: row for row in reference}
    values = [case_cost(row) / case_cost(index[row["instance_id"]]) for row in measured
              if (row["profile"], row["eta"]) == (profile, eta)]
    if not values or len(values) != sum((r["profile"], r["eta"]) == (profile, eta) for r in reference):
        raise ValueError("incompatible cell evidence")
    return _geomean(values)  # type: ignore[return-value]


def _variation(values: list[float]) -> dict[str, float | int | None]:
    return {"count": len(values), "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
            "median": statistics.median(values) if values else None,
            "coefficient_of_variation": (statistics.pstdev(values) / statistics.fmean(values)
                                           if len(values) > 1 and statistics.fmean(values) else None)}


def _case_variation(rows_by_role: dict[str, list[list[dict[str, Any]]]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for role, runs in rows_by_role.items():
        by_cell: dict[str, list[float]] = {}
        per_case: dict[str, list[float]] = {}
        for rows in runs:
            for row in rows:
                if row["verification_result"]:
                    key = row["instance_id"]
                    per_case.setdefault(key, []).append(row["median_cpu_seconds"])
        # Case IDs stay private; only their per-case relative variation is aggregated.
        cells = {row["instance_id"]: f"{row['profile']}/eta{row['eta']}"
                 for rows in runs for row in rows if row["verification_result"]}
        for case_id, values in per_case.items():
            if len(values) == len(runs):
                cv = _variation(values)["coefficient_of_variation"]
                if cv is not None:
                    by_cell.setdefault(cells[case_id], []).append(float(cv))
        result[role] = {cell: _variation(values) for cell, values in sorted(by_cell.items())}
    return result


def _analyze_once(root: Path, adapter_digest: str, candidate_digest: str) -> dict[str, Any]:
    if (root / "INCOMPLETE.json").exists():
        raise ValueError("study evidence is incomplete")
    study = ev.read(root / "study.json")
    if study["study_version"] != STUDY_VERSION or study["cycles"] != CYCLES or study["roles"] != list(ROLES):
        raise ValueError("incompatible stability study protocol")
    if study["adapter_source_digest"] != adapter_digest or study["candidate_source_digest"] != candidate_digest:
        raise ValueError("requested source identity differs from study evidence")
    epoch, reference = ev.audit_epoch(root / "epoch")
    runs: list[dict[str, Any]] = []
    rows_by_role: dict[str, list[list[dict[str, Any]]]] = {role: [] for role in ROLES}
    raw_by_cycle: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for cycle in range(1, CYCLES + 1):
        for role in role_order(cycle):
            manifest, rows = ev.audit_run(root / "runs" / run_name(cycle, role), root / "epoch")
            if manifest["environment"] != epoch["environment"]:
                raise ValueError("run environment differs from epoch")
            if role == "native":
                if manifest["solver"] != "primal-lll" or manifest["solver_files"] is not None:
                    raise ValueError("native run is not frozen primal-LLL")
            else:
                if manifest["solver"] != "contestant" or ev.sha(manifest["solver_files"]) != study[f"{role}_source_digest"]:
                    raise ValueError(f"{role} source snapshot mismatch")
            summary = ev.summary(manifest, rows, reference)
            if not summary["eligible"]:
                raise ValueError("invalid answer makes stability cohort ineligible")
            runs.append({"cycle": cycle, "role": role, "run_id": summary["run_id"],
                         "score": summary["score"], "interval_95": summary["interval_95"],
                         "failures": summary["repetition_status_counts"], "cells": summary["cells"]})
            rows_by_role[role].append(rows)
            raw_by_cycle[(cycle, role)] = rows
    role_summary = {}
    for role in ROLES:
        role_runs = [item for item in runs if item["role"] == role]
        scores = [item["score"] for item in role_runs]
        failures = Counter()
        for item in role_runs:
            failures.update(item["failures"])
        cells = {}
        for profile, eta in CHALLENGE_CELLS:
            cell = f"{profile}/eta{eta}"
            cell_rows = [item["cells"][cell] for item in role_runs]
            cells[cell] = {"successes": sum(row["successes"] for row in cell_rows),
                           "cases": sum(row["cases"] for row in cell_rows),
                           "timing_variation": _variation([row["successful_median_cpu_seconds"]
                               for row in cell_rows if row["successful_median_cpu_seconds"] is not None])}
        role_summary[role] = {"ordered_run_series": scores, "score_statistics": _variation(scores),
                              "failure_counts": dict(sorted(failures.items())),
                              "cell_aggregate": cells}
    comparisons = []
    for cycle in range(1, CYCLES + 1):
        native = next(r for r in runs if r["cycle"] == cycle and r["role"] == "native")
        adapter = next(r for r in runs if r["cycle"] == cycle and r["role"] == "adapter")
        candidate = next(r for r in runs if r["cycle"] == cycle and r["role"] == "candidate")
        comparisons.append({"cycle": cycle, "adapter_native_ratio": _ratio(adapter["score"], native["score"]),
            "candidate_adapter_ratio": _ratio(candidate["score"], adapter["score"]),
            "cell_adapter_native_ratios": {f"{p}/eta{e}": _cell_ratio(raw_by_cycle[(cycle, "native")], raw_by_cycle[(cycle, "adapter")], p, e) for p, e in CHALLENGE_CELLS},
            "cell_candidate_adapter_ratios": {f"{p}/eta{e}": _cell_ratio(raw_by_cycle[(cycle, "adapter")], raw_by_cycle[(cycle, "candidate")], p, e) for p, e in CHALLENGE_CELLS}})
    aggregate_cell_ratios = {}
    for profile, eta in CHALLENGE_CELLS:
        cell = f"{profile}/eta{eta}"
        aggregate_cell_ratios[cell] = {
            "adapter_native": _variation([item["cell_adapter_native_ratios"][cell] for item in comparisons]),
            "candidate_adapter": _variation([item["cell_candidate_adapter_ratios"][cell] for item in comparisons]),
        }
    return {"study_version": STUDY_VERSION, "benchmark_version": "0.5.0", "complete": True,
            "provenance": {"epoch_id": epoch["id"], "adapter_source_digest": adapter_digest,
                           "candidate_source_digest": candidate_digest, "environment": _public_environment(epoch["environment"]),
                           "cycles": CYCLES, "runs": RUNS, "executions": TOTAL_EXECUTIONS,
                           "analysis_reproductions": 2}, "runs": runs, "roles": role_summary,
            "comparisons": comparisons,
            "aggregate_ratios": {"adapter_native": _variation([x["adapter_native_ratio"] for x in comparisons]),
                                 "candidate_adapter": _variation([x["candidate_adapter_ratio"] for x in comparisons])},
            "aggregate_cell_ratios": aggregate_cell_ratios,
            "case_level_variation": _case_variation(rows_by_role), "tie_band_percent": 1.0,
            "interpretation": "Descriptive one-host, one-epoch observation only; it makes no statistical-significance or portability claim and cannot justify a scoring, tie-band, or environment change."}


def analyze_root(root: Path, adapter_digest: str, candidate_digest: str) -> dict[str, Any]:
    first = _analyze_once(root, adapter_digest, candidate_digest)
    second = _analyze_once(root, adapter_digest, candidate_digest)
    if ev.encoded(first) != ev.encoded(second):
        raise ValueError("analysis did not reproduce byte-for-byte")
    return first


def sanitize(value: Any, parent_key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: sanitize(item, key) for key, item in value.items()
                if parent_key == "roles" or key.lower() not in SENSITIVE_KEYS}
    if isinstance(value, list):
        return [sanitize(item, parent_key) for item in value]
    return value


def render_report(summary: dict[str, Any]) -> str:
    lines = ["# MLWE Measurement-Stability Study", "",
             "This is a descriptive, single-host, single-epoch observational cohort. It makes no statistical-significance or portability claim and cannot justify a scoring, tie-band, or environment change.", "",
             f"Cohort: {summary['provenance']['runs']} ranked runs and {summary['provenance']['executions']} fresh executions.", ""]
    for role in ROLES:
        stats = summary["roles"][role]["score_statistics"]
        lines.append(f"- {role}: median {stats['median']:.6f}; range {stats['minimum']:.6f}–{stats['maximum']:.6f}; CV {stats['coefficient_of_variation']:.6f}.")
    a = summary["aggregate_ratios"]["adapter_native"]
    c = summary["aggregate_ratios"]["candidate_adapter"]
    lines += ["", f"Adapter/native ratio median: {a['median']:.6f}; candidate/adapter ratio median: {c['median']:.6f}.",
              f"The frozen tie band is {summary['tie_band_percent']:.0f}%; reported variation is descriptive rather than a decision rule.", ""]
    return "\n".join(lines)


def report(args: argparse.Namespace) -> dict[str, Any]:
    if args.summary.exists() or args.markdown.exists():
        raise ValueError("report outputs already exist")
    summary = sanitize(analyze_root(args.private_root, args.adapter_digest, args.candidate_digest))
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    ev.write(args.summary, summary)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.markdown, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w") as stream:
        stream.write(render_report(summary))
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="mlwe_stability.py")
    commands = result.add_subparsers(dest="command", required=True)
    run_cmd = commands.add_parser("run")
    run_cmd.add_argument("--adapter-dir", type=Path, required=True); run_cmd.add_argument("--candidate-dir", type=Path, required=True)
    run_cmd.add_argument("--adapter-digest", required=True); run_cmd.add_argument("--candidate-digest", required=True)
    run_cmd.add_argument("--private-root", type=Path, required=True)
    for name in ("analyze", "report"):
        cmd = commands.add_parser(name); cmd.add_argument("--private-root", type=Path, required=True)
        cmd.add_argument("--adapter-digest", required=True); cmd.add_argument("--candidate-digest", required=True)
    commands.choices["report"].add_argument("--summary", type=Path, required=True)
    commands.choices["report"].add_argument("--markdown", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        value = {"run": run, "analyze": lambda a: analyze_root(a.private_root, a.adapter_digest, a.candidate_digest), "report": report}[args.command](args)
        print(json.dumps(value, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"mlwe-stability: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
