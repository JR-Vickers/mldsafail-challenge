"""Version and epoch binding, native ratio scoring and private output boundaries."""
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from mldsafail.evaluator.coordinator import Coordinator, CoordinatorConfig
from mldsafail.evaluator.envelope import EnvelopeError, sign_envelope, verify_envelope
from mldsafail.web.app import comparison_cohort, create_app
from mldsafail.web.comparison import rankable_score
from mldsafail.web.models import Base, EvaluationAttempt, EvaluationJob, ExperimentResult, Submission, User
from mldsafail.web.repositories import DatabaseResultRepository
from mldsafail.web.services import cancel_submission, create_api_token, create_submission

COHORT = {"epoch_id": "epoch-a", "evaluator_fingerprint": "eval-amd64",
          "hidden_suite_version": "staging-1", "worker_class": "mlwe-amd64-v1"}
REQUEST = {"repository_url": "https://github.com/example/solver", "commit_sha": "a" * 40,
           "hypothesis": "reduce complete worker CPU", "benchmark_version": "0.5.0"}


def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'hosted.db'}")
    Base.metadata.create_all(engine)
    return engine


def test_api_defaults_to_mlwe_and_rejects_incompatible_identity(tmp_path):
    app = create_app(config_name="test", config={"DATABASE_URL": f"sqlite:///{tmp_path / 'api.db'}",
        "BENCHMARK_VERSION": "0.5.0", "MLWE_EPOCH_ID": COHORT["epoch_id"],
        **{name.upper(): value for name, value in COHORT.items() if name != "epoch_id"}})
    Base.metadata.create_all(app.extensions["mldsafail_engine"])
    with Session(app.extensions["mldsafail_engine"]) as session:
        user = User(display_name="researcher"); session.add(user); session.commit()
        _, token = create_api_token(session, user, "CLI")
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "first"}
    client = app.test_client()
    request = {name: value for name, value in REQUEST.items() if name != "benchmark_version"}
    response = client.post("/api/v1/submissions", headers=headers, json=request)
    assert response.status_code == 201
    assert response.json["submission"]["benchmark_version"] == "0.5.0"
    assert all(response.json["submission"][k] == v for k, v in COHORT.items())
    assert client.post("/api/v1/submissions", headers=headers, json=request).status_code == 200
    for field in COHORT:
        response = client.post("/api/v1/submissions", headers=headers, json=request | {field: "wrong"})
        assert response.status_code == 422
        assert response.json["error"]["code"] == "incompatible_cohort"
    app.config["ENV"] = "staging"
    assert client.post("/api/v1/submissions", headers=headers,
                       json=request | {"repository_url": "file:///etc"}).status_code == 422


