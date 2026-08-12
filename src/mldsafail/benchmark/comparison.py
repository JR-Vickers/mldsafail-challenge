"""Multi-metric comparison helpers for experiment records."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


METRICS = (
    "total_wall_seconds",
    "median_instance_seconds",
    "peak_memory_bytes",
    "abstract_cost",
    "solution_quality",
)


def aggregate_vector(record: Mapping[str, Any]) -> dict[str, float] | None:
    """Return a lower-is-better metric vector, or ``None`` for invalid runs."""

    if not record.get("correct"):
        return None
    aggregate = record.get("aggregate", {})
    try:
        vector = {metric: float(aggregate[metric]) for metric in METRICS}
    except (KeyError, TypeError, ValueError):
        return None
    return vector


def dominates(left: Mapping[str, float], right: Mapping[str, float]) -> bool:
    """Whether ``left`` is no worse everywhere and better somewhere."""

    return all(left[key] <= right[key] for key in METRICS) and any(
        left[key] < right[key] for key in METRICS
    )


def pareto_frontier(records: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    valid = [(record, aggregate_vector(record)) for record in records]
    scored = [(record, vector) for record, vector in valid if vector is not None]
    return [
        record
        for record, vector in scored
        if not any(other is not record and dominates(other_vector, vector) for other, other_vector in scored)
    ]


def best_per_metric(records: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    scored = [(record, aggregate_vector(record)) for record in records]
    valid = [(record, vector) for record, vector in scored if vector is not None]
    if not valid:
        return {}
    return {
        metric: min(valid, key=lambda pair: pair[1][metric])[0]
        for metric in METRICS
    }
