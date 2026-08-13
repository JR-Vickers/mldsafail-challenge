"""Application factory for the offline dashboard and hosted challenge."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, render_template

from mldsafail.benchmark.comparison import (
    best_score_record,
    improvement_percent,
    rankable_score,
    score_delta,
    score_frontier,
)
from mldsafail.benchmark.records import read_records
from mldsafail.web.config import load_config
from mldsafail.web.db import get_session, init_database
from mldsafail.web.repositories import DatabaseResultRepository, JsonlResultRepository


DEFAULT_RESULTS = Path(__file__).resolve().parents[3] / "results" / "experiments.jsonl"
METRICS = {
    "score": ("score",),
    "runtime": ("runtime_seconds", "total_wall_seconds", "wall_seconds"),
    "cost": ("abstract_cost", "total_abstract_cost", "cost"),
    "memory": ("peak_memory_bytes", "peak_memory_mb"),
    "quality": ("solution_quality", "quality"),
}

ScopeSignature = tuple[tuple[str, tuple[str, ...]], ...]
ComparisonSignature = tuple[ScopeSignature, str, str, str]


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
    return (
        suites == {"public", "hidden"}
        and profile_scopes == {("large", "medium", "small")}
    )


def _comparison_signature(record: dict[str, Any]) -> ComparisonSignature:
    integrity = record.get("integrity")
    fingerprint = integrity.get("trusted_fingerprint") if isinstance(integrity, dict) else None
    return (
        scope_signature(record),
        str(record.get("benchmark_version", "legacy")),
        # Hosted records use a storage envelope, but the benchmark contract is
        # still identified by benchmark version and evaluator fingerprint.
        "2" if record.get("schema_version") == "hosted-1" else str(record.get("schema_version", "legacy")),
        str(fingerprint or "legacy"),
    )


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
    ranked = [
        record for record in records
        if rankable_score(record) is not None and _is_full_scope(scope_signature(record))
    ]
    if not ranked:
        return []
    # Records arrive newest first. Versions, scope, and fingerprints prevent
    # different benchmark contracts from being compared.
    anchor = ranked[0]
    selected = _comparison_signature(anchor)
    return [record for record in ranked if _comparison_signature(record) == selected]


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
    current = best_score_record(cohort)

    baseline = next(
        (record for record in chronological if "baseline" in record.get("tags", []) or record.get("is_baseline")),
        chronological[0] if chronological else None,
    )
    improvement = improvement_percent(current, baseline) if baseline and current else None

    history = []
    frontier = score_frontier(cohort)
    scores = [rankable_score(record) for record in frontier]
    max_score = max((value for value in scores if value is not None), default=1)
    for index, record in enumerate(frontier):
        score = rankable_score(record)
        if score is not None:
            history.append({
                "record": record,
                "height": max(4, score / max_score * 100),
                "index": index,
                "delta": score_delta(record, baseline) if baseline else None,
            })
    return {
        "records": records,
        "correct": correct,
        "baseline": baseline,
        "current": current,
        "improvement": improvement,
        "frontier": frontier,
        "history": history,
        "comparison_scope": scope_label(cohort[0]) if cohort else "No rankable scope",
    }


def create_app(
    results_path: str | Path | None = None,
    *,
    config_name: str | None = None,
    config: dict[str, Any] | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(load_config(config_name))
    if config:
        app.config.update(config)
    configured = results_path or os.environ.get("MLDSAFAIL_RESULTS_PATH") or DEFAULT_RESULTS
    app.config["RESULTS_PATH"] = Path(configured)
    app.config["PERMANENT_SESSION_LIFETIME"] = app.config.pop("PERMANENT_SESSION_LIFETIME_SECONDS")
    init_database(app)

    def result_repository():
        if app.config.get("DATABASE_URL"):
            return DatabaseResultRepository(get_session())
        return JsonlResultRepository(app.config["RESULTS_PATH"])

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
        if name in {"score", "cost", "quality"}:
            return f"{value:,.0f}"
        return str(value)

    app.add_template_filter(scope_label, "scope")

    @app.get("/")
    def index():
        records, malformed = result_repository().records()
        return render_template("index.html", malformed=malformed, **_view_model(records))

    @app.get("/experiment/<experiment_id>")
    def experiment(experiment_id: str):
        records, malformed = result_repository().records()
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

    @app.get("/health/live")
    def health_live():
        return jsonify(status="ok")

    @app.get("/health/ready")
    def health_ready():
        if app.config.get("DATABASE_URL"):
            from sqlalchemy import text
            get_session().execute(text("SELECT 1"))
        return jsonify(status="ready")

    return app


def main() -> None:
    create_app().run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
