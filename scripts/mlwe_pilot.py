"""Bounded public-development and private-validation orchestration for MLWE 0.5.0."""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from mldsafail.benchmark_v050 import cli as frozen_cli
from mldsafail.benchmark_v050 import evidence as ev
from mldsafail.benchmark_v050.constants import DEVELOPMENT_SEEDS, MAX_SERIALIZED_BYTES
from mldsafail.benchmark_v050.execution import environment
from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v050.models import digest
from mldsafail.benchmark_v050.scoring import CHALLENGE_CELLS, case_cost, ranking, ranking_interval, tied

PILOT_VERSION = "mlwe-agent-pilot-v1"
FINAL_ORDER = ((1, "reference"), (1, "candidate"), (2, "candidate"),
               (2, "reference"), (3, "reference"), (3, "candidate"))
PUBLIC_CASES = len(CHALLENGE_CELLS) * len(DEVELOPMENT_SEEDS)
EXECUTIONS_PER_CASE = 4
PUBLIC_EXECUTIONS = PUBLIC_CASES * EXECUTIONS_PER_CASE
MAX_HYPOTHESES = 6
OPTIMIZATION_BUDGET = timedelta(hours=4)
SENSITIVE_KEYS = frozenset({
    "nonce", "secret", "secrets", "seed", "seeds", "candidate",
    "candidates", "stdout", "stderr", "stream", "streams", "records",
    "measurements", "path", "paths", "host", "host_id", "private_root",
})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_cases() -> list[dict[str, Any]]:
    rows = []
    for profile, eta in CHALLENGE_CELLS:
        for seed in DEVELOPMENT_SEEDS:
            public = generate_mlwe(profile, seed, eta).public
            rows.append({"profile": profile, "eta": eta, "seed": seed,
                         "instance_id": public.instance_id,
                         "input_digest": digest(public.to_dict())})
    return rows


def source_files(source: Path) -> dict[str, dict[str, Any]]:
    source = source.resolve()
    if not (source / "solver.py").is_file():
        raise ValueError("solver directory must contain solver.py")
    result: dict[str, dict[str, Any]] = {}
    total = 0
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("solver symlinks are forbidden")
        if path.is_file():
            if path.suffix != ".py":
                raise ValueError("only Python source files are approved solver files")
            data = path.read_bytes()
            total += len(data)
            if total > MAX_SERIALIZED_BYTES:
                raise ValueError("solver source exceeds 2 MB")
            result[str(path.relative_to(source))] = {
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    return result


def source_digest(source: Path) -> str:
    return ev.sha(source_files(source))


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = ev.encoded(value) + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _run_dir(path: Path) -> Path:
    return path / "run" if (path / "run").is_dir() else path


def audited_public(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run = _run_dir(path)
    manifest, rows = ev.audit_run(run)
    if manifest["cases"] != public_cases():
        raise ValueError("development run does not use the exact public grid")
    return manifest, rows


def _label(rows: list[dict[str, Any]], solver: str) -> list[dict[str, Any]]:
    return [{**copy.deepcopy(row), "solver": solver} for row in rows]


def diagnostic_scores(baseline_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]],
                      candidate_name: str) -> tuple[float, dict[str, float]]:
    reference = _label(baseline_rows, "primal-lll")
    candidate = _label(candidate_rows, candidate_name)
    total = ranking(reference + candidate, candidate_name)
    baseline = {(r["profile"], r["eta"], r["seed"]): r for r in baseline_rows}
    cells: dict[str, float] = {}
    for profile, eta in CHALLENGE_CELLS:
        logs = []
        for row in candidate_rows:
            if (row["profile"], row["eta"]) == (profile, eta):
                key = (profile, eta, row["seed"])
                logs.append(math.log(case_cost(row) / case_cost(baseline[key])))
        cells[f"{profile}/eta{eta}"] = math.exp(sum(logs) / len(logs))
    return total, cells


