from __future__ import annotations

from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from mldsafail.web.app import create_app
from mldsafail.web.models import ExperimentResult, Submission, User
from mldsafail.web.repositories import DatabaseResultRepository


def test_migration_builds_hosted_schema(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'schema.db'}"
    monkeypatch.setenv("MLDSAFAIL_DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    assert {"users", "api_tokens", "submissions", "evaluation_jobs", "experiment_results"} <= tables


def test_token_creation_migration_preserves_existing_tokens(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    monkeypatch.setenv("MLDSAFAIL_DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "d6e80c850001")
    engine = create_engine(url)
    with engine.begin() as database:
        database.execute(text("INSERT INTO users (id, display_name, is_admin, created_at, updated_at) VALUES ('user', 'Ada', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
        database.execute(text("INSERT INTO api_tokens (id, user_id, prefix, secret_hash, name, scopes, created_at) VALUES ('token', 'user', '1234567890', 'unchanged-hash', 'existing', '[]', CURRENT_TIMESTAMP)"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with engine.connect() as database:
        assert database.execute(text("SELECT secret_hash, creation_request_key FROM api_tokens WHERE id='token'")).one() == ("unchanged-hash", None)
    assert any(constraint["name"] == "uq_api_token_creation_request"
               for constraint in inspect(engine).get_unique_constraints("api_tokens"))


def test_database_repository_produces_rankable_hosted_records(tmp_path):
    url = f"sqlite:///{tmp_path / 'hosted.db'}"
    app = create_app(config_name="test", config={"DATABASE_URL": url})
    from mldsafail.web.models import Base
    engine = app.extensions["mldsafail_engine"]
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(display_name="researcher", avatar_url=None)
        submission = Submission(
            user=user, repository_url="https://github.com/example/solver.git", commit_sha="a" * 40,
            hypothesis="fewer reductions", tags=["accepted"], benchmark_version="0.2.0",
        )
        result = ExperimentResult(
            submission=submission, user=user, score=123, verified=True, source_digest="b" * 64,
            benchmark_version="0.2.0", evaluator_fingerprint="eval-1",
            hidden_suite_version="hidden-1", worker_class="rootless-docker-v1",
            accepted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        session.add(result)
        session.commit()
        records, malformed = DatabaseResultRepository(session).records()
        assert malformed == 0
        assert records[0]["score"] == 123
        assert records[0]["participant"]["name"] == "researcher"
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert b"researcher" in response.data


def test_health_routes_work_without_database(tmp_path):
    client = create_app(tmp_path / "missing.jsonl", config_name="test").test_client()
    assert client.get("/health/live").json == {"status": "ok"}
    assert client.get("/health/ready").json == {"status": "ready"}
