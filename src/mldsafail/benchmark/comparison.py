"""Canonical single-score comparison helpers for experiment records."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any


def rankable_score(record: Mapping[str, Any]) -> int | None:
    """Return a valid version-2 headline score, otherwise ``None``."""

    if record.get("schema_version") not in {"2", "hosted-1"} or record.get("correct") is not True:
        return None
    value = record.get("score")
    aggregate = record.get("aggregate")
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or not isinstance(aggregate, Mapping)
        or aggregate.get("score") != value
    ):
        return None
    return value


def _tie_key(record: Mapping[str, Any]) -> tuple[int, str, str]:
    score = rankable_score(record)
    if score is None:
        raise ValueError("record is not rankable")
    return score, str(record.get("timestamp", "")), str(record.get("experiment_id", ""))


def best_score_record(records: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    rankable = [record for record in records if rankable_score(record) is not None]
    return min(rankable, key=_tie_key) if rankable else None


def score_frontier(records: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Return chronological records that established a strictly lower score."""

    ordered = sorted(
        (record for record in records if rankable_score(record) is not None),
        key=lambda record: (str(record.get("timestamp", "")), str(record.get("experiment_id", ""))),
    )
    frontier: list[Mapping[str, Any]] = []
    best = math.inf
    for record in ordered:
        score = rankable_score(record)
        assert score is not None
        if score < best:
            frontier.append(record)
            best = score
    return frontier


def score_delta(record: Mapping[str, Any], baseline: Mapping[str, Any]) -> int | None:
    current, starting = rankable_score(record), rankable_score(baseline)
    return None if current is None or starting is None else current - starting


def improvement_percent(record: Mapping[str, Any], baseline: Mapping[str, Any]) -> float | None:
    current, starting = rankable_score(record), rankable_score(baseline)
    if current is None or starting in (None, 0):
        return None
    return (starting - current) / starting * 100