def select_candidate(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [r for r in records if r.get("complete") and r.get("eligible")
                and r.get("diagnostic_score") is not None]
    if not eligible:
        return None
    baseline = next((r for r in eligible if r.get("role") == "baseline"), None)
    if baseline is None:
        raise ValueError("experiment ledger has no eligible baseline")
    winner = baseline
    for record in eligible:
        if record["diagnostic_score"] < winner["diagnostic_score"]:
            winner = record
    return winner


def enforce_budget(records: list[dict[str, Any]], now: datetime) -> None:
    baselines = [r for r in records if r.get("role") == "baseline" and r.get("complete")]
    if len(baselines) != 1:
        raise ValueError("optimization requires exactly one completed baseline")
    attempts = [r for r in records if r.get("role") == "candidate"]
    if len(attempts) >= MAX_HYPOTHESES:
        raise ValueError("six-hypothesis optimization budget exhausted")
    started = datetime.fromisoformat(baselines[0]["finished_utc"])
    if now >= started + OPTIMIZATION_BUDGET:
        raise ValueError("four-hour optimization budget expired")


def classify_outcome(pair_scores: list[tuple[float, float]], eligible: bool = True,
                     complete: bool = True) -> str:
    if not complete:
        return "incomplete"
    if not eligible:
        return "invalid"
    if all(candidate < reference and not tied(candidate, reference)
           for reference, candidate in pair_scores):
        return "consistent observed improvement"
    if all(tied(candidate, reference) for reference, candidate in pair_scores):
        return "tied"
    if all(candidate > reference and not tied(candidate, reference)
           for reference, candidate in pair_scores):
        return "regressed"
    return "inconsistent"


def _experiment_record(args: argparse.Namespace, started: str, digest_value: str,
                       env: dict[str, Any]) -> dict[str, Any]:
    return {"pilot_version": PILOT_VERSION, "experiment_id": args.output.name,
            "role": "baseline" if args.baseline_run is None else "candidate",
            "hypothesis": args.hypothesis, "mechanism": args.mechanism,
            "parent_revision": args.parent_revision, "source_digest": digest_value,
            "agent": args.agent, "model": args.model, "started_utc": started,
            "command": sys.argv, "environment": env}


def develop(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists():
        raise ValueError("output directory already exists")
    solver_digest = source_digest(args.solver_dir)
    if args.expected_source_digest and solver_digest != args.expected_source_digest:
        raise ValueError("contestant source identity changed")
    env = environment()
    if args.baseline_run is not None:
        enforce_budget(read_jsonl(args.ledger), datetime.now(timezone.utc))
        baseline_manifest, baseline_rows = audited_public(args.baseline_run)
        if env != baseline_manifest["environment"]:
            raise ValueError("development environment changed from baseline")
    else:
        baseline_rows = None
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    started = utc_now()
    start = _experiment_record(args, started, solver_digest, env)
    ev.write(args.output / "experiment-start.json", start)
    try:
        frozen_cli.evaluate(args.output / "run", public_cases(), env, "contestant",
                            solver_dir=args.solver_dir)
        manifest, rows = audited_public(args.output)
        summary = ev.summary(manifest, rows)
        if not summary["eligible"]:
            score, cells = None, {}
        elif baseline_rows is None:
            score, cells = 1.0, {f"{p}/eta{e}": 1.0 for p, e in CHALLENGE_CELLS}
        else:
            score, cells = diagnostic_scores(baseline_rows, rows, manifest["id"])
        result = {**start, "finished_utc": utc_now(), "complete": True,
                  "eligible": summary["eligible"], "correctness": summary,
                  "failures": summary["repetition_status_counts"],
                  "cell_scores": cells, "diagnostic_score": score,
                  "score_kind": "diagnostic-public-development"}
        previous = select_candidate(read_jsonl(args.ledger)) if args.ledger.exists() else None
        if result["role"] == "baseline":
            result["decision"] = "keep_baseline"
        elif not result["eligible"]:
            result["decision"] = "reject_invalid"
        elif previous is None or score < previous["diagnostic_score"]:
            result["decision"] = "keep"
        else:
            result["decision"] = "revert"
        ev.write(args.output / "experiment-result.json", result)
        append_jsonl(args.ledger, result)
        return result
    except BaseException as exc:
        incomplete = {**start, "finished_utc": utc_now(), "complete": False,
                      "eligible": False, "diagnostic_score": None,
                      "decision": "retain_incomplete", "failure": f"{type(exc).__name__}: {exc}"}
        ev.write(args.output / "experiment-incomplete.json", incomplete)
        append_jsonl(args.ledger, incomplete)
        raise


def _case_ratio(reference_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]],
                profile: str, eta: int) -> float:
    reference = {(r["profile"], r["eta"], r["seed"]): r for r in reference_rows}
    logs = [math.log(case_cost(row) / case_cost(reference[(profile, eta, row["seed"])]))
            for row in candidate_rows if (row["profile"], row["eta"]) == (profile, eta)]
    return math.exp(sum(logs) / len(logs))


