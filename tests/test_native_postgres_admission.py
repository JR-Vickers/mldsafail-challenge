"""Native gates: run only against an explicitly named empty disposable database.

Set MLDSAFAIL_NATIVE_TEST_DATABASE_URL to a PostgreSQL URL whose database starts
with mldsafail_acceptance_. The owner of the host provisions/removes that database.
These tests never contact staging or create/drop the database itself.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
from threading import Barrier

import pytest
from sqlalchemy import create_engine, inspect, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from mldsafail.evaluator.queue import claim_job, heartbeat, recover_stale_jobs
from mldsafail.web.models import Base, EvaluationJob, IdempotencyKey, Submission, User, utcnow
from mldsafail.web.services import DomainError, create_submission as application_create_submission

PAYLOAD = dict(repository_url='https://github.com/example/solver', commit_sha='a' * 40,
               hypothesis='disposable native admission gate', benchmark_version='0.5.0')
def create_submission(*args, **kwargs):
    kwargs.setdefault('cohort', dict(epoch_id='synthetic', evaluator_fingerprint='synthetic',
                                    hidden_suite_version='synthetic', worker_class='synthetic'))
    return application_create_submission(*args, **kwargs)


LIMITS = dict(outstanding_per_account=1, submissions_per_day=2, queued_globally=10)


@pytest.fixture
def database():
    value = os.environ.get('MLDSAFAIL_NATIVE_TEST_DATABASE_URL')
    if not value:
        pytest.skip('explicit disposable native PostgreSQL URL required')
    url = make_url(value)
    if url.get_backend_name() != 'postgresql' or not (url.database or '').startswith('mldsafail_acceptance_'):
        pytest.fail('native tests require a disposable PostgreSQL database name')
    engine = create_engine(url, pool_size=8)
    if inspect(engine).get_table_names():
        engine.dispose()
        pytest.fail('native disposable database must be empty')
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            users = [User(display_name='native-' + str(index)) for index in range(4)]
            session.add_all(users)
            session.commit()
            ids = [user.id for user in users]
        yield engine, ids
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def simultaneous(function, count=2):
    barrier = Barrier(count)
    def invoke(index):
        barrier.wait(timeout=10)
        return function(index)
    with ThreadPoolExecutor(count) as pool:
        return list(pool.map(invoke, range(count)))


def test_native_account_admission_and_idempotency(database):
    engine, users = database
    def submit(index):
        with Session(engine) as session:
            try:
                return create_submission(session, session.get(User, users[0]), PAYLOAD,
                                         'distinct-' + str(index), admission_limits=LIMITS)[1]
            except DomainError as error:
                return error.status
    assert sorted(simultaneous(submit), key=str) == [429, True]
    # Replaying the accepted key bypasses admission and never adds another job.
    with Session(engine) as session:
        submission = session.scalar(select(Submission))
        key = session.scalar(select(IdempotencyKey.key).where(IdempotencyKey.submission_id == submission.id))
    def replay(_):
        with Session(engine) as session:
            return create_submission(session, session.get(User, users[0]), PAYLOAD,
                                     key, admission_limits=LIMITS)[1]
    assert simultaneous(replay) == [False, False]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Submission)) == 1
        assert session.scalar(select(func.count()).select_from(EvaluationJob)) == 1


def test_native_global_queue_admission(database):
    engine, users = database
    def submit(index):
        with Session(engine) as session:
            try:
                return create_submission(session, session.get(User, users[index]), PAYLOAD,
                                         'queue-' + str(index), admission_limits={**LIMITS, 'queued_globally': 1})[1]
            except DomainError as error:
                return error.status
    assert sorted(simultaneous(submit), key=str) == [429, True]


def test_native_serialized_claim_and_stale_owner_fencing(database):
    engine, users = database
    with Session(engine) as session:
        for index in range(2):
            create_submission(session, session.get(User, users[index]), PAYLOAD,
                              'claim-' + str(index), admission_limits=LIMITS)
    def claim(index):
        with Session(engine) as session:
            job = claim_job(session, 'owner-' + str(index))
            return job.id if job else None
    claimed = [value for value in simultaneous(claim) if value]
    assert len(claimed) == 1
    with Session(engine) as session:
        assert claim_job(session, 'restart-owner') is None
        job = session.get(EvaluationJob, claimed[0])
        old_owner = job.lease_owner
        job.lease_expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
        assert recover_stale_jobs(session) == (0, 0)
        assert recover_stale_jobs(session, verified_stopped=lambda job: True) == (1, 0)
        assert not heartbeat(session, job.id, old_owner)
        replacement = claim_job(session, 'new-owner')
        assert replacement.id == job.id and replacement.attempts == 2
    with Session(engine) as session:
        assert not heartbeat(session, claimed[0], old_owner)
        assert heartbeat(session, claimed[0], 'new-owner')
        assert claim_job(session, 'competing-owner') is None


def test_native_operator_revocation_and_actor_audit(database):
    # Exercise the same source-bound operator controls on real PostgreSQL.
    from test_admin_moderation import exercise
    engine, _ = database
    exercise(engine)


def test_native_daily_window_and_running_cancellation_lease_fence(database):
    from mldsafail.web.services import cancel_submission, transition_submission
    from mldsafail.web.models import SubmissionState
    engine, users = database
    with Session(engine) as session:
        user=session.get(User,users[0])
        first,_=create_submission(session,user,PAYLOAD,'daily-first',admission_limits=LIMITS)
        cancel_submission(session,first)
        second,_=create_submission(session,user,PAYLOAD,'daily-second',admission_limits=LIMITS)
        job=claim_job(session,'native-cancellation-owner')
        assert job.submission_id==second.id
        transition_submission(session,second,SubmissionState.RUNNING)
        job.status='running';session.commit()
        cancel_submission(session,second)
        assert second.cancel_requested and second.state=='running'
        assert session.get(EvaluationJob,job.id).status=='running'
        assert claim_job(session,'premature-replacement') is None
        with pytest.raises(DomainError) as limited:
            create_submission(session,user,PAYLOAD,'daily-third',admission_limits=LIMITS)
        assert limited.value.status==429;session.rollback()
        # Only the explicitly expired cancelled lease is reconciled. The prior
        # owner's heartbeat is fenced after reconciliation, and cancellation
        # still counts toward the independently configured rolling daily limit.
        second=session.get(Submission,second.id)
        transition_submission(session,second,SubmissionState.CANCELLED)
        job=session.get(EvaluationJob,job.id)
        job.lease_expires_at=utcnow()-timedelta(seconds=1);session.commit()
        assert recover_stale_jobs(session)==(0,0)
        assert recover_stale_jobs(session, verified_stopped=lambda job: True)==(0,0)
        assert not heartbeat(session,job.id,'native-cancellation-owner')
        with pytest.raises(DomainError):
            create_submission(session,user,PAYLOAD,'daily-third',admission_limits=LIMITS)
        session.rollback()
        first=session.get(Submission,first.id)
        first.created_at=utcnow()-timedelta(hours=24,seconds=1);session.commit()
        assert create_submission(session,user,PAYLOAD,'daily-third',admission_limits=LIMITS)[1]
