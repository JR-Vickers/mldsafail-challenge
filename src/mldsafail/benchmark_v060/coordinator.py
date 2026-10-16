"""Explicit proposed queue consumer; constructed by trusted operators only."""
from datetime import timedelta
import os
import hashlib
import json
import math
import socket
import tempfile
from pathlib import Path, PurePosixPath
from sqlalchemy.orm import Session
from mldsafail.evaluator.queue import claim_job, heartbeat, recover_stale_jobs
from mldsafail.evaluator.source import acquire_commit, validate_eligible_source, SourcePolicy
from mldsafail.evaluator.mlwe import solver_directory
from mldsafail.benchmark_v050.constants import MAX_SERIALIZED_BYTES
from mldsafail.web.models import Submission, SubmissionState, EvaluationAttempt, ExperimentResult, utcnow
from mldsafail.web.services import DomainError, transition_submission


class Cancelled(Exception):
    pass


class Coordinator:
    def __init__(self, *, engine, cohort, gates, work_root, evaluate_source, signing_key, private_rehearsal=False):
        from .candidate_authority import CandidateRehearsalAuthority
        if isinstance(gates,CandidateRehearsalAuthority):
            gates.require_private(private_rehearsal)
            if gates.cohort_id!=cohort.public_id: raise ValueError('Candidate coordinator authority mismatch')
        gates.require()
        if cohort.benchmark_version != '0.6.0':
            raise ValueError('This coordinator consumes only v060 jobs')
        if len(signing_key) < 32:
            raise ValueError('Private v060 signing key required')
        self.signing_key = signing_key
        self.engine, self.cohort = engine, cohort
        self.root, self.evaluate_source = Path(work_root), evaluate_source
        self.worker_id = f'{socket.gethostname()}:{os.getpid()}:v060'

    def run_once(self):
        with Session(self.engine) as database:
            recover_stale_jobs(database)
            job = claim_job(database, self.worker_id, benchmark_version='0.6.0')
            if job is None:
                return False
            submission = database.get(Submission, job.submission_id)
            attempt = EvaluationAttempt(job_id=job.id, number=job.attempts, worker_id=self.worker_id, status='validating')
            database.add(attempt)
            database.commit()
            identity = dict(benchmark_version='0.6.0', epoch_id=self.cohort.epoch_id,
                            evaluator_fingerprint=self.cohort.evaluator_fingerprint,
                            hidden_suite_version=self.cohort.hidden_suite_version, worker_class=self.cohort.worker_class)
            def checkpoint():
                database.refresh(submission)
                if submission.cancel_requested or submission.state == SubmissionState.CANCELLED.value:
                    raise Cancelled()
                if not heartbeat(database, job.id, self.worker_id):
                    raise RuntimeError('evaluation lease lost')
            try:
                if any(getattr(submission, key) != value for key, value in identity.items()):
                    raise DomainError('incompatible_cohort', 'Submission targets an incompatible cohort.')
                relative = submission.solver_path or 'solver'
                if PurePosixPath(relative).is_absolute() or any(part.startswith('.') for part in relative.split('/')):
                    raise DomainError('invalid_solver_path', 'Invalid solver directory.')
                self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(dir=self.root) as temporary:
                    checkout = acquire_commit(submission.repository_url, submission.commit_sha,
                                              Path(temporary)/'source', sparse_paths=(relative,))
                    validate_eligible_source(checkout, SourcePolicy(max_eligible_bytes=MAX_SERIALIZED_BYTES),
                                             eligible_roots=(PurePosixPath(relative),))
                    from mldsafail.benchmark_v050.execution import solver_snapshot
                    snapshot = Path(temporary)/'snapshot'
                    solver_snapshot(solver_directory(checkout, relative), snapshot)
                    source = snapshot
                    source_sha256 = hashlib.sha256(json.dumps({path.relative_to(source).as_posix():
                        dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                        for path in sorted(source.rglob('*.py'))}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                    checkpoint()
                    transition_submission(database, submission, SubmissionState.RUNNING)
                    attempt.status = 'running'; job.status = 'running'; database.commit()
                    # Trusted adapter must authenticate and independently audit
                    # version-specific evidence before returning this payload.
                    from .envelope import verify
                    envelope = self.evaluate_source(source, checkpoint)
                    payload = verify(envelope, self.signing_key, cohort_id=self.cohort.public_id, source_sha256=source_sha256)
                    if payload.get('benchmark_version') != '0.6.0' or payload.get('cohort_id') != self.cohort.public_id:
                        raise RuntimeError('authenticated result cohort mismatch')
                    checkpoint()
                    if type(payload.get('verified')) is not bool:
                        raise RuntimeError('invalid verified disposition')
                    if payload['verified'] is True:
                        if type(payload.get('score')) not in (int, float) or not math.isfinite(payload['score']) or payload['score'] <= 0:
                            raise RuntimeError('invalid independently audited score')
                        transition_submission(database, submission, SubmissionState.ACCEPTED)
                        database.add(ExperimentResult(submission_id=submission.id, user_id=submission.user_id,
                            score=None, mlwe_score=payload['score'], verified=True,
                            source_digest=payload['source_sha256'], diagnostics={}, **identity))
                        attempt.status = 'accepted'; job.status = 'complete'
                    else:
                        attempt.status = 'rejected'; attempt.failure_class = 'invalid_answer'; job.status = 'complete'
                        submission.rejection_code = 'invalid_answer'
                        transition_submission(database, submission, SubmissionState.REJECTED)
            except Cancelled:
                attempt.status = 'cancelled'; job.status = 'complete'
                transition_submission(database, submission, SubmissionState.CANCELLED)
            except DomainError as error:
                attempt.status = 'rejected'; attempt.failure_class = error.code; job.status = 'complete'
                submission.rejection_code = error.code
                transition_submission(database, submission, SubmissionState.REJECTED)
            except Exception:
                # Malformed evidence/accounting/cleanup are platform failures,
                # never ordinary contestant penalties or leaderboard results.
                attempt.status = 'infrastructure_failed'; attempt.failure_class = 'v060_platform_failure'
                transition_submission(database, submission, SubmissionState.INFRASTRUCTURE_FAILED)
                if job.attempts < job.max_attempts:
                    transition_submission(database, submission, SubmissionState.QUEUED)
                    job.status = 'queued'; job.available_at = utcnow()+timedelta(seconds=5*job.attempts)
                    job.lease_owner = None; job.lease_expires_at = None
                else:
                    job.status = 'failed'
            attempt.finished_at = utcnow()
            database.commit()
            return True