def analyze_private(root: Path, reference_digest: str, candidate_digest: str) -> dict[str, Any]:
    epoch_manifest, epoch_reference = ev.audit_epoch(root / "epoch")
    expected = {"reference": reference_digest, "candidate": candidate_digest}
    audited: dict[tuple[int, str], tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]] = {}
    for pair, role in FINAL_ORDER:
        path = root / "runs" / f"pair-{pair}-{role}"
        manifest, rows = ev.audit_run(path, root / "epoch")
        if ev.sha(manifest["solver_files"]) != expected[role]:
            raise ValueError(f"frozen {role} source identity mismatch")
        summary = ev.summary(manifest, rows, epoch_reference)
        audited[(pair, role)] = (manifest, rows, summary)
    runs = []
    pairs = []
    for pair in range(1, 4):
        _, ref_rows, ref_summary = audited[(pair, "reference")]
        _, cand_rows, cand_summary = audited[(pair, "candidate")]
        for role, summary in (("reference", ref_summary), ("candidate", cand_summary)):
            runs.append({"pair": pair, "role": role, "run_id": summary["run_id"],
                         "eligible": summary["eligible"], "score": summary.get("score"),
                         "interval_95": summary.get("interval_95"),
                         "failures": summary["repetition_status_counts"],
                         "cells": summary["cells"]})
        ratio = cand_summary["score"] / ref_summary["score"] if (
            cand_summary["eligible"] and ref_summary["eligible"]) else None
        cells = {f"{p}/eta{e}": _case_ratio(ref_rows, cand_rows, p, e)
                 for p, e in CHALLENGE_CELLS} if ratio is not None else {}
        pairs.append({"pair": pair, "candidate_reference_ratio": ratio,
                      "candidate_wins_beyond_tie_band": ratio is not None and
                      cand_summary["score"] < ref_summary["score"] and
                      not tied(cand_summary["score"], ref_summary["score"]),
                      "cell_candidate_reference_ratios": cells})
    eligible = all(run["eligible"] for run in runs)
    ratios = [pair["candidate_reference_ratio"] for pair in pairs]
    outcome = classify_outcome(
        [(audited[(p, "reference")][2]["score"], audited[(p, "candidate")][2]["score"])
         for p in range(1, 4)], eligible)
    reference_scores = [audited[(p, "reference")][2]["score"] for p in range(1, 4)]
    public_environment = {"image_id": epoch_manifest["environment"]["image_id"],
                          "trusted_fingerprint": epoch_manifest["environment"]["trusted_fingerprint"],
                          "artifact_digest": ev.sha(epoch_manifest["environment"]["artifacts"]),
                          "architecture": epoch_manifest["environment"]["artifacts"]["architecture"],
                          "python": epoch_manifest["environment"]["artifacts"]["python"],
                          "packages": epoch_manifest["environment"]["artifacts"]["packages"]}
    return {"pilot_version": PILOT_VERSION, "benchmark_version": "0.5.0",
            "complete": True, "outcome": outcome,
            "provenance": {"epoch_id": epoch_manifest["id"],
                           "reference_source_digest": reference_digest,
                           "candidate_source_digest": candidate_digest,
                           "environment": public_environment,
                           "final_order": [list(item) for item in FINAL_ORDER],
                           "analysis_reproductions": 2},
            "runs": runs, "pairs": pairs,
            "reference_score_spread": {"minimum": min(reference_scores),
                                       "maximum": max(reference_scores),
                                       "relative_range": max(reference_scores) / min(reference_scores) - 1},
            "interpretation": "initial repeat-execution stability check; no claim of statistical significance",
            "adapter_note": "scores include the frozen reference/contestant adapter difference separately from repeat-execution variation"}


def sanitize_private_summary(value: dict[str, Any]) -> dict[str, Any]:
    allowed_top = {"pilot_version", "benchmark_version", "complete", "outcome", "provenance",
                   "runs", "pairs", "reference_score_spread", "interpretation", "adapter_note"}
    allowed_nested = {"epoch_id", "reference_source_digest", "candidate_source_digest", "final_order",
                      "environment", "image_id", "trusted_fingerprint", "artifact_digest",
                      "architecture", "python", "packages", "fpylll", "cysignals",
                      "analysis_reproductions", "pair", "role", "run_id", "eligible", "score",
                      "interval_95", "failures", "cells", "success", "timeout", "memory_failure",
                      "crash", "no_candidate", "applicability_cap", "invalid_answer", "mixed",
                      "successes", "successful_median_cpu_seconds", "candidate_reference_ratio",
                      "candidate_wins_beyond_tie_band", "cell_candidate_reference_ratios",
                      "minimum", "maximum", "relative_range", "cases"}
    def clean(item: Any, top: bool = False) -> Any:
        if isinstance(item, dict):
            permitted = allowed_top if top else allowed_nested
            cell_keys = {f"{p}/eta{e}" for p, e in CHALLENGE_CELLS}
            return {key: clean(val) for key, val in item.items()
                    if (key in permitted or key in cell_keys)
                    and key.lower() not in SENSITIVE_KEYS}
        if isinstance(item, list):
            return [clean(part) for part in item]
        return item
    return clean(value, top=True)


