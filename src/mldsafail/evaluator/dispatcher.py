"""Production DB dispatcher. No Docker access, source acquisition or evaluator."""
from __future__ import annotations

from datetime import timedelta
import hashlib
import hmac
import json
from pathlib import Path
import time
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from mldsafail.evaluator.envelope import canonical_payload, verify_envelope, EnvelopeError
from mldsafail.evaluator.queue import claim_job, heartbeat
from mldsafail.evaluator.workload import WorkloadBlocked
from mldsafail.evaluator.workload_client import WorkloadClient
from mldsafail.web.models import EvaluationAttempt, EvaluationJob, ExperimentResult, Submission, SubmissionState, utcnow
from mldsafail.web.services import evaluation_transaction_lock, transition_submission


def authenticated_result(envelope, key, reference, workload_id):
    if type(envelope) is not dict or set(envelope) != {'payload', 'signature'}:
        raise EnvelopeError('invalid controller envelope')
    signature = hmac.new(key, canonical_payload(envelope['payload']), hashlib.sha256).hexdigest()
    if not isinstance(envelope['signature'], str) or not hmac.compare_digest(envelope['signature'], signature):
        raise EnvelopeError('invalid controller signature')
    result = envelope['payload']
    expected = dict(workload_id=workload_id, role='participant', reference=reference)
    if result.get('binding') != expected:
        raise EnvelopeError('controller ownership binding changed')
    if result.get('status') == 'evaluated':
        identity = {**reference['identity'], 'source_digest': result['source_digest']}
        payload = verify_envelope(result['envelope'], key, identity)
        return {'disposition': 'accepted' if payload['verified'] else 'rejected', 'payload': payload}
    if result.get('status') == 'rejected':
        return dict(disposition='rejected', code=result.get('code', 'invalid_source'))
    if result.get('status') == 'infrastructure_failed':
        return dict(disposition='infrastructure_failed', code='controller_failure')
    raise EnvelopeError('controller status invalid')


def result_binding(reference, workload_id, outcome):
    return dict(workload_id=workload_id, job_id=reference['job_id'], attempt_id=reference['attempt_id'],
                attempt_number=reference['attempt_number'], submission_id=reference['submission_id'],
                owner=reference['owner'], disposition=outcome['disposition'],
                outcome_sha256=hashlib.sha256(canonical_payload(outcome)).hexdigest(), outcome=outcome)


def apply_outcome(database, binding, *, retry):
    """Idempotent commit/reconciliation under the existing transaction mutex.

    No schema migration and no computation retry after an ambiguous commit.
    A matching terminal result is preserved; a conflicting result blocks recovery.
    """
    evaluation_transaction_lock(database)
    job = database.get(EvaluationJob, binding['job_id'], with_for_update=True)
    attempt = database.get(EvaluationAttempt, binding['attempt_id'], with_for_update=True)
    submission = database.get(Submission, binding['submission_id'], with_for_update=True)
    if (job is None or attempt is None or submission is None or attempt.job_id != job.id or
            job.submission_id != submission.id or attempt.number != binding['attempt_number'] or
            job.attempts != binding['attempt_number'] or attempt.worker_id != binding['owner']['worker_id']):
        raise WorkloadBlocked('database_attempt_identity_changed')
    outcome = binding['outcome']
    if hashlib.sha256(canonical_payload(outcome)).hexdigest() != binding['outcome_sha256']:
        raise WorkloadBlocked('database_outcome_binding_changed')
    existing = database.scalar(select(ExperimentResult).where(ExperimentResult.submission_id == submission.id))
    payload = outcome.get('payload')
    if existing is not None:
        if (binding['disposition'] != 'accepted' or not payload or
                any(getattr(existing, field) != payload[field] for field in
                    ('source_digest', 'benchmark_version', 'evaluator_fingerprint', 'hidden_suite_version', 'worker_class', 'epoch_id')) or
                existing.mlwe_score != payload['score'] or existing.diagnostics != payload['diagnostics'] or
                attempt.status != 'accepted' or job.status != 'complete'):
            raise WorkloadBlocked('conflicting_committed_result')
        database.commit()
        return
    if attempt.finished_at is not None:
        # Non-result terminal dispositions also reconcile without another insert
        # or transition; inspect the existing attempt and job under the mutex.
        if binding['disposition'] == 'accepted' or attempt.status != binding['disposition']:
            raise WorkloadBlocked('conflicting_committed_attempt')
        database.commit(); return
    if job.lease_owner != binding['owner']['worker_id']:
        raise WorkloadBlocked('database_lease_owner_changed')
    disposition = binding['disposition']
    if submission.cancel_requested or submission.state == SubmissionState.CANCELLED.value:
        if disposition != 'cancelled':
            raise WorkloadBlocked('cancellation_won_result_transaction')
    attempt.status = disposition; attempt.finished_at = utcnow()
    if disposition == 'accepted':
        database.add(ExperimentResult(submission_id=submission.id, user_id=submission.user_id,
            score=None, mlwe_score=payload['score'], verified=True,
            **{field: payload[field] for field in ('source_digest', 'benchmark_version', 'evaluator_fingerprint',
                'hidden_suite_version', 'worker_class', 'epoch_id')}, diagnostics=payload['diagnostics']))
        job.status = 'complete'
        transition_submission(database, submission, SubmissionState.ACCEPTED)
    elif disposition == 'cancelled':
        job.status = 'complete'
        if submission.state != SubmissionState.CANCELLED.value:
            transition_submission(database, submission, SubmissionState.CANCELLED, 'cancellation completed')
    elif disposition == 'rejected':
        job.status = 'complete'; attempt.failure_class = outcome.get('code', 'invalid_answer')
        submission.rejection_code = attempt.failure_class
        transition_submission(database, submission, SubmissionState.REJECTED, 'controller verification failed')
    else:
        attempt.failure_class = outcome.get('code', 'infrastructure_failure')
        transition_submission(database, submission, SubmissionState.INFRASTRUCTURE_FAILED, 'evaluation platform failure')
        job.status = 'failed'
        if retry and job.attempts < job.max_attempts:
            transition_submission(database, submission, SubmissionState.QUEUED, 'verified cleanup permits infrastructure retry')
            job.status = 'queued'; job.available_at = utcnow()+timedelta(seconds=5*job.attempts)
            job.lease_owner = None; job.lease_expires_at = None
    database.commit()


