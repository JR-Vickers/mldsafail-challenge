from __future__ import annotations

from mldsafail.web.app import create_app
from mldsafail.web.models import Base


def test_metrics_and_json_health_contract(tmp_path):
    app = create_app(config_name="test", config={"DATABASE_URL": f"sqlite:///{tmp_path / 'metrics.db'}"})
    Base.metadata.create_all(app.extensions["mldsafail_engine"])
    client = app.test_client()
    assert client.get("/health/live").json == {"status": "ok"}
    assert client.get("/missing").status_code == 404
    metrics = client.get("/metrics").get_data(as_text=True)
    assert "mldsafail_http_requests_total" in metrics
    assert "mldsafail_http_request_failures_total 1" in metrics
    assert "mldsafail_evaluation_queue_depth 0" in metrics


def test_production_requires_database_and_secret(monkeypatch):
    monkeypatch.delenv("MLDSAFAIL_DATABASE_URL", raising=False)
    monkeypatch.delenv("MLDSAFAIL_SECRET_KEY", raising=False)
    try:
        create_app(config_name="production")
    except RuntimeError as error:
        assert "SECRET_KEY" in str(error) or "DATABASE_URL" in str(error)
    else:
        raise AssertionError("production accepted missing required configuration")
