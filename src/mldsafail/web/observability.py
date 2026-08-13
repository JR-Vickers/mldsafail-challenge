"""Small dependency-free metrics and structured request logging."""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone

from flask import Response, request
from sqlalchemy import func, select

from mldsafail.web.db import get_session
from mldsafail.web.models import EvaluationAttempt, EvaluationJob, Submission


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname.lower(),
            "logger": record.name, "message": record.getMessage(),
        }, separators=(",", ":"))


def init_observability(app) -> None:
    counters = Counter()
    app.extensions["mldsafail_metrics"] = counters
    if not app.testing:
        handler = logging.StreamHandler(); handler.setFormatter(JsonFormatter())
        app.logger.handlers[:] = [handler]; app.logger.setLevel(logging.INFO)

    @app.before_request
    def request_started():
        request.environ["mldsafail.started"] = time.monotonic()

    @app.after_request
    def request_finished(response):
        counters["http_requests_total"] += 1
        if response.status_code >= 400:
            counters["http_request_failures_total"] += 1
        if response.status_code == 401:
            counters["authentication_failures_total"] += 1
        elapsed = time.monotonic() - request.environ.get("mldsafail.started", time.monotonic())
        app.logger.info(json.dumps({"event": "request", "method": request.method, "path": request.path,
                                   "status": response.status_code, "duration_seconds": round(elapsed, 6)}, separators=(",", ":")))
        return response

    @app.get("/metrics")
    def metrics():
        values = dict(counters)
        if app.config.get("DATABASE_URL"):
            database = get_session()
            values["evaluation_queue_depth"] = database.scalar(select(func.count()).select_from(EvaluationJob).where(EvaluationJob.status == "queued")) or 0
            for state in ("accepted", "rejected", "infrastructure_failed"):
                values[f"submissions_{state}_total"] = database.scalar(select(func.count()).select_from(Submission).where(Submission.state == state)) or 0
            values["worker_failures_total"] = database.scalar(
                select(func.count()).select_from(EvaluationAttempt).where(
                    EvaluationAttempt.status == "infrastructure_failed"
                )
            ) or 0
            completed = database.scalars(
                select(EvaluationAttempt).where(EvaluationAttempt.finished_at.is_not(None)).order_by(
                    EvaluationAttempt.finished_at.desc()
                ).limit(1000)
            ).all()
            durations = [(item.finished_at - item.started_at).total_seconds() for item in completed]
            values["job_latency_seconds"] = round(sum(durations) / len(durations), 6) if durations else 0
        lines = ["# TYPE mldsafail gauge"] + [f"mldsafail_{name} {value}" for name, value in sorted(values.items())]
        return Response("\n".join(lines) + "\n", mimetype="text/plain")
