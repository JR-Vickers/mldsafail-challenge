"""PostgreSQL lease queue with concurrent skip-locked claims."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from mldsafail.web.models import EvaluationAttempt, EvaluationJob, Submission, SubmissionState, utcnow
from mldsafail.web.services import transition_submission


def claim_job(session: Session, worker_id: str, lease_seconds: int = 120,
              benchmark_version: str | None = None) -> EvaluationJob | None:
    now = utcnow()
    job = session.scalar(
        select(EvaluationJob).join(Submission, Submission.id == EvaluationJob.submission_id).where(
            EvaluationJob.status == "queued", EvaluationJob.available_at <= now,
            Submission.state == SubmissionState.QUEUED.value,
            *([Submission.benchmark_version == benchmark_version] if benchmark_version else []),
        ).order_by(EvaluationJob.created_at, EvaluationJob.id).with_for_update(skip_locked=True).limit(1)
    )
    if job is None:
        session.rollback()
        return None
    job.status = "claimed"; job.lease_owner = worker_id; job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.heartbeat_at = now; job.attempts += 1
    submission = session.get(Submission, job.submission_id)
    if submission.state == SubmissionState.QUEUED.value:
        transition_submission(session, submission, SubmissionState.VALIDATING)
    session.commit()
    return job


def heartbeat(session: Session, job_id: str, worker_id: str, lease_seconds: int = 120) -> bool:
    job = session.get(EvaluationJob, job_id)
    if job is None or job.lease_owner != worker_id or job.status not in {"claimed", "running"}:
        session.rollback(); return False
    job.heartbeat_at = utcnow(); job.lease_expires_at = utcnow() + timedelta(seconds=lease_seconds)
    session.commit(); return True


def recover_stale_jobs(session: Session) -> tuple[int, int]:
    now = utcnow(); retried = failed = 0
    jobs = session.scalars(select(EvaluationJob).where(EvaluationJob.status.in_(["claimed", "running"]), EvaluationJob.lease_expires_at < now).with_for_update(skip_locked=True)).all()
    for job in jobs:
        attempt = session.scalar(select(EvaluationAttempt).where(
            EvaluationAttempt.job_id == job.id, EvaluationAttempt.number == job.attempts))
        if attempt is not None:
            attempt.status = "infrastructure_failed"
            attempt.failure_class = "lease_expired"
            attempt.log = "Evaluation lease expired."
            attempt.finished_at = now
        submission = session.get(Submission, job.submission_id)
        if submission.state == SubmissionState.CANCELLED.value:
            job.status = "complete"
            if attempt is not None:
                attempt.status = "cancelled"
            continue
        if job.attempts < job.max_attempts:
            job.status = "queued"; job.available_at = now; job.lease_owner = None; job.lease_expires_at = None
            transition_submission(session, submission, SubmissionState.INFRASTRUCTURE_FAILED, "worker lease expired")
            transition_submission(session, submission, SubmissionState.QUEUED, "retrying stale job")
            retried += 1
        else:
            job.status = "failed"
            transition_submission(session, submission, SubmissionState.INFRASTRUCTURE_FAILED, "worker lease expired")
            failed += 1
    session.commit()
    return retried, failed
