"""Descriptive analysis of complete, independently audited cohorts; no selection claims."""

from __future__ import annotations

import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .audit import audited_records
from .runner import DEFAULT_RESULTS
from .worker import classify_result


def _median(values):
    usable = [value for value in values if value is not None]
    return statistics.median(usable) if usable else None


def _fmt(value, digits=4):
    return "n/a" if value is None else f"{value:.{digits}f}"


def _quality(record, key):
    return _median(r.get("verification", {}).get(key) for r in record["repetitions"]
                   if r.get("verification", {}).get("verified"))


def _status(record):
    statuses = {classify_result(r) for r in record["repetitions"]}
    return next(iter(statuses)) if len(statuses) == 1 else "mixed"


def _bootstrap(observations, statistic=statistics.mean):
    """Percentile interval on one value per seed; never resample timing repetitions."""
    if len(observations) < 2:
        return None
    rng = random.Random("primitive-selection-seed-bootstrap-v2")
    n = len(observations)
    distribution = sorted(statistic(rng.choices(observations, k=n)) for _ in range(2000))
    return distribution[49], distribution[1949]


def _interval_text(interval, percent=False):
    if interval is None:
        return "n/a"
    return (f"[{interval[0]:.1%}, {interval[1]:.1%}]" if percent
            else f"[{interval[0]:.6f}, {interval[1]:.6f}]")


def _seed_values(records, function):
    clustered = defaultdict(list)
    for record in records:
        value = function(record)
        if value is not None:
            clustered[(record["profile"], record["seed"])].append(value)
    return [statistics.mean(values) for _, values in sorted(clustered.items())]


def summarize(records: list[dict[str, Any]], keys=("track", "solver")):
    groups = defaultdict(list)
    for record in records:
        groups[tuple(record.get(key) for key in keys)].append(record)
    rows = []
    for group, values in sorted(groups.items(), key=lambda item: str(item[0])):
        successful = [value for value in values if value["verification_result"]]
        rates = _seed_values(values, lambda r: int(r["verification_result"]))
        row = dict(zip(keys, group, strict=True))
        statuses = Counter(_status(value) for value in values)
        row.update({"cases": len(values), "seed_clusters": len(rates), "statuses": statuses,
                    "success_rate": statistics.mean(rates), "success_interval": _bootstrap(rates),
                    "median_cpu": _median(value["median_cpu_seconds"] for value in successful),
                    "cpu_interval": _bootstrap(_seed_values(successful, lambda r: r["median_cpu_seconds"]), statistics.median),
                    "peak_rss": max(value["peak_rss_bytes"] for value in values),
                    "median_norm_squared": _median(_quality(value, "norm_squared") for value in successful),
                    "median_rhf": _median(_quality(value, "root_hermite_factor") for value in successful),
                    "norm_interval": _bootstrap(_seed_values(successful, lambda r: _quality(r, "norm_squared")), statistics.median),
                    "rhf_interval": _bootstrap(_seed_values(successful, lambda r: _quality(r, "root_hermite_factor")), statistics.median)})
        rows.append(row)
    return rows


def reduction_share(record):
    # Include the whole timed invocation, including verification and uninstrumented overhead.
    return _median(r.get("phase_cpu_seconds", {}).get("reduction", 0.0) / r["cpu_seconds"]
                   for r in record["repetitions"] if r.get("verification", {}).get("verified") and r.get("cpu_seconds"))


def _paired_gains(records, track, baseline, challenger):
    def key(record):
        return record["profile"], record["eta"], record["seed"], record.get("source_track")
    old = {key(r): r for r in records if r["track"] == track and r["solver"] == baseline}
    new = {key(r): r for r in records if r["track"] == track and r["solver"] == challenger}
    groups = defaultdict(list)
    for case_key in old.keys() | new.keys():
        groups[(case_key[0], case_key[1])].append((case_key, old.get(case_key), new.get(case_key)))
    rows = []
    for (profile, eta), pairs in sorted(groups.items()):
        gains, quality_deltas = [], []
        for _, left, right in pairs:
            if not left or not right or not left["verification_result"] or not right["verification_result"]:
                continue
            if left["median_cpu_seconds"] and right["median_cpu_seconds"]:
                gains.append(1 - right["median_cpu_seconds"] / left["median_cpu_seconds"])
            lq, rq = _quality(left, "norm_squared"), _quality(right, "norm_squared")
            if lq is not None and rq is not None:
                quality_deltas.append(rq - lq)
        rows.append((profile, eta, len(pairs), len(gains), _median(gains), _bootstrap(gains, statistics.median),
                     _median(quality_deltas)))
    return rows