def test_cohorts_keep_native_ratios_and_private_diagnostics_out(tmp_path):
    engine = database(tmp_path)
    with Session(engine) as session:
        user = User(display_name="researcher"); session.add(user); session.flush()
        for index, (version, epoch, score) in enumerate([
            ("0.4.0", None, 123), ("0.5.0", "epoch-a", 0.9131), ("0.5.0", "epoch-b", 0.8123)]):
            submission = Submission(user_id=user.id, **(REQUEST | {"benchmark_version": version}))
            session.add(submission); session.flush()
            session.add(ExperimentResult(submission_id=submission.id, user_id=user.id,
                score=score if version == "0.4.0" else None,
                mlwe_score=score if version == "0.5.0" else None, verified=True,
                source_digest="b" * 64, benchmark_version=version,
                **(COHORT | {"epoch_id": epoch}),
                diagnostics={"seed": "SECRET-SEED", "candidate": "SECRET-CANDIDATE", "path": "/private/epoch"}))
        session.commit()
        records, _ = DatabaseResultRepository(session).records()
        assert "SECRET" not in str(records) and "/private" not in str(records)
        assert sorted(rankable_score(record) for record in records) == [0.8123, 0.9131, 123]
        assert len(comparison_cohort(records)) == 1
        for name in ("hidden_suite_version", "worker_class", "epoch_id"):
            first = records[0]
            second = {**first, "provenance": {**first["provenance"], name: "different"}}
            assert comparison_cohort([first, second]) == [first]
        _, token = create_api_token(session, user, "leaderboard")
    app = create_app(config_name="test", config={"DATABASE_URL": str(engine.url),
        "BENCHMARK_VERSION": "0.5.0", "MLWE_EPOCH_ID": "epoch-a",
        **{name.upper(): value for name, value in COHORT.items() if name != "epoch_id"}})
    response = app.test_client().get("/api/v1/leaderboard", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert len(response.json["leaderboard"]) == 1
    assert response.json["leaderboard"][0]["score"] == 0.9131
    assert b"SECRET" not in response.data and b"epoch-b" not in response.data
    assert b"0.913100" in app.test_client().get("/").data or b"0.812300" in app.test_client().get("/").data


def test_mlwe_envelope_requires_epoch_and_preserves_fractional_score():
    identity = {**COHORT, "benchmark_version": "0.5.0", "source_digest": "b" * 64}
    payload = {**identity, "verified": True, "score": 0.9131, "diagnostics": {}, "failure_class": None}
    assert verify_envelope(sign_envelope(payload, b"key"), b"key", identity)["score"] == 0.9131
    for score in (True, 0, -1):
        with pytest.raises(EnvelopeError):
            verify_envelope(sign_envelope(payload | {"score": score}, b"key"), b"key", identity)
    with pytest.raises(EnvelopeError):
        verify_envelope(sign_envelope(payload, b"key"), b"key", identity | {"epoch_id": "other"})


def test_private_staging_requires_oauth_and_disables_development_login(monkeypatch):
    from mldsafail.web.config import load_config
    for key, value in {"MLDSAFAIL_SECRET_KEY": "test", "MLDSAFAIL_DATABASE_URL": "sqlite://",
                       "MLDSAFAIL_EVALUATOR_FINGERPRINT": "eval", "MLDSAFAIL_HIDDEN_SUITE_VERSION": "hidden"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
    monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="OAuth"):
        load_config("private-staging")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-secret")
    config = load_config("private-staging")
    assert config["ALLOW_DEV_AUTH"] is False
    assert config["SESSION_COOKIE_HTTPONLY"] is True
    assert config["SESSION_COOKIE_SECURE"] is False


def test_mlwe_pages_describe_native_score_without_changing_historical_pages():
    client = create_app(config_name="test", config={"BENCHMARK_VERSION": "0.5.0"}).test_client()
    assert b"Reference-normalized CPU scoring" in client.get("/").data
    assert b"t = A" in client.get("/about").data
    assert b"60-second penalty" in client.get("/methodology").data
    historical = create_app(config_name="test").test_client()
    assert b"trusted abstract operation counts" in historical.get("/methodology").data


def test_queue_never_acquires_cancelled_or_other_version(tmp_path):
    from mldsafail.evaluator.queue import claim_job
    engine = database(tmp_path)
    with Session(engine) as session:
        user = User(display_name="researcher"); session.add(user); session.commit()
        submission, _ = create_submission(session, user, REQUEST, "mlwe", cohort=COHORT)
        cancel_submission(session, submission)
        create_submission(session, user, REQUEST | {"benchmark_version": "0.4.0"}, "legacy")
        assert claim_job(session, "mlwe-worker", benchmark_version="0.5.0") is None
        assert claim_job(session, "legacy-worker", benchmark_version="0.4.0") is not None


@pytest.mark.parametrize("outcome", ["accepted", "invalid", "cancelled", "validating_cancel", "retry", "incompatible"])
def test_coordinator_mlwe_states_and_safe_failure_logs(tmp_path, monkeypatch, outcome):
    from mldsafail.evaluator.mlwe import EvaluationCancelled
    import mldsafail.evaluator.coordinator as module
    engine = database(tmp_path)
    config = CoordinatorConfig(str(engine.url), tmp_path, tmp_path / "unused", "image", "0.5.0",
        COHORT["evaluator_fingerprint"], COHORT["hidden_suite_version"], COHORT["worker_class"],
        tmp_path / "private", tmp_path / "epoch", COHORT["epoch_id"])
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.config, coordinator.engine, coordinator.worker_id = config, engine, "worker"
    with Session(engine) as session:
        user = User(display_name="researcher"); session.add(user); session.commit()
        submission, _ = create_submission(session, user, REQUEST, "key", cohort=COHORT)
        identifier = submission.id
        if outcome == "incompatible":
            submission.epoch_id = "other"; session.commit()
    source = tmp_path / "source" / "src/mldsafail/solver"
    source.mkdir(parents=True)
    (source / "solver.py").write_text("def solve(x): return None\n")
    def acquire(*args, **kwargs):
        if outcome == "validating_cancel":
            with Session(engine) as session:
                cancel_submission(session, session.get(Submission, identifier))
        return tmp_path / "source"
    monkeypatch.setattr(module, "acquire_commit", acquire)
    monkeypatch.setattr(module, "validate_eligible_source", lambda *args, **kwargs: None)

    class Evaluator:
        def evaluate(self, source, output, identity, key, checkpoint):
            checkpoint()
            if outcome == "retry":
                raise RuntimeError("/private/epoch SECRET-SEED SECRET-CANDIDATE")
            if outcome == "cancelled":
                raise EvaluationCancelled()
            verified = outcome != "invalid"
            return sign_envelope({**identity, "verified": verified,
                "score": 0.9131 if verified else None, "diagnostics": {"eligible": verified},
                "failure_class": None if verified else "invalid_answer"}, key)

    coordinator.mlwe = Evaluator()
    assert coordinator.run_once()
    with Session(engine) as session:
        submission = session.get(Submission, identifier)
        expected = {"invalid": "rejected", "retry": "queued", "incompatible": "rejected",
                    "validating_cancel": "cancelled"}.get(outcome, outcome)
        assert submission.state == expected
        attempt = session.scalar(select(EvaluationAttempt))
        assert "SECRET" not in attempt.log and "/private" not in attempt.log
        result = session.scalar(select(ExperimentResult))
        if outcome == "accepted":
            assert result.score is None and result.mlwe_score == 0.9131 and result.epoch_id == "epoch-a"
        else:
            assert result is None