def final(args: argparse.Namespace) -> dict[str, Any]:
    if args.private_root.exists():
        raise ValueError("private output directory already exists")
    if args.public_summary.exists():
        raise ValueError("public summary already exists")
    actual = {"reference": source_digest(args.reference_dir),
              "candidate": source_digest(args.candidate_dir)}
    expected = {"reference": args.reference_digest, "candidate": args.candidate_digest}
    if actual != expected:
        raise ValueError("frozen source identity mismatch before private validation")
    args.private_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    try:
        frozen_cli.create_epoch(args.private_root / "epoch")
        epoch_manifest, _ = ev.audit_epoch(args.private_root / "epoch")
        expected_env = epoch_manifest["environment"]
        (args.private_root / "runs").mkdir(mode=0o700)
        for pair, role in FINAL_ORDER:
            if environment() != expected_env:
                raise ValueError("private execution environment changed")
            solver_dir = args.reference_dir if role == "reference" else args.candidate_dir
            if source_digest(solver_dir) != expected[role]:
                raise ValueError(f"frozen {role} source identity changed")
            frozen_cli.evaluate(args.private_root / "runs" / f"pair-{pair}-{role}",
                                epoch_manifest["cases"], expected_env, "contestant",
                                epoch_manifest, solver_dir)
        first = analyze_private(args.private_root, args.reference_digest, args.candidate_digest)
        second = analyze_private(args.private_root, args.reference_digest, args.candidate_digest)
        if ev.encoded(first) != ev.encoded(second):
            raise ValueError("private analysis reproduction differs")
        sanitized = sanitize_private_summary(first)
        ev.write(args.public_summary, sanitized)
        return sanitized
    except BaseException as exc:
        marker = args.private_root / "INCOMPLETE.json"
        if not marker.exists():
            ev.write(marker, {"pilot_version": PILOT_VERSION, "complete": False,
                              "finished_utc": utc_now(), "failure": f"{type(exc).__name__}: {exc}"})
        raise


def render_report(ledger: list[dict[str, Any]], private: dict[str, Any] | None) -> str:
    winner = select_candidate(ledger)
    lines = ["# MLWE Optimization Pilot Report", "",
             f"Development experiments recorded: {len(ledger)}."]
    if winner:
        lines += [f"Selected public candidate: `{winner['experiment_id']}` at diagnostic score "
                  f"`{winner['diagnostic_score']:.6f}` (source `{winner['source_digest']}`)."]
    if private is None:
        lines += ["Final comparison: incomplete."]
    else:
        clean = sanitize_private_summary(private)
        lines += [f"Final classification: **{clean['outcome']}**.", "",
                  "The three predeclared candidate/reference score ratios were " +
                  ", ".join(f"`{p['candidate_reference_ratio']:.6f}`" for p in clean["pairs"]) + ".",
                  "Intervals and cell aggregates are preserved in the sanitized comparison JSON. "
                  "This is an initial stability check and does not establish statistical significance."]
    lines += ["", "Development scores are diagnostic and are separate from private-epoch rankings.",
              "The local runner assumes cooperative contestant code; the frozen container limits remain in force.", ""]
    return "\n".join(lines)


def report(args: argparse.Namespace) -> str:
    ledger = read_jsonl(args.ledger)
    private = ev.read(args.private_summary) if args.private_summary and args.private_summary.exists() else None
    text = render_report(ledger, private)
    if args.output:
        if args.output.exists():
            raise ValueError("report output already exists")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
    return text


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="mlwe_pilot.py")
    commands = result.add_subparsers(dest="command", required=True)
    dev = commands.add_parser("develop")
    dev.add_argument("--solver-dir", type=Path, required=True)
    dev.add_argument("--output", type=Path, required=True)
    dev.add_argument("--baseline-run", type=Path)
    dev.add_argument("--ledger", type=Path, required=True)
    dev.add_argument("--hypothesis", required=True)
    dev.add_argument("--mechanism", required=True)
    dev.add_argument("--parent-revision", required=True)
    dev.add_argument("--agent", default="codex")
    dev.add_argument("--model", required=True)
    dev.add_argument("--expected-source-digest")
    fin = commands.add_parser("final")
    fin.add_argument("--reference-dir", type=Path, required=True)
    fin.add_argument("--candidate-dir", type=Path, required=True)
    fin.add_argument("--reference-digest", required=True)
    fin.add_argument("--candidate-digest", required=True)
    fin.add_argument("--private-root", type=Path, required=True)
    fin.add_argument("--public-summary", type=Path, required=True)
    rep = commands.add_parser("report")
    rep.add_argument("--ledger", type=Path, required=True)
    rep.add_argument("--private-summary", type=Path)
    rep.add_argument("--output", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        value = {"develop": develop, "final": final, "report": report}[args.command](args)
        print(value if isinstance(value, str) else json.dumps(value, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"mlwe-pilot: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