def render(records: list[dict[str, Any]], cohort: str) -> str:
    lines = [f"# Primitive-selection {cohort} audited report", "",
             "Generated from complete raw cohorts after input regeneration, independent candidate verification, and aggregate checks.", "",
             "Intervals are deterministic 95% percentile bootstrap intervals (2,000 resamples) over seed-level observations; three timing repetitions are one instance, not three. Zero-width bootstrap intervals at 0%/100% are empirical resampling limits, not proof of population certainty. Small samples limit inference. Cross-track quality has no common score.", "",
             "Successful timing uses the median measured process CPU; each process includes solver work and independent verification but excludes interpreter startup. Parent wall timing includes startup. Quality is reduced to a median per seed before summary. `n/a` means no usable observations; the outcome table supplies the reason.", ""]
    cohorts = defaultdict(list)
    for record in records:
        cohorts[(record["study_version"], record["cohort"], record.get("run_id", "legacy"))].append(record)
    for (version, name, identity), values in sorted(cohorts.items()):
        lines += [f"## {version} / {name} / {identity}", "",
                  "| Track/source | Solver | Profile/eta | Cases | Seed clusters | Success (95% CI) | Successful median CPU (95% CI), s | Peak RSS MiB |",
                  "|---|---|---|---:|---:|---|---|---:|"]
        keys = ("track", "source_track", "solver", "profile", "eta")
        for row in summarize(values, keys):
            lines.append(f"| {row['track']}/{row['source_track'] or '-'} | {row['solver']} | {row['profile']}/{row['eta']} | "
                         f"{row['cases']} | {row['seed_clusters']} | {row['success_rate']:.1%} {_interval_text(row['success_interval'], True)} | "
                         f"{_fmt(row['median_cpu'], 6)} {_interval_text(row['cpu_interval'])} | {row['peak_rss']/1024**2:.1f} |")
        lines += ["", "### Every case outcome", "",
                  "Applicability caps are declared omissions, not measured algorithmic failures. Signals alone are crashes, not evidence of a memory limit. A mixed case has different outcomes across repetitions; its repetitions remain in the raw record. Warmups are retained and independently checked but do not enter timing summaries.", "",
                  "| Track | Solver | Cases | Success | Cap | Timeout | Memory | Crash | Invalid | No candidate | Mixed |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for row in summarize(values):
            counts = row["statuses"]
            lines.append(f"| {row['track']} | {row['solver']} | {row['cases']} | " + " | ".join(str(counts[key]) for key in
                         ("success", "applicability_cap", "timeout", "memory_failure", "crash", "invalid_answer", "no_candidate", "mixed")) + " |")
        lines += ["", "### Quality and complete-process reduction share", "",
                  "Reduction share divides instrumented reduction CPU by complete measured process CPU, including verification and overhead. A large share establishes runtime consumption only. It does not establish an end-to-end gain from improving reduction.", "",
                  "| Track/source | Solver | Profile/eta | Median norm² (95% CI) | Median RHF (95% CI) | Reduction share (95% CI) |",
                  "|---|---|---|---|---|---|"]
        for row in summarize(values, keys):
            matching = [r for r in values if all(r.get(k) == row[k] for k in keys) and r["verification_result"]]
            shares = _seed_values(matching, reduction_share)
            lines.append(f"| {row['track']}/{row['source_track'] or '-'} | {row['solver']} | {row['profile']}/{row['eta']} | "
                         f"{_fmt(row['median_norm_squared'], 1)} {_interval_text(row['norm_interval'])} | "
                         f"{_fmt(row['median_rhf'], 6)} {_interval_text(row['rhf_interval'])} | "
                         f"{_fmt(_median(shares), 6)} {_interval_text(_bootstrap(shares, statistics.median), True)} |")
        lines += ["", "### Paired complete-solver comparisons", "",
                  "Positive gains mean lower complete CPU on cases solved by both methods. All eligible pair counts are shown, including unsolved pairs. Conditioning on joint success can bias timing comparisons; failure and quality columns must be considered. These strategy comparisons do not isolate a causal reduction-only change.", "",
                  "| Track | Comparison | Profile/eta | All pairs | Joint successes | Median CPU gain (95% CI) | Median norm² change |",
                  "|---|---|---|---:|---:|---|---:|"]
        for track, old, new in (("mlwe", "primal-lll", "primal-bkz"), ("msis", "lll-short-vector", "progressive-bkz")):
            for profile, eta, total, count, gain, interval, delta in _paired_gains(values, track, old, new):
                lines.append(f"| {track} | {new} / {old} | {profile}/{eta} | {total} | {count} | "
                             f"{'n/a' if gain is None else f'{gain:.1%}'} {_interval_text(interval, True)} | {_fmt(delta, 1)} |")
    lines += ["", "## Study decision", "",
              "This report computes descriptive evidence only. Eligibility, scientific gates, primitive selection, and agent approval must be recorded separately under the committed freeze. Neither a complete cohort nor high reduction share waives a failed gate.", ""]
    return "\n".join(lines)


def generate(input_paths: list[Path] | None = None, output: Path | None = None) -> Path:
    paths = input_paths or [DEFAULT_RESULTS / "development.jsonl"]
    records = audited_records(paths)
    output = output or DEFAULT_RESULTS / "REPORT-AUDITED.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(records, "+".join(sorted({r["cohort"] for r in records}))))
    return output
