"""Generate auditable Markdown analysis directly from raw JSONL records."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .runner import DEFAULT_RESULTS


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _median(values):
    usable = [x for x in values if x is not None]
    return statistics.median(usable) if usable else None


def _fmt(value, digits=4):
    return "n/a" if value is None else f"{value:.{digits}f}"


def summarize(records: list[dict[str, Any]], keys=("track", "solver")) -> list[dict[str, Any]]:
    groups = defaultdict(list)
    for record in records:
        groups[tuple(record[key] for key in keys)].append(record)
    rows = []
    for group, values in sorted(groups.items()):
        successful = [v for v in values if v["verification_result"]]
        row = {key: value for key, value in zip(keys, group, strict=True)}
        row.update({
            "cases": len(values),
            "success_rate": sum(bool(v["verification_result"]) for v in values) / len(values),
            "median_cpu": _median(v["median_cpu_seconds"] for v in successful),
            "peak_rss": max(v["peak_rss_bytes"] for v in values),
            "median_norm_squared": _median(v.get("answer_quality", {}).get("norm_squared") for v in successful),
            "best_norm_squared": min((v.get("answer_quality", {}).get("norm_squared") for v in successful
                                       if v.get("answer_quality", {}).get("norm_squared") is not None), default=None),
            "median_rhf": _median(v.get("answer_quality", {}).get("root_hermite_factor") for v in successful),
        })
        rows.append(row)
    return rows


def _kernel_evidence(records):
    result = []
    for track, solver in (("mlwe", "primal-bkz"), ("mlwe", "hybrid-bdd"),
                          ("msis", "progressive-bkz"), ("msis", "restart-bkz")):
        values = [r for r in records if r["track"] == track and r["solver"] == solver
                  and r["verification_result"]]
        shares = []
        for value in values:
            phases = value.get("phase_cpu_seconds", {})
            total = sum(phases.values())
            if total:
                shares.append(phases.get("reduction", 0.0) / total)
        result.append((track, solver, _median(shares), len(values)))
    return result


def _paired_gains(records, track, baseline, challenger):
    def key(record):
        return record["profile"], record["eta"], record["seed"], record.get("source_track")

    old = {key(r): r for r in records if r["track"] == track and r["solver"] == baseline
           and r["verification_result"]}
    new = {key(r): r for r in records if r["track"] == track and r["solver"] == challenger
           and r["verification_result"]}
    by_profile = defaultdict(list)
    for case_key in old.keys() & new.keys():
        old_cpu, new_cpu = old[case_key]["median_cpu_seconds"], new[case_key]["median_cpu_seconds"]
        if old_cpu and new_cpu:
            by_profile[case_key[0]].append(1 - new_cpu / old_cpu)
    return [(profile, _median(gains), len(gains)) for profile, gains in sorted(by_profile.items())]


def render(records: list[dict[str, Any]], cohort: str) -> str:
    rows = summarize(records)
    lines = [f"# Primitive-selection {cohort} report", "",
             "Generated only from the committed JSONL records by `primitive-study report`.", "",
             "| Track | Solver | Cases | Success | Median successful CPU (s) | Peak RSS (MiB) | Median norm² | Median RHF |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['track']} | {row['solver']} | {row['cases']} | {row['success_rate']:.1%} | "
                     f"{_fmt(row['median_cpu'], 6)} | {row['peak_rss'] / 1024**2:.1f} | "
                     f"{_fmt(row['median_norm_squared'], 1)} | {_fmt(row['median_rhf'], 6)} |")
    lines += ["", "## Scaling by profile", "",
              "CPU medians include verified cases only; `n/a` means that the family reached its declared difficulty cap.", "",
              "| Track | Solver | Profile | Cases | Success | Median CPU (s) | Peak RSS (MiB) |",
              "|---|---|---|---:|---:|---:|---:|"]
    for row in summarize(records, ("track", "solver", "profile")):
        lines.append(f"| {row['track']} | {row['solver']} | {row['profile']} | {row['cases']} | "
                     f"{row['success_rate']:.1%} | {_fmt(row['median_cpu'], 6)} | {row['peak_rss'] / 1024**2:.1f} |")
    lines += ["", "## Module-SIS quality at the fixed budget", "",
              "| Solver | Profile | Success | Best verified norm² | Median verified norm² |",
              "|---|---|---:|---:|---:|"]
    for row in summarize([r for r in records if r["track"] == "msis"], ("solver", "profile")):
        lines.append(f"| {row['solver']} | {row['profile']} | {row['success_rate']:.1%} | "
                     f"{_fmt(row['best_norm_squared'], 1)} | {_fmt(row['median_norm_squared'], 1)} |")
    lines += ["", "## Derived-basis quality against resources", "",
              "| Source | Solver | Profile | Success | Median CPU (s) | Peak RSS (MiB) | Median RHF |",
              "|---|---|---|---:|---:|---:|---:|"]
    for row in summarize([r for r in records if r["track"] == "bkz"],
                         ("source_track", "solver", "profile")):
        lines.append(f"| {row['source_track']} | {row['solver']} | {row['profile']} | "
                     f"{row['success_rate']:.1%} | {_fmt(row['median_cpu'], 6)} | "
                     f"{row['peak_rss'] / 1024**2:.1f} | {_fmt(row['median_rhf'], 6)} |")
    lines += ["", "## Reduction share in end-to-end solvers", "",
              "| Track | Solver | Median reduction share | Verified cases |", "|---|---|---:|---:|"]
    kernel = _kernel_evidence(records)
    for track, solver, share, cases in kernel:
        lines.append(f"| {track} | {solver} | {'n/a' if share is None else f'{share:.1%}'} | {cases} |")
    lines += ["", "## Paired kernel substitutions", "",
              "Positive values are end-to-end CPU gains from replacing the LLL kernel with the BKZ strategy on the same verified case.", "",
              "| Track | Comparison | Profile | Paired cases | Median gain |", "|---|---|---|---:|---:|"]
    comparisons = (("mlwe", "primal-lll", "primal-bkz"),
                   ("msis", "lll-short-vector", "progressive-bkz"))
    for track, baseline, challenger in comparisons:
        for profile, gain, count in _paired_gains(records, track, baseline, challenger):
            lines.append(f"| {track} | {challenger} vs {baseline} | {profile} | {count} | {gain:.1%} |")
    validation = [r for r in records if r["cohort"] == "validation"]
    qualifying = [(track, solver, share) for track, solver, share, cases in kernel
                  if share is not None and share >= .70 and cases]
    lines += ["", "## Decision-rule status", ""]
    if not validation:
        lines.append("The development data meet the 70% reduction-share gate in multiple end-to-end families, but the paired substitutions do not establish a 20% gain at two sizes. No recommendation is frozen: validation results from a post-freeze reviewer nonce and agent specialist-review approval are absent.")
    elif len(qualifying) < 2:
        lines.append("BKZ/block-SVP does not satisfy the 70% dominance gate in two materially different solvers; compare MLWE and MSIS with the weighted rubric.")
    else:
        lines.append("The dominance gate is met, but a separately measured kernel improvement must still show at least 20% end-to-end validation gain at two sizes.")
    image_digests = {r.get("container_image_digest") for r in records}
    if image_digests == {"unavailable"}:
        measurement_note = "The development run used exact local Python pins and records its image digest as `unavailable`; validation must run in the pinned container."
    else:
        measurement_note = "The development run was executed in the digest-pinned container; validation must use a fresh reviewer nonce after the freeze."
    lines += ["", "## Negative results and limitations", "",
              "- Exhaustive MLWE is deliberately limited to the committed tiny fixture; the exploratory grid is beyond its search cap.",
              "- Hybrid MLWE is tractable only at the small profile. Primal LLL/BKZ also solve medium/eta=1, but medium/eta=2 and large exceed the frozen applicability limit.",
              "- All three Module-SIS families verify on small, while seed-dependent enumeration made medium and large unsuitable for the fixed budget.",
              "- Derived-basis reduction verifies at small and medium; large derived bases exceed the frozen dimension limit.",
              f"- {measurement_note}",
              "", "## Integrity notes", "",
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
