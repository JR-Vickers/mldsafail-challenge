"""Versioned participant API authenticated with scoped bearer tokens."""

from __future__ import annotations

from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import select

from mldsafail.web.db import get_session
from mldsafail.web.models import EvaluationAttempt, EvaluationJob, Submission
from mldsafail.web.services import DomainError, cancel_submission, check_rate_limit, create_submission, sanitize_log, verify_api_token

api = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def error(code: str, message: str, status: int):
    return jsonify(error={"code": code, "message": message}), status


@api.errorhandler(DomainError)
def domain_error(exception):
    return error(exception.code, exception.message, exception.status)


def token_required(scope: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            plaintext = header[7:] if header.startswith("Bearer ") else ""
            verified = verify_api_token(get_session(), plaintext, scope)
            if not verified:
                return error("invalid_token", "A valid bearer token with the required scope is needed.", 401)
            g.api_user, g.api_token = verified
            return view(*args, **kwargs)
        return wrapped
    return decorator


def serialize_submission(item: Submission) -> dict:
    return {
        "id": item.id, "repository_url": item.repository_url, "commit_sha": item.commit_sha,
        "hypothesis": item.hypothesis, "notes": item.notes, "tags": item.tags,
        "benchmark_version": item.benchmark_version, "state": item.state,
        "cancel_requested": item.cancel_requested, "rejection_code": item.rejection_code,
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
    }


def owned_submission(identifier: str) -> Submission:
    item = get_session().get(Submission, identifier)
    if item is None or item.user_id != g.api_user.id:
        raise DomainError("not_found", "Submission not found.", 404)
    return item


@api.get("/me")
@token_required("submission:read")
def me():
    return jsonify(id=g.api_user.id, display_name=g.api_user.display_name, scopes=g.api_token.scopes)


@api.post("/submissions")
@token_required("submission:write")
def submissions_create():
    check_rate_limit(get_session(), f"submission-create:{g.api_user.id}", limit=20, seconds=3600)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("invalid_json", "Request body must be a JSON object.", 400)
    if payload.get("benchmark_version", current_app.config["BENCHMARK_VERSION"]) != current_app.config["BENCHMARK_VERSION"]:
        return error("unsupported_benchmark", "The requested benchmark version is unsupported.", 422)
    item, created = create_submission(get_session(), g.api_user, payload, request.headers.get("Idempotency-Key", ""))
    return jsonify(submission=serialize_submission(item)), 201 if created else 200


@api.get("/submissions")
@token_required("submission:read")
def submissions_list():
    items = get_session().scalars(select(Submission).where(Submission.user_id == g.api_user.id).order_by(Submission.created_at.desc()).limit(100)).all()
    return jsonify(submissions=[serialize_submission(item) for item in items])


@api.get("/submissions/<identifier>")
@token_required("submission:read")
def submissions_get(identifier):
    return jsonify(submission=serialize_submission(owned_submission(identifier)))


@api.get("/submissions/<identifier>/logs")
@token_required("submission:read")
def submissions_logs(identifier):
    item = owned_submission(identifier)
    job = get_session().scalar(select(EvaluationJob).where(EvaluationJob.submission_id == item.id))
    attempts = [] if not job else get_session().scalars(select(EvaluationAttempt).where(EvaluationAttempt.job_id == job.id).order_by(EvaluationAttempt.number)).all()
    return jsonify(logs=[{"attempt": attempt.number, "status": attempt.status, "text": sanitize_log(attempt.log)} for attempt in attempts])


@api.post("/submissions/<identifier>/cancel")
@token_required("submission:write")
def submissions_cancel(identifier):
    item = owned_submission(identifier)
    cancel_submission(get_session(), item)
    return jsonify(submission=serialize_submission(item))


def init_api(app):
    app.register_blueprint(api)
