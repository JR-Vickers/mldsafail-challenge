"""Local, read-only dashboard for benchmark experiment history."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Iterable

from flask import Flask, abort, render_template


DEFAULT_RESULTS = Path(__file__).resolve().parents[3] / "results" / "experiments.jsonl"
METRICS = {
    "runtime": ("runtime_seconds", "total_wall_seconds", "wall_seconds"),
    "cost": ("abstract_cost", "total_abstract_cost", "cost"),
    "memory": ("peak_memory_bytes", "peak_memory_mb"),
    "quality": ("solution_quality", "quality"),
}


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


def load_experiments(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Read append-only JSONL, skipping malformed or non-object records."""
    if not path.exists():
        return [], 0
    records: list[dict[str, Any]] = []
    malformed = 0
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                malformed += 1
                continue
            if not isinstance(record, dict):
                malformed += 1
                continue
            records.append(record)
    records.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    return records, malformed


def pareto_frontier(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return correct records not dominated on their available core metrics."""
    eligible = [record for record in records if is_correct(record)]
    frontier: list[dict[str, Any]] = []
    for candidate in eligible:
        candidate_metrics = [metric(candidate, name) for name in METRICS]
        available = [index for index, value in enumerate(candidate_metrics) if value is not None]
        if not available:
            continue
        dominated = False
        for other in eligible:
            if other is candidate:
                continue
            other_metrics = [metric(other, name) for name in METRICS]
            comparable = [index for index in available if other_metrics[index] is not None]
            if comparable == available and all(
                other_metrics[index] <= candidate_metrics[index] for index in available
            ) and any(other_metrics[index] < candidate_metrics[index] for index in available):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return frontier


def _view_model(records: list[dict[str, Any]]) -> dict[str, Any]:
    correct = [record for record in records if is_correct(record)]
    chronological = list(reversed(records))
    best: dict[str, dict[str, Any] | None] = {}
    for name in METRICS:
        candidates = [record for record in correct if metric(record, name) is not None]
        best[name] = min(candidates, key=lambda record: metric(record, name)) if candidates else None

    baseline = next(
        (record for record in chronological if "baseline" in record.get("tags", []) or record.get("is_baseline")),
        correct[0] if correct else None,
    )
    current = best["runtime"] or (correct[0] if correct else None)
    improvement = None
    if baseline and current:
        before, after = metric(baseline, "runtime"), metric(current, "runtime")
        if before and after is not None:
            improvement = (before - after) / before * 100

    history = []
    runtimes = [metric(record, "runtime") for record in chronological if is_correct(record)]
    max_runtime = max((value for value in runtimes if value is not None), default=1)
    for index, record in enumerate(chronological):
        runtime = metric(record, "runtime")
        if is_correct(record) and runtime is not None:
            history.append({"record": record, "height": max(4, runtime / max_runtime * 100), "index": index})
    return {
        "records": records,
        "correct": correct,
        "best": best,
        "baseline": baseline,
        "current": current,
        "improvement": improvement,
        "frontier": pareto_frontier(records),
        "history": history,
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
