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


def test_reconcile_historical_cancellations_is_narrow_and_idempotent(tmp_path):
    from mldsafail.evaluator.queue import reconcile_cancelled_queued_jobs
    from mldsafail.web.models import EvaluationAttempt, SubmissionTransition
    engine, users = setup(tmp_path, 4)
    with Session(engine) as session:
        jobs = []
        for index, user_id in enumerate(users):
            submission, _ = create_submission(
                session, session.get(User, user_id), PAYLOAD, str(index))
            job = session.scalar(select(EvaluationJob).where(
                EvaluationJob.submission_id == submission.id))
            if index != 1:
                cancel_submission(session, submission)
                job.status = ['queued', 'queued', 'claimed', 'running'][index]
            jobs.append(job)
        session.commit()
        transitions = session.scalar(select(func.count()).select_from(SubmissionTransition))
        expected = [(jobs[0].id, jobs[0].submission_id)]
        assert reconcile_cancelled_queued_jobs(session) == expected
        session.rollback()
        assert jobs[0].status == 'queued'
        assert reconcile_cancelled_queued_jobs(session) == expected
        session.commit()
        assert reconcile_cancelled_queued_jobs(session) == []
        session.commit()
        assert [job.status for job in jobs] == ['complete', 'queued', 'claimed', 'running']
        assert all(job.attempts == 0 for job in jobs)
        assert session.scalar(select(func.count()).select_from(EvaluationAttempt)) == 0
        assert session.scalar(select(func.count()).select_from(SubmissionTransition)) == transitions


def test_reconciliation_cli_preserves_private_intent_and_preview(tmp_path, monkeypatch, capsys):
    import json
    import sys
    from deploy.reconcile_cancelled_jobs import main
    engine, users = setup(tmp_path)
    with Session(engine) as session:
        submission, _ = create_submission(session, session.get(User, users[0]), PAYLOAD, 'repair')
        cancel_submission(session, submission)
        job = session.scalar(select(EvaluationJob))
        job.status = 'queued'
        session.commit()
        job_id = job.id
    monkeypatch.setenv('DATABASE_URL', str(engine.url))
    for index, apply in enumerate([False, True, True]):
        report = tmp_path / f'repair-{index}.jsonl'
        monkeypatch.setattr(sys, 'argv', ['repair', '--report', str(report)] + (['--apply'] if apply else []))
        main()
        records = [json.loads(line) for line in report.read_text().splitlines()]
        assert [record['stage'] for record in records] == [
            'started', 'prepared', 'committed' if apply else 'preview_rolled_back']
        assert len(records[1]['jobs']) == (0 if index == 2 else 1)
        assert report.stat().st_mode & 0o777 == 0o600
        output = json.loads(capsys.readouterr().out)
        assert output == {'applied': apply, 'affected_count': 0 if index == 2 else 1}
        with Session(engine) as session:
            assert session.get(EvaluationJob, job_id).status == ('complete' if apply else 'queued')
    with pytest.raises(FileExistsError):
        main()
