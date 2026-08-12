from __future__ import annotations

from mldsafail.benchmark.comparison import best_per_metric, pareto_frontier
from mldsafail.benchmark.records import append_record, new_experiment_record
from mldsafail.web.app import comparison_cohort, create_app, load_experiments, scope_label


def _record(
    identifier: str,
    timestamp: str,
    values,
    *,
    correct=True,
    tags=None,
    hypothesis=None,
    suites=None,
):
    record = new_experiment_record(
        benchmark_version="test",
        suites=suites if suites is not None else {"public": {}},
        profiles={},
        aggregate=values,
        correct=correct,
        tags=tags or ["test"],
        hypothesis=hypothesis or f"hypothesis for {identifier}",
        command=["pytest"],
    )
    record.update(experiment_id=identifier, timestamp=timestamp)
    return record


def _metrics(runtime, median, memory, cost, quality):
    return {
        "total_wall_seconds": runtime,
        "median_instance_seconds": median,
        "peak_memory_bytes": memory,
        "abstract_cost": cost,
        "solution_quality": quality,
    }


def _write_mixed_log(path):
    baseline = _record(
        "baseline", "2026-01-01T00:00:00Z", _metrics(2, 1, 12_000_000, 200, 8),
        tags=["baseline"], hypothesis="reference run",
    )
    faster = _record(
        "faster", "2026-01-02T00:00:00Z", _metrics(1, .5, 20_000_000, 150, 7),
        hypothesis="cache repeated work",
    )
    invalid = _record(
        "invalid", "2026-01-03T00:00:00Z", _metrics(.01, .01, 1, 1, 1), correct=False,
    )
    partial = _record(
        "partial", "2026-01-04T00:00:00Z", {"total_wall_seconds": .001},
    )
    for record in (baseline, faster, invalid, partial):
        append_record(record, path)
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n{not json}\n[]\n")
    return baseline, faster, invalid, partial


def test_dashboard_handles_missing_and_empty_results(tmp_path):
    for path in (tmp_path / "missing.jsonl", tmp_path / "empty.jsonl"):
        if path.name == "empty.jsonl":
            path.write_text("\n", encoding="utf-8")
        response = create_app(path).test_client().get("/")
        assert response.status_code == 200
        assert b"No experiments yet" in response.data


def test_dashboard_uses_canonical_comparison_and_reports_corrupt_lines(tmp_path):
    path = tmp_path / "experiments.jsonl"
    baseline, faster, invalid, partial = _write_mixed_log(path)
    records, malformed = load_experiments(path)
    assert malformed == 2
    assert {record["experiment_id"] for record in pareto_frontier(records)} == {"baseline", "faster"}
    assert best_per_metric(records)["total_wall_seconds"]["experiment_id"] == faster["experiment_id"]

    response = create_app(path).test_client().get("/")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "50.0%" in body
    assert "Skipped 2 malformed experiment lines" in body
    frontier = body.split("Pareto frontier", 1)[1].split("Research log", 1)[0]
    assert "/experiment/baseline" in frontier
    assert "/experiment/faster" in frontier
    assert "/experiment/invalid" not in frontier
    assert "/experiment/partial" not in frontier