class Dispatcher:
    def __init__(self, config, *, client=None):
        self.config = config
        self.engine = create_engine(config.database_url, pool_pre_ping=True,
                                    connect_args={'connect_timeout': 2, 'options': '-c statement_timeout=800 -c lock_timeout=800'} if config.database_url.startswith('postgresql') else {})
        self.database_id = hashlib.sha256(str(self.engine.url.set(password=None)).encode()).hexdigest()
        self.client = client or WorkloadClient(config.supervisor_socket, config.work_root/'dispatcher')
        self.key = config.signing_key.read_bytes()
        if len(self.key) < 32 or config.benchmark_version != '0.5.0':
            raise ValueError('protected dispatcher requires MLWE and a private signing key')

    def recover(self, state):
        reference = state['reference']
        if reference.get('owner', {}).get('database') != self.database_id:
            return False
        self.client.attach(state)
        if state['phase'] in ('commit_intent', 'committed'):
            binding = state['database_commit']
            with Session(self.engine) as database:
                evaluation_transaction_lock(database)
                attempt = database.get(EvaluationAttempt, binding['attempt_id'], with_for_update=True)
                existing = database.scalar(select(ExperimentResult).where(ExperimentResult.submission_id == binding['submission_id']))
                committed = existing is not None or attempt is not None and attempt.finished_at is not None
                if not committed:
                    if state['phase'] == 'committed':
                        raise WorkloadBlocked('acknowledged_database_commit_missing')
                    # The original transaction did not commit. Do not reuse its
                    # orphan output to insert a new score after recovery.
                    reference = {key: binding[key] for key in ('job_id', 'attempt_id', 'attempt_number', 'submission_id', 'owner')}
                    submission = database.get(Submission, binding['submission_id'])
                    cancelled = submission and (submission.cancel_requested or submission.state == SubmissionState.CANCELLED.value)
                    resolution = result_binding(reference, state['workload_id'],
                        dict(disposition='cancelled' if cancelled else 'infrastructure_failed', code='ambiguous_commit_uncommitted'))
                    self.client.mutation('resolve_commit', binding=binding, resolution=resolution)
                    binding = resolution
                apply_outcome(database, binding, retry=False)
            if state['phase'] == 'commit_intent': self.client.acknowledge(binding)
            elif not state['paused']: self.client.mutation('release')
            return True
        # No computation is repeated. Resources must be reconciled first; a
        # legacy expired job without this ownership binding stays blocked.
        if state['phase'] not in ('cleaned', 'postflight'):
            self.client.mutation('abort')
        if 'job_id' not in reference:
            with Session(self.engine) as database:
                evaluation_transaction_lock(database)
                jobs = database.scalars(select(EvaluationJob).where(EvaluationJob.lease_owner == reference['owner']['worker_id'])).all()
                if jobs:
                    # Claim acknowledgement was lost before bind: establish the
                    # exact attempt identity, never reset its attempt number.
                    if len(jobs) != 1: raise WorkloadBlocked('ambiguous_claim_recovery')
                    job = jobs[0]
                    attempt = database.scalar(select(EvaluationAttempt).where(EvaluationAttempt.job_id == job.id,
                                                        EvaluationAttempt.number == job.attempts))
                    if attempt is None:
                        attempt = EvaluationAttempt(id=reference['owner']['attempt_id'], job_id=job.id, number=job.attempts,
                            worker_id=reference['owner']['worker_id'], status='running')
                        database.add(attempt); database.commit()
                    reference = {**reference, 'job_id': job.id, 'submission_id': job.submission_id,
                                 'attempt_id': attempt.id, 'attempt_number': attempt.number}
                else:
                    binding=dict(disposition='unused_ownership',workload_id=state['workload_id'],owner=reference['owner'])
                    self.client.mutation('commit_intent',binding=binding)
                    database.commit()
                    self.client.acknowledge(binding)
                    return True
        outcome = dict(disposition='infrastructure_failed', code='orphaned_controller_output')
        binding = result_binding(reference, state['workload_id'], outcome)
        self.client.mutation('commit_intent', binding=binding)
        with Session(self.engine) as database: apply_outcome(database, binding, retry=False)
        self.client.acknowledge(binding)
        return True

    def run_once(self):
        state = self.client.status()
        if state and (state['phase'] != 'complete' or state['paused']):
            if not state['paused'] and state.get('heartbeat_monotonic_deadline', 0) >= time.monotonic():
                return False
            if state['paused'] and state['phase'] == 'committed': return False
            return self.recover(state)
        with Session(self.engine) as database:
            if database.scalar(select(EvaluationJob.id).where(EvaluationJob.status.in_(['claimed', 'running'])).limit(1)) is not None:
                return False  # Legacy unresolved ownership is never inferred dead.
            if database.scalar(select(EvaluationJob.id).where(EvaluationJob.status == 'queued').limit(1)) is None:
                return False
        owner = dict(database=self.database_id, worker_id='protected:'+uuid.uuid4().hex, attempt_id=str(uuid.uuid4()))
        try:
            self.client.acquire('evaluation', {'owner': owner})
        except (WorkloadBlocked, OSError):
            return False  # No database claim, and no attempt consumed.
        reference = None
        try:
            with Session(self.engine) as database:
                job = claim_job(database, owner['worker_id'], benchmark_version='0.5.0')
                if job is None:
                    self.client.unused(); return False
                submission = database.get(Submission, job.submission_id)
                attempt = EvaluationAttempt(id=owner['attempt_id'], job_id=job.id, number=job.attempts,
                                            worker_id=owner['worker_id'], status='running')
                database.add(attempt)
                identity = {name: getattr(self.config, name) for name in
                            ('benchmark_version', 'evaluator_fingerprint', 'hidden_suite_version', 'worker_class', 'epoch_id')}
                if any(getattr(submission, name) != value for name, value in identity.items()):
                    raise WorkloadBlocked('dispatcher_cohort_changed')
                reference = dict(owner=owner, job_id=job.id, attempt_id=attempt.id,
                    submission_id=submission.id, attempt_number=job.attempts,
                    repository_url=submission.repository_url, commit_sha=submission.commit_sha,
                    solver_path=submission.solver_path or 'src/mldsafail/solver', identity=identity)
                job.status = 'running'
                transition_submission(database, submission, SubmissionState.RUNNING)
                database.commit()
            self.client.bind(reference)
            self.client.launch('participant')
            while True:
                with Session(self.engine) as database:
                    submission = database.get(Submission, reference['submission_id'])
                    if submission.cancel_requested or submission.state == SubmissionState.CANCELLED.value:
                        self.client.mutation('cancel')
                        outcome = dict(disposition='cancelled'); break
                    if not heartbeat(database, reference['job_id'], owner['worker_id']):
                        raise WorkloadBlocked('dispatcher_lease_lost')
                self.client.heartbeat()
                result = self.client.result()
                if result is not None:
                    outcome = authenticated_result(result, self.key, reference, self.client.token)
                    break
                time.sleep(.25)
            binding = result_binding(reference, self.client.token, outcome)
            self.client.finish(binding)
            with Session(self.engine) as database: apply_outcome(database, binding, retry=True)
            self.client.acknowledge(binding)
            return True
        except Exception:
            # Database outages, cancellation races, invalid envelopes and lost
            # control responses all revoke authority. A later turn reconciles
            # state; none of these exceptions establishes worker termination.
            state = self.client.status()
            if state['phase'] not in ('postflight', 'commit_intent', 'committed', 'complete'):
                self.client.mutation('abort')
            raise
