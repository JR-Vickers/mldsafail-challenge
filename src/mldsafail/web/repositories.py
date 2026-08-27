"""Adapters exposing one dashboard record contract for local and hosted data."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from mldsafail.web.models import ExperimentResult


class ResultRepository(Protocol):
    def records(self) -> tuple[list[dict], int]: ...


class JsonlResultRepository:
    def __init__(self, path: Path):
        self.path = path

    def records(self) -> tuple[list[dict], int]:
        from mldsafail.web.app import load_experiments
        return load_experiments(self.path)


class DatabaseResultRepository:
    def __init__(self, session: Session, jsonl_path: Path | None = None):
        self.session = session
        self.jsonl_path = jsonl_path

    def records(self) -> tuple[list[dict], int]:
        results = self.session.scalars(
            select(ExperimentResult).where(ExperimentResult.verified.is_(True)).order_by(
                ExperimentResult.accepted_at.desc(), ExperimentResult.id
            )
        ).all()
        if results:
            return [self._record(result) for result in results], 0
        if self.jsonl_path and self.jsonl_path.exists():
            from mldsafail.web.app import load_experiments
            return load_experiments(self.jsonl_path)
        return [], 0

    @staticmethod
    def _record(result: ExperimentResult) -> dict:
        submission = result.submission
        user = result.user
        suites = {"public": {name: {} for name in ("small", "medium", "large")},
                  "hidden": {name: {} for name in ("small", "medium", "large")}}
        return {
            "schema_version": "hosted-1",
            "benchmark_version": result.benchmark_version,
            "experiment_id": result.id,
            "timestamp": result.accepted_at.isoformat(),
            "agent": user.display_name,
            "participant": {"name": user.display_name, "avatar_url": user.avatar_url},
            "hypothesis": submission.hypothesis,
            "tags": submission.tags,
            "notes": submission.notes,
            "correct": True,
            "score": result.score,
            "aggregate": {"score": result.score},
            "profiles": {},
            "suites": suites,
            "integrity": {"trusted_fingerprint": result.evaluator_fingerprint},
            "provenance": {
                "repository_url": submission.repository_url,
                "commit_sha": submission.commit_sha,
                "source_digest": result.source_digest,
                "hidden_suite_version": result.hidden_suite_version,
                "worker_class": result.worker_class,
            },
        }