def test_headline_prefers_full_suite_cohort_over_toy_smoke(tmp_path):
    path = tmp_path / "experiments.jsonl"
    full_scope = {
        "public": {"toy-small": {}, "toy-medium": {}, "toy-large": {}},
        "hidden": {"toy-small": {}, "toy-medium": {}, "toy-large": {}},
    }
    smoke = _record(
        "toy-smoke", "2026-01-03T00:00:00Z", _metrics(.001, .001, 100, 10, 1),
        tags=["baseline"], suites={"public": {"toy-small": {}}},
    )
    full_baseline = _record(
        "full-baseline", "2026-01-01T00:00:00Z", _metrics(10, 1, 1000, 1000, 3),
        tags=["baseline"], suites=full_scope,
    )
    full_optimized = _record(
        "full-optimized", "2026-01-02T00:00:00Z", _metrics(5, .5, 1200, 700, 3),
        tags=["algorithm"], suites=full_scope,
    )
    for record in (full_baseline, full_optimized, smoke):
        append_record(record, path)

    cohort = comparison_cohort([smoke, full_optimized, full_baseline])
    assert [record["experiment_id"] for record in cohort] == ["full-optimized", "full-baseline"]
    assert scope_label(cohort[0]) == "Full · toy-large, toy-medium, toy-small"

    body = create_app(path).test_client().get("/").get_data(as_text=True)
    assert "50.0%" in body
    assert "Full · toy-large, toy-medium, toy-small" in body
    comparison = body.split("Baseline → current", 1)[1].split("Trade-offs", 1)[0]
    assert "10.0000 s" in comparison
    assert "5.0000 s" in comparison
    frontier = body.split("Pareto frontier", 1)[1].split("Research log", 1)[0]
    assert "/experiment/full-optimized" in frontier
    assert "/experiment/toy-smoke" not in frontier


def test_headline_never_mixes_trusted_fingerprints():
    suites = {
        "public": {"toy-small": {}},
        "hidden": {"toy-small": {}},
    }
    old = _record("old", "2026-01-01T00:00:00Z", _metrics(10, 1, 1, 10, 1), suites=suites)
    current_baseline = _record(
        "baseline", "2026-01-02T00:00:00Z", _metrics(8, 1, 1, 8, 1),
        suites=suites, tags=["baseline"],
    )
    current_best = _record(
        "best", "2026-01-03T00:00:00Z", _metrics(4, 1, 1, 4, 1), suites=suites,
    )
    old["integrity"] = {"trusted_fingerprint": "old"}
    current_baseline["integrity"] = {"trusted_fingerprint": "current"}
    current_best["integrity"] = {"trusted_fingerprint": "current"}
    assert comparison_cohort([current_best, current_baseline, old]) == [
        current_best,
        current_baseline,
    ]


def test_without_full_suite_latest_scope_is_compared_only_with_itself():
    public = _record(
        "public", "2026-01-01T00:00:00Z", _metrics(2, 1, 100, 100, 2),
        suites={"public": {"toy-small": {}, "toy-medium": {}, "toy-large": {}}},
    )
    custom = _record(
        "custom", "2026-01-02T00:00:00Z", _metrics(1, 1, 100, 100, 2),
        suites={"custom": {"toy-small": {}}},
    )
    assert comparison_cohort([custom, public]) == [custom]


def test_history_links_only_rankable_results(tmp_path):
    path = tmp_path / "experiments.jsonl"
    _write_mixed_log(path)
    body = create_app(path).test_client().get("/").get_data(as_text=True)
    history = body.split('class="chart"', 1)[1].split('class="axis"', 1)[0]
    assert 'href="/experiment/baseline"' in history
    assert 'href="/experiment/faster"' in history
    assert "/experiment/invalid" not in history
    assert "/experiment/partial" not in history


def test_detail_404_and_methodology(tmp_path):
    path = tmp_path / "experiments.jsonl"
    _write_mixed_log(path)
    client = create_app(path).test_client()
    detail = client.get("/experiment/faster")
    assert detail.status_code == 200
    assert b"cache repeated work" in detail.data
    assert client.get("/experiment/unknown").status_code == 404
    assert b"never accepts external public keys" in client.get("/methodology").data


def test_templates_escape_untrusted_record_content(tmp_path):
    path = tmp_path / "experiments.jsonl"
    hostile = _record(
        "hostile", "2026-01-01T00:00:00Z", _metrics(1, 1, 1, 1, 1),
        hypothesis='<script>alert("owned")</script>',
    )
    append_record(hostile, path)
    client = create_app(path).test_client()
    for response in (client.get("/"), client.get("/experiment/hostile")):
        assert response.status_code == 200
        assert b'<script>alert("owned")</script>' not in response.data
        assert b"&lt;script&gt;" in response.data
