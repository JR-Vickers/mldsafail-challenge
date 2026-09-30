"""Hosted ratio scores alongside unchanged historical integer scoring."""
import math
from mldsafail.benchmark.comparison import rankable_score as historical_score


def rankable_score(record):
    if record.get("benchmark_version") != "0.5.0":
        return historical_score(record)
    value = record.get("score")
    if (record.get("schema_version") != "hosted-mlwe-1" or record.get("correct") is not True
            or type(value) not in (int, float) or not math.isfinite(value) or value <= 0
            or record.get("aggregate", {}).get("score") != value):
        return None
    return value


def best_score_record(records):
    ranked = [r for r in records if rankable_score(r) is not None]
    return min(ranked, key=lambda r: (rankable_score(r), str(r.get("timestamp", "")),
                                      str(r.get("experiment_id", "")))) if ranked else None


def score_frontier(records):
    result, best = [], math.inf
    for record in sorted(records, key=lambda r: (str(r.get("timestamp", "")), str(r.get("experiment_id", "")))):
        score = rankable_score(record)
        if score is not None and score < best:
            result.append(record)
            best = score
    return result


def score_delta(record, baseline):
    current, starting = rankable_score(record), rankable_score(baseline)
    return None if current is None or starting is None else current - starting


def improvement_percent(record, baseline):
    current, starting = rankable_score(record), rankable_score(baseline)
    return None if current is None or starting in (None, 0) else (starting - current) / starting * 100
