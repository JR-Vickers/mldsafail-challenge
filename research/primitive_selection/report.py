"""Generate auditable Markdown analysis directly from raw JSONL records."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .runner import DEFAULT_RESULTS, ROOT


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _median(values):
    usable = [x for x in values if x is not None]
    return statistics.median(usable) if usable else None


def _fmt(value, digits=4):
    return "n/a" if value is None else f"{value:.{digits}f}"


def summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = defaultdict(list)
    for record in records:
        groups[(record["track"], record["solver"])].append(record)
    rows = []
    for (track, solver), values in sorted(groups.items()):
        rows.append({
            "track": track, "solver": solver, "cases": len(values),
            "success_rate": sum(bool(v["verification_result"]) for v in values) / len(values),
            "median_cpu": _median(v["median_cpu_seconds"] for v in values),
            "peak_rss": max(v["peak_rss_bytes"] for v in values),
            "median_norm_squared": _median(v.get("answer_quality", {}).get("norm_squared") for v in values
                                           if v["verification_result"]),
            "median_rhf": _median(v.get("answer_quality", {}).get("root_hermite_factor") for v in values
                                  if v["verification_result"]),
        })
    return rows


def _kernel_evidence(records):
    result = []
    for solver in ("primal-bkz", "hybrid-bdd", "progressive-bkz", "restart-bkz"):
        values = [r for r in records if r["solver"] == solver and r["verification_result"]]
        shares = []
        for value in values:
            phases = value.get("phase_cpu_seconds", {})
            total = sum(phases.values())
            if total:
                shares.append(phases.get("reduction", 0.0) / total)
        result.append((solver, _median(shares), len(values)))
    return result


def render(records: list[dict[str, Any]], cohort: str) -> str:
    rows = summarize(records)
    lines = [f"# Primitive-selection {cohort} report", "",
             "Generated only from the committed JSONL records by `primitive-study report`.", "",
             "| Track | Solver | Cases | Success | Median CPU (s) | Peak RSS (MiB) | Median norm² | Median RHF |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['track']} | {row['solver']} | {row['cases']} | {row['success_rate']:.1%} | "
                     f"{_fmt(row['median_cpu'], 6)} | {row['peak_rss'] / 1024**2:.1f} | "
                     f"{_fmt(row['median_norm_squared'], 1)} | {_fmt(row['median_rhf'], 6)} |")
    lines += ["", "## Reduction share in end-to-end solvers", "",
              "| Solver | Median reduction share | Verified cases |", "|---|---:|---:|"]
    kernel = _kernel_evidence(records)
    for solver, share, cases in kernel:
        lines.append(f"| {solver} | {'n/a' if share is None else f'{share:.1%}'} | {cases} |")
    validation = [r for r in records if r["cohort"] == "validation"]
    qualifying = [(solver, share) for solver, share, cases in kernel if share is not None and share >= .70 and cases]
    lines += ["", "## Decision-rule status", ""]
    if not validation:
        lines.append("No recommendation is frozen: validation results from a post-freeze reviewer nonce are absent.")
    elif len(qualifying) < 2:
        lines.append("BKZ/block-SVP does not satisfy the 70% dominance gate in two materially different solvers; compare MLWE and MSIS with the weighted rubric.")
    else:
        lines.append("The dominance gate is met, but a separately measured kernel improvement must still show at least 20% end-to-end validation gain at two sizes.")
    lines += ["", "## Integrity notes", "",
              "Times, memory, correctness, and quality remain separate; no cross-track synthetic score is computed.",
              "The cooperative Benchmark 0.4.0 `OperationMeter` is not imported or used.", ""]
    return "\n".join(lines)


def generate(input_paths: list[Path] | None = None, output: Path | None = None) -> Path:
    paths = input_paths or [DEFAULT_RESULTS / "development.jsonl", DEFAULT_RESULTS / "validation.jsonl"]
    records = [record for path in paths for record in _load(path)]
    if not records:
        raise ValueError("no raw study results found")
    cohorts = "+".join(sorted({r["cohort"] for r in records}))
    output = output or DEFAULT_RESULTS / "REPORT.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(records, cohorts))
    return output
