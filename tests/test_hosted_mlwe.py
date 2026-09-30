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
from mldsafail.web.services import create_api_token, create_submission

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


def test_mlwe_envelope_requires_epoch_and_preserves_fractional_score():
    identity = {**COHORT, "benchmark_version": "0.5.0", "source_digest": "b" * 64}
    payload = {**identity, "verified": True, "score": 0.9131, "diagnostics": {}, "failure_class": None}
    assert verify_envelope(sign_envelope(payload, b"key"), b"key", identity)["score"] == 0.9131
    for score in (True, 0, -1):
        with pytest.raises(EnvelopeError):
            verify_envelope(sign_envelope(payload | {"score": score}, b"key"), b"key", identity)
    with pytest.raises(EnvelopeError):
        verify_envelope(sign_envelope(payload, b"key"), b"key", identity | {"epoch_id": "other"})


@pytest.mark.parametrize("outcome", ["accepted", "invalid", "cancelled", "retry", "incompatible"])
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
    monkeypatch.setattr(module, "acquire_commit", lambda *args: tmp_path / "source")
    monkeypatch.setattr(module, "validate_eligible_source", lambda *args: None)

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
        expected = {"invalid": "rejected", "retry": "queued", "incompatible": "rejected"}.get(outcome, outcome)
        assert submission.state == expected
        attempt = session.scalar(select(EvaluationAttempt))
        assert "SECRET" not in attempt.log and "/private" not in attempt.log
        result = session.scalar(select(ExperimentResult))
        if outcome == "accepted":
            assert result.score is None and result.mlwe_score == 0.9131 and result.epoch_id == "epoch-a"
        else:
            assert result is None
