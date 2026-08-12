from __future__ import annotations

from mldsafail.benchmark.comparison import best_score_record, score_frontier
from mldsafail.benchmark.records import append_record, new_experiment_record
from mldsafail.web.app import comparison_cohort, create_app, load_experiments, scope_label


FULL_SCOPE = {
    "public": {"small": {}, "medium": {}, "large": {}},
    "hidden": {"small": {}, "medium": {}, "large": {}},
}


def _record(identifier, timestamp, score, *, correct=True, tags=None, suites=None, hypothesis=None):
    aggregate = {
        "score": score if correct else None,
        "abstract_cost": score if correct else None,
        "total_wall_seconds": score / 100,
        "median_instance_seconds": score / 1000,
        "peak_memory_bytes": 12_000_000,
        "solution_quality": 3,
    }
    record = new_experiment_record(
        benchmark_version="0.2.0", suites=suites or FULL_SCOPE, profiles={},
        aggregate=aggregate, correct=correct, score=score if correct else None,
        tags=tags or ["test"], hypothesis=hypothesis or identifier,
        command=["pytest"], resource_limits={"wall": 5, "memory": 67108864},
    )
    record.update(experiment_id=identifier, timestamp=timestamp)
    return record


def _write_log(path):
    records = (
        _record("baseline", "2026-01-01T00:00:00Z", 200, tags=["baseline"]),
        _record("best", "2026-01-02T00:00:00Z", 150, hypothesis="cache work"),
        _record("regression", "2026-01-03T00:00:00Z", 175),
        _record("invalid", "2026-01-04T00:00:00Z", 1, correct=False),
    )
    for record in records:
        append_record(record, path)
    return records


def test_dashboard_handles_missing_and_empty_results(tmp_path):
    for path in (tmp_path / "missing.jsonl", tmp_path / "empty.jsonl"):
        if path.name == "empty.jsonl":
            path.write_text("\n")
        response = create_app(path).test_client().get("/")
        assert response.status_code == 200
        assert b"No experiments yet" in response.data


def test_dashboard_ranks_and_plots_only_best_score_frontier(tmp_path):
    path = tmp_path / "experiments.jsonl"
    baseline, best, regression, invalid = _write_log(path)
    with path.open("a") as stream:
        stream.write("{broken}\n[]\n")
    records, malformed = load_experiments(path)
    assert malformed == 2
    assert best_score_record(records)["experiment_id"] == "best"
    assert [item["experiment_id"] for item in score_frontier(records)] == ["baseline", "best"]

    body = create_app(path).test_client().get("/").get_data(as_text=True)
    assert "25.0%" in body
    assert "Skipped 2 malformed experiment lines" in body
    frontier = body.split("Headline-score frontier", 1)[1].split("Research log", 1)[0]
    assert "/experiment/baseline" in frontier
    assert "/experiment/best" in frontier
    assert "/experiment/regression" not in frontier
    assert "/experiment/invalid" not in frontier


def test_comparison_prefers_full_scope_and_matching_fingerprint():
    smoke = _record("smoke", "2026-01-04", 1, suites={"public": {"small": {}}})
    old = _record("old", "2026-01-01", 90)
    baseline = _record("baseline", "2026-01-02", 100, tags=["baseline"])
    best = _record("best", "2026-01-03", 80)
    old["integrity"] = {"trusted_fingerprint": "old"}
    baseline["integrity"] = best["integrity"] = {"trusted_fingerprint": "current"}
    assert comparison_cohort([smoke, best, baseline, old]) == [best, baseline]
    assert scope_label(best) == "Full · large, medium, small"


def test_legacy_records_are_readable_but_unranked(tmp_path):
    path = tmp_path / "experiments.jsonl"
    legacy = _record("legacy", "2026-01-01", 10)
    legacy.update(schema_version="1")
    legacy.pop("score")
    legacy.pop("cost_model_version")
    legacy.pop("resource_limits")
    append_record(legacy, path)
    records, malformed = load_experiments(path)
    assert malformed == 0
    assert comparison_cohort(records) == []
    assert "No rankable scope" in create_app(path).test_client().get("/").get_data(as_text=True)


def test_detail_methodology_and_escaping(tmp_path):
    path = tmp_path / "experiments.jsonl"
    hostile = _record(
        "hostile", "2026-01-01", 10,
        hypothesis='<script>alert("owned")</script>',
    )
    append_record(hostile, path)
    client = create_app(path).test_client()
    detail = client.get("/experiment/hostile")
    assert detail.status_code == 200
    assert b'<script>alert("owned")</script>' not in detail.data
    assert b"&lt;script&gt;" in detail.data
    assert client.get("/experiment/unknown").status_code == 404
    assert b"never accepts external public keys" in client.get("/methodology").data
