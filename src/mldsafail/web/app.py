"""Local, read-only dashboard for benchmark experiment history."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from flask import Flask, abort, render_template

from mldsafail.benchmark.comparison import (
    aggregate_vector,
    best_per_metric,
    pareto_frontier as benchmark_pareto_frontier,
)
from mldsafail.benchmark.records import read_records


DEFAULT_RESULTS = Path(__file__).resolve().parents[3] / "results" / "experiments.jsonl"
METRICS = {
    "runtime": ("runtime_seconds", "total_wall_seconds", "wall_seconds"),
    "cost": ("abstract_cost", "total_abstract_cost", "cost"),
    "memory": ("peak_memory_bytes", "peak_memory_mb"),
    "quality": ("solution_quality", "quality"),
}

ScopeSignature = tuple[tuple[str, tuple[str, ...]], ...]


def _mapping(record: dict[str, Any]) -> dict[str, Any]:
    """Return aggregate metrics while accepting old and new record shapes."""
    for key in ("aggregate", "aggregate_metrics", "metrics", "summary"):
        value = record.get(key)
        if isinstance(value, dict):
            return record | value
    return record


def metric(record: dict[str, Any], name: str) -> float | None:
    values = _mapping(record)
    for key in METRICS[name]:
        value = values.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            if name == "memory" and key == "peak_memory_mb":
                return float(value) * 1024 * 1024
            return float(value)
        if name == "cost" and isinstance(value, dict):
            total = value.get("total")
            if isinstance(total, (int, float)) and not isinstance(total, bool):
                return float(total)
    return None


def is_correct(record: dict[str, Any]) -> bool:
    value = record.get("correct", record.get("valid"))
    if value is None:
        profiles = record.get("profiles")
        if isinstance(profiles, dict) and profiles:
            return all(bool(item.get("correct")) for item in profiles.values() if isinstance(item, dict))
    return value is True


def scope_signature(record: dict[str, Any]) -> ScopeSignature:
    """Return a deterministic suite/profile signature for fair comparisons."""
    suites = record.get("suites")
    if isinstance(suites, dict) and suites:
        return tuple(
            sorted(
                (
                    str(suite),
                    tuple(sorted(str(profile) for profile in profiles))
                    if isinstance(profiles, dict)
                    else (),
                )
                for suite, profiles in suites.items()
            )
        )
    profiles = record.get("profiles")
    names = tuple(sorted(str(profile) for profile in profiles)) if isinstance(profiles, dict) else ()
    return (("unspecified", names),)


def _is_full_scope(signature: ScopeSignature) -> bool:
    suites = {suite for suite, _profiles in signature}
    profile_scopes = {profiles for _suite, profiles in signature}
    return suites == {"public", "hidden"} and len(profile_scopes) == 1


def scope_label(record: dict[str, Any]) -> str:
    signature = scope_signature(record)
    suites = {suite for suite, _profiles in signature}
    profiles = sorted({profile for _suite, names in signature for profile in names})
    if _is_full_scope(signature):
        prefix = "Full"
    elif len(suites) == 1:
        prefix = next(iter(suites)).replace("_", " ").title()
    else:
        prefix = " + ".join(suite.replace("_", " ").title() for suite in sorted(suites))
    return f"{prefix} · {', '.join(profiles)}" if profiles else prefix


def comparison_cohort(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select rankable records with one comparable deterministic scope."""
    ranked = [record for record in records if aggregate_vector(record) is not None]
    if not ranked:
        return []
    signatures = {scope_signature(record) for record in ranked}
    full_scopes = [signature for signature in signatures if _is_full_scope(signature)]
    if full_scopes:
        selected = max(
            full_scopes,
            key=lambda signature: (
                sum(len(profiles) for _suite, profiles in signature),
                sum(scope_signature(record) == signature for record in ranked),
                signature,
            ),
        )
    else:
        # Records arrive newest first; anchor the fallback cohort to the latest
        # rankable result while requiring all comparisons to share its scope.
        selected = scope_signature(ranked[0])
    return [record for record in ranked if scope_signature(record) == selected]


def load_experiments(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Read append-only JSONL, skipping malformed or non-object records."""
    if not path.exists():
        return [], 0
    # Use the benchmark's canonical tolerant reader. Counting non-empty lines
    # separately lets the UI report skipped records without duplicating parsing.
    nonempty_lines = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    records = read_records(path)
    malformed = nonempty_lines - len(records)
    records.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    return records, malformed


def _view_model(records: list[dict[str, Any]]) -> dict[str, Any]:
    correct = [record for record in records if is_correct(record)]
    cohort = comparison_cohort(records)
    chronological = list(reversed(cohort))
    canonical_best = best_per_metric(cohort)
    best = {
        "runtime": canonical_best.get("total_wall_seconds"),
        "cost": canonical_best.get("abstract_cost"),
        "memory": canonical_best.get("peak_memory_bytes"),
        "quality": canonical_best.get("solution_quality"),
    }

    baseline = next(
        (record for record in chronological if "baseline" in record.get("tags", []) or record.get("is_baseline")),
        chronological[0] if chronological else None,
    )
    current = best["runtime"] or (correct[0] if correct else None)
    improvement = None
    if baseline and current:
        before, after = metric(baseline, "runtime"), metric(current, "runtime")
        if before and after is not None:
            improvement = (before - after) / before * 100

    history = []
    runtimes = [metric(record, "runtime") for record in chronological]
    max_runtime = max((value for value in runtimes if value is not None), default=1)
    for index, record in enumerate(chronological):
        runtime = metric(record, "runtime")
        if runtime is not None:
            history.append({"record": record, "height": max(4, runtime / max_runtime * 100), "index": index})
    return {
        "records": records,
        "correct": correct,
        "best": best,
        "baseline": baseline,
        "current": current,
        "improvement": improvement,
        "frontier": benchmark_pareto_frontier(cohort),
        "history": history,
        "comparison_scope": scope_label(cohort[0]) if cohort else "No rankable scope",
    }


def create_app(results_path: str | Path | None = None) -> Flask:
    app = Flask(__name__)
    configured = results_path or os.environ.get("MLDSAFAIL_RESULTS_PATH") or DEFAULT_RESULTS
    app.config["RESULTS_PATH"] = Path(configured)

    @app.template_filter("metric")
    def metric_filter(record: dict[str, Any] | None, name: str) -> str:
        if not record:
            return "—"
        value = metric(record, name)
        if value is None:
            return "—"
        if name == "runtime":
            return f"{value:.4f} s"
        if name == "memory":
            return f"{value / (1024 * 1024):.1f} MiB"
        if name in {"cost", "quality"}:
            return f"{value:,.0f}"
        return str(value)

    app.add_template_filter(scope_label, "scope")

    @app.get("/")
    def index():
        records, malformed = load_experiments(app.config["RESULTS_PATH"])
        return render_template("index.html", malformed=malformed, **_view_model(records))

    @app.get("/experiment/<experiment_id>")
    def experiment(experiment_id: str):
        records, malformed = load_experiments(app.config["RESULTS_PATH"])
        record = next(
            (item for item in records if str(item.get("experiment_id", item.get("id", ""))) == experiment_id),
            None,
        )
        if record is None:
            abort(404)
        return render_template("experiment.html", record=record, malformed=malformed)

    @app.get("/methodology")
    def methodology():
        return render_template("methodology.html")

    return app


def main() -> None:
    create_app().run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
