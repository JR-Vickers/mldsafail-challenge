"""Transactional hosted-challenge domain operations."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from pathlib import PurePosixPath

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mldsafail.web.models import (
    ApiToken, AuditEvent, EvaluationJob, IdempotencyKey, RateLimitState,
    Submission, SubmissionState, SubmissionTransition, TERMINAL_STATES, User, utcnow,
)

TOKEN_RE = re.compile(r"^mldsa_([A-Za-z0-9]{10})_([A-Za-z0-9_-]{43})$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
ALLOWED_TRANSITIONS = {
    SubmissionState.QUEUED: {SubmissionState.VALIDATING, SubmissionState.CANCELLED},
    SubmissionState.VALIDATING: {SubmissionState.RUNNING, SubmissionState.REJECTED, SubmissionState.CANCELLED, SubmissionState.INFRASTRUCTURE_FAILED},
    SubmissionState.RUNNING: {SubmissionState.ACCEPTED, SubmissionState.REJECTED, SubmissionState.CANCELLED, SubmissionState.INFRASTRUCTURE_FAILED},
    SubmissionState.INFRASTRUCTURE_FAILED: {SubmissionState.QUEUED},
}
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)
dummy_token_hash = password_hasher.hash("constant-time-invalid-token-check")


class DomainError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def audit(session: Session, event_type: str, user_id: str | None, **detail) -> None:
    session.add(AuditEvent(event_type=event_type, user_id=user_id, detail=detail))


def create_api_token(
    session: Session, user: User, name: str, *, expires_at: datetime | None = None,
    creation_request_key: str | None = None,
) -> tuple[ApiToken, str | None]:
    if creation_request_key is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", creation_request_key):
            raise DomainError("invalid_creation_request", "Reload the token form and try again.")
        existing = session.scalar(select(ApiToken).where(
            ApiToken.user_id == user.id, ApiToken.creation_request_key == creation_request_key))
        if existing:
            return existing, None
    if not name.strip() or len(name) > 100:
        raise DomainError("invalid_token_name", "Token name must be between 1 and 100 characters.")
    prefix = secrets.token_hex(5)
    secret = secrets.token_urlsafe(32)
    plaintext = f"mldsa_{prefix}_{secret}"
    token = ApiToken(
        user_id=user.id, prefix=prefix, secret_hash=password_hasher.hash(secret), name=name.strip(),
        scopes=["submission:write", "submission:read"], expires_at=expires_at,
        creation_request_key=creation_request_key,
    )
    session.add(token)
    audit(session, "api_token.created", user.id, token_id=token.id, prefix=prefix)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if creation_request_key is not None:
            existing = session.scalar(select(ApiToken).where(
                ApiToken.user_id == user.id, ApiToken.creation_request_key == creation_request_key))
            if existing:
                return existing, None
        raise
    return token, plaintext


def verify_api_token(session: Session, plaintext: str, required_scope: str | None = None) -> tuple[User, ApiToken] | None:
    match = TOKEN_RE.fullmatch(plaintext)
    if not match:
        return None
    prefix, secret = match.groups()
    token = session.scalar(select(ApiToken).where(ApiToken.prefix == prefix))
    candidate_hash = token.secret_hash if token is not None else dummy_token_hash
    try:
        secret_matches = password_hasher.verify(candidate_hash, secret)
    except (VerifyMismatchError, InvalidHashError):
        secret_matches = False
    if token is None or not secret_matches or token.revoked_at is not None:
        return None
    now = utcnow()
    expiry = token.expires_at
    if expiry is not None:
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= now:
            return None
    if required_scope and required_scope not in token.scopes:
        return None
    token.last_used_at = now
    user = session.get(User, token.user_id)
    session.commit()
    return (user, token) if user else None


def revoke_token(session: Session, token: ApiToken, user: User) -> None:
    if token.user_id != user.id:
        raise DomainError("not_found", "Token not found.", 404)
    if token.revoked_at is None:
        token.revoked_at = utcnow()
        audit(session, "api_token.revoked", user.id, token_id=token.id, prefix=token.prefix)
        session.commit()


def valid_repository_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme == "file":
        # Local development: allow file:// URLs for testing the pipeline.
        path = parsed.path
        if not path or not path.startswith("/"):
            raise DomainError("invalid_repository", "file:// URL must have an absolute path.")
        return value
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        raise DomainError("invalid_repository", "Repository must be a public GitHub HTTPS URL.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise DomainError("invalid_repository", "Repository URL must identify one GitHub owner and repository.")
    repository = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
    if not repository:
        raise DomainError("invalid_repository", "Repository name is empty.")
    return f"https://github.com/{parts[0]}/{repository}.git"


def _request_digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def create_submission(session: Session, user: User, payload: dict, idempotency_key: str,
                      *, cohort: dict | None = None) -> tuple[Submission, bool]:
    if not idempotency_key or len(idempotency_key) > 128:
        raise DomainError("invalid_idempotency_key", "A valid Idempotency-Key header is required.")
    allowed = {"repository_url", "commit_sha", "hypothesis", "notes", "tags", "benchmark_version",
               "epoch_id", "evaluator_fingerprint", "hidden_suite_version", "worker_class", "solver_path"}
    if set(payload) - allowed:
        raise DomainError("unknown_fields", "Request contains unsupported fields.")
    repository_url = valid_repository_url(str(payload.get("repository_url", "")))
    commit_sha = str(payload.get("commit_sha", ""))
    if not SHA_RE.fullmatch(commit_sha):
        raise DomainError("invalid_commit", "Commit must be a full 40-character hexadecimal SHA.")
    hypothesis = str(payload.get("hypothesis", "")).strip()
    notes = str(payload.get("notes", ""))
    tags = payload.get("tags", [])
    benchmark_version = str(payload.get("benchmark_version", "0.4.0"))
    if not hypothesis or len(hypothesis) > 2000 or len(notes) > 5000:
        raise DomainError("invalid_text", "Hypothesis is required and text fields must be within limits.")
    if not isinstance(tags, list) or len(tags) > 10 or not all(isinstance(tag, str) and 0 < len(tag) <= 40 for tag in tags):
        raise DomainError("invalid_tags", "Tags must be a list of at most 10 short strings.")
    normalized = {"repository_url": repository_url, "commit_sha": commit_sha.lower(), "hypothesis": hypothesis,
                  "notes": notes, "tags": tags, "benchmark_version": benchmark_version}
    if benchmark_version == "0.5.0":
        if not cohort or not all(cohort.get(name) for name in
                                ("epoch_id", "evaluator_fingerprint", "hidden_suite_version", "worker_class")):
            raise DomainError("epoch_unavailable", "The MLWE cohort is not configured.", 503)
        for name, value in cohort.items():
            if name in payload and payload[name] != value:
                raise DomainError("incompatible_cohort", "The requested evaluation cohort is incompatible.", 422)
        normalized.update(cohort)
        solver_path = payload.get("solver_path", "src/mldsafail/solver")
        if (not isinstance(solver_path, str) or not solver_path or len(solver_path) > 200
                or PurePosixPath(solver_path).is_absolute() or ".." in PurePosixPath(solver_path).parts
                or any(part.startswith(".") for part in solver_path.split("/"))
                or str(PurePosixPath(solver_path)) != solver_path):
            raise DomainError("invalid_solver_path", "Solver directory must be a normalized repository-relative path.", 422)
        normalized["solver_path"] = solver_path
    elif any(name in payload for name in allowed - set(normalized)):
        raise DomainError("incompatible_cohort", "Epoch fields require MLWE 0.5.0.", 422)
    digest = _request_digest(normalized)
    existing = session.scalar(select(IdempotencyKey).where(IdempotencyKey.user_id == user.id, IdempotencyKey.key == idempotency_key))
    if existing:
        if existing.request_hash != digest:
            raise DomainError("idempotency_conflict", "This idempotency key was used for a different request.", 409)
        return session.get(Submission, existing.submission_id), False
    submission = Submission(user_id=user.id, **normalized)
    session.add(submission)
    session.flush()
    session.add_all([
        SubmissionTransition(submission_id=submission.id, from_state=None, to_state=SubmissionState.QUEUED.value),
        EvaluationJob(submission_id=submission.id),
        IdempotencyKey(user_id=user.id, key=idempotency_key, request_hash=digest, submission_id=submission.id),
    ])
    audit(session, "submission.created", user.id, submission_id=submission.id)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(select(IdempotencyKey).where(IdempotencyKey.user_id == user.id, IdempotencyKey.key == idempotency_key))
        if existing and existing.request_hash == digest:
            return session.get(Submission, existing.submission_id), False
        raise DomainError("idempotency_conflict", "This idempotency key was used concurrently.", 409) from None
    return submission, True


def transition_submission(session: Session, submission: Submission, target: SubmissionState, reason: str | None = None) -> None:
    current = SubmissionState(submission.state)
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise DomainError("invalid_state_transition", f"Cannot transition {current.value} to {target.value}.", 409)
    submission.state = target.value
    submission.updated_at = utcnow()
    session.add(SubmissionTransition(submission_id=submission.id, from_state=current.value, to_state=target.value, reason=reason))
    audit(session, "submission.transitioned", submission.user_id, submission_id=submission.id, from_state=current.value, to_state=target.value)


def cancel_submission(session: Session, submission: Submission) -> None:
    current = SubmissionState(submission.state)
    if current in TERMINAL_STATES:
        raise DomainError("already_terminal", "Submission is already in a terminal state.", 409)
    if current is SubmissionState.RUNNING:
        submission.cancel_requested = True
        audit(session, "submission.cancellation_requested", submission.user_id, submission_id=submission.id)
    else:
        transition_submission(session, submission, SubmissionState.CANCELLED, "cancelled by participant")
    session.commit()


def check_rate_limit(session: Session, bucket: str, *, limit: int, seconds: int) -> None:
    now = utcnow()
    state = session.scalar(select(RateLimitState).where(RateLimitState.bucket == bucket).with_for_update())
    if state is None:
        state = RateLimitState(bucket=bucket, count=1, window_started_at=now)
        session.add(state)
    else:
        started = state.window_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if now - started >= timedelta(seconds=seconds):
            state.window_started_at, state.count = now, 1
        elif state.count >= limit:
            raise DomainError("rate_limited", "Too many requests; try again later.", 429)
        else:
            state.count += 1
    session.commit()


def sanitize_log(value: str, limit: int = 64 * 1024) -> str:
    value = re.sub(r"mldsa_[A-Za-z0-9]{10}_[A-Za-z0-9_-]{43}", "[REDACTED_TOKEN]", value)
    value = re.sub(r"/(?:run/secrets|workspace/hidden|var/lib/mldsafail)/[^\s:]+", "[REDACTED_PATH]", value)
    return value[-limit:]
