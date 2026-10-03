from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from mldsafail.web.models import Base, User, Submission, EvaluationJob, utcnow
from mldsafail.web.services import create_submission, cancel_submission, DomainError
from mldsafail.evaluator.queue import claim_job

PAYLOAD = dict(repository_url='https://github.com/example/solver', commit_sha='a' * 40,
               hypothesis='bounded admission', benchmark_version='0.4.0')
LIMITS = dict(outstanding_per_account=1, submissions_per_day=2, queued_globally=10)


def setup(tmp_path, count=1):
    engine = create_engine('sqlite:///' + str(tmp_path / 'admission.db'))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users = [User(display_name=str(index)) for index in range(count)]
        session.add_all(users)
        session.commit()
        return engine, [user.id for user in users]


def test_admission_idempotency_cancellation_and_rolling_window(tmp_path):
    engine, users = setup(tmp_path)
    with Session(engine) as session:
        user = session.get(User, users[0])
        first, created = create_submission(session, user, PAYLOAD, 'first', admission_limits=LIMITS)
        assert created
        assert not create_submission(session, user, PAYLOAD, 'first', admission_limits=LIMITS)[1]
        with pytest.raises(DomainError) as failure:
            create_submission(session, user, PAYLOAD, 'second', admission_limits=LIMITS)
        assert failure.value.status == 429
        session.rollback()
        cancel_submission(session, first)
        assert session.scalar(select(EvaluationJob).where(EvaluationJob.submission_id == first.id)).status == 'complete'
        second, _ = create_submission(session, user, PAYLOAD, 'second', admission_limits=LIMITS)
        cancel_submission(session, second)
        with pytest.raises(DomainError):
            create_submission(session, user, PAYLOAD, 'third', admission_limits=LIMITS)
        session.rollback()
        first.created_at = utcnow() - timedelta(hours=24, seconds=1)
        session.commit()
        assert create_submission(session, user, PAYLOAD, 'third', admission_limits=LIMITS)[1]


def test_concurrent_account_admission_and_global_lease(tmp_path):
    engine, users = setup(tmp_path, 2)
    barrier = Barrier(2)
    def submit(index):
        with Session(engine) as session:
            user = session.get(User, users[0])
            barrier.wait()
            try:
                create_submission(session, user, PAYLOAD, str(index), admission_limits=LIMITS)
                return 'accepted'
            except DomainError as error:
                return error.status
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(submit, range(2)), key=str) == [429, 'accepted']
    with Session(engine) as session:
        create_submission(session, session.get(User, users[1]), PAYLOAD, 'other', admission_limits=LIMITS)
    barrier = Barrier(2)
    def claim(index):
        with Session(engine) as session:
            barrier.wait()
            job = claim_job(session, str(index))
            return job.id if job else None
    with ThreadPoolExecutor(2) as pool:
        assert sum(value is not None for value in pool.map(claim, range(2))) == 1
    # A new coordinator process/session sees the same persisted capacity lease.
    with Session(engine) as session:
        assert claim_job(session, 'restart') is None
        assert session.scalar(select(func.count()).select_from(EvaluationJob).where(EvaluationJob.status == 'claimed')) == 1


def test_global_queue_bound(tmp_path):
    engine, users = setup(tmp_path, 2)
    with Session(engine) as session:
        limits = dict(LIMITS, queued_globally=1)
        create_submission(session, session.get(User, users[0]), PAYLOAD, 'first', admission_limits=limits)
        with pytest.raises(DomainError) as failure:
            create_submission(session, session.get(User, users[1]), PAYLOAD, 'other', admission_limits=limits)
        assert failure.value.status == 429


def test_resource_floor_checks_fail_closed(tmp_path, monkeypatch):
    from mldsafail.evaluator.resources import resource_floors_available
    from types import SimpleNamespace
    meminfo = tmp_path / 'meminfo'
    meminfo.write_text('MemAvailable: 131072 kB\n')
    monkeypatch.setattr('mldsafail.evaluator.resources.shutil.disk_usage', lambda _: SimpleNamespace(free=5*1024**3))
    assert resource_floors_available(tmp_path, meminfo)
    meminfo.write_text('MemAvailable: 131071 kB\n')
    assert not resource_floors_available(tmp_path, meminfo)
    meminfo.unlink()
    assert not resource_floors_available(tmp_path, meminfo)
