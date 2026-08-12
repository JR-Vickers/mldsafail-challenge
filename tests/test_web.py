import json

from mldsafail.web.app import create_app, load_experiments, pareto_frontier


def _write_records(path):
    records = [
        {"experiment_id": "baseline", "timestamp": "2026-01-01T00:00:00Z", "tags": ["baseline"], "correct": True, "runtime_seconds": 2.0, "peak_memory_mb": 12, "abstract_cost": 200, "solution_quality": 8, "hypothesis": "reference"},
        {"experiment_id": "faster", "timestamp": "2026-01-02T00:00:00Z", "correct": True, "aggregate": {"total_wall_seconds": 1.0, "peak_memory_bytes": 20_000_000, "abstract_cost": 150, "solution_quality": 7}, "hypothesis": "cache work"},
        {"experiment_id": "failed", "timestamp": "2026-01-03T00:00:00Z", "correct": False, "runtime_seconds": .5, "abstract_cost": 40},
    ]
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n{not json}\n")
    return records


def test_dashboard_handles_missing_results(tmp_path):
    client = create_app(tmp_path / "missing.jsonl").test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"No experiments yet" in response.data


def test_dashboard_renders_records_and_reports_bad_lines(tmp_path):
    path = tmp_path / "experiments.jsonl"
    _write_records(path)
    response = create_app(path).test_client().get("/")
    assert response.status_code == 200
    assert b"Current records" in response.data
    assert b"50.0%" in response.data
    assert b"Skipped 1 malformed experiment line" in response.data
    assert b"faster" in response.data


def test_detail_and_methodology_routes(tmp_path):
    path = tmp_path / "experiments.jsonl"
    _write_records(path)
    client = create_app(path).test_client()
    detail = client.get("/experiment/faster")
    assert detail.status_code == 200
    assert b"cache work" in detail.data
    assert client.get("/experiment/unknown").status_code == 404
    safety = client.get("/methodology")
    assert b"never accepts external public keys" in safety.data


def test_parser_skips_non_objects_and_pareto_excludes_invalid(tmp_path):
    path = tmp_path / "experiments.jsonl"
    records = _write_records(path)
    with path.open("a") as stream:
        stream.write("[]\n")
    loaded, malformed = load_experiments(path)
    assert len(loaded) == 3
    assert malformed == 2
    assert [record["experiment_id"] for record in pareto_frontier(records)] == ["baseline", "faster"]
    assert "failed" not in [record["experiment_id"] for record in pareto_frontier(records)]
