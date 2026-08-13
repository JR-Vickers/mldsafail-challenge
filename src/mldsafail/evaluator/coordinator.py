"""Dedicated coordinator process; the public web service never receives Docker access."""

from __future__ import annotations

import argparse
import os
import socket
import tempfile
import time
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mldsafail.evaluator.docker import run_worker
from mldsafail.evaluator.envelope import EnvelopeError, verify_envelope
from mldsafail.evaluator.queue import claim_job
from mldsafail.evaluator.source import acquire_commit, assemble_harness, validate_eligible_source
from mldsafail.benchmark.cost_model import CATEGORIES, CostSnapshot
from mldsafail.benchmark.suites import load_seed_suite
from mldsafail.models import Candidate
from mldsafail.trusted.generator import generate_instance
from mldsafail.trusted.verifier import verify
from mldsafail.web.models import EvaluationAttempt, ExperimentResult, Submission, SubmissionState, utcnow
from mldsafail.web.services import DomainError, sanitize_log, transition_submission


@dataclass(frozen=True)
class CoordinatorConfig:
    database_url: str
    trusted_checkout: Path
    hidden_seeds: Path
    worker_image: str
    benchmark_version: str
    evaluator_fingerprint: str
    hidden_suite_version: str
    worker_class: str = "rootless-docker-v1"
    work_root: Path = Path("/srv/mldsafail-evaluator")


class Coordinator:
    def __init__(self, config: CoordinatorConfig):
        self.config = config
        if not config.hidden_seeds.is_file():
            raise RuntimeError("hidden seed secret is missing")
        os.environ["MLDSAFAIL_HIDDEN_SEEDS_PATH"] = str(config.hidden_seeds)
        self.engine = create_engine(config.database_url, pool_pre_ping=True)
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}"

    def run_once(self) -> bool:
        with Session(self.engine) as database:
            job = claim_job(database, self.worker_id)
            if job is None:
                return False
            submission = database.get(Submission, job.submission_id)
            attempt = EvaluationAttempt(job_id=job.id, number=job.attempts, worker_id=self.worker_id, status="validating")
            database.add(attempt); database.commit()
            try:
                self.config.work_root.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix="job-", dir=self.config.work_root) as temporary:
                    base = Path(temporary)
                    checkout = acquire_commit(submission.repository_url, submission.commit_sha, base / "source")
                    eligible = validate_eligible_source(checkout)
                    harness = base / "harness"
                    assemble_harness(self.config.trusted_checkout, eligible, harness)
                    key = os.urandom(32)
                    metadata = {
                        "MLDSAFAIL_SOURCE_DIGEST": eligible.digest,
                        "MLDSAFAIL_BENCHMARK_VERSION": self.config.benchmark_version,
                        "MLDSAFAIL_EVALUATOR_FINGERPRINT": self.config.evaluator_fingerprint,
                        "MLDSAFAIL_HIDDEN_SUITE_VERSION": self.config.hidden_suite_version,
                        "MLDSAFAIL_WORKER_CLASS": self.config.worker_class,
                    }
                    job.status = "running"; attempt.status = "running"
                    transition_submission(database, submission, SubmissionState.RUNNING); database.commit()
                    instances = self._instances()
                    wire_instances = [asdict(instance) | {"seed": 0} for instance in instances]
                    envelope = run_worker(self.config.worker_image, harness, key, wire_instances, metadata)
                    payload = verify_envelope(envelope, key, {name.removeprefix("MLDSAFAIL_").lower(): value for name, value in metadata.items()})
                    verified, score, safe_diagnostics = self._verify_results(instances, payload["diagnostics"])
                    attempt.finished_at = utcnow()
                    database.refresh(submission)
                    if submission.cancel_requested:
                        attempt.status = "cancelled"; job.status = "complete"
                        transition_submission(database, submission, SubmissionState.CANCELLED, "cancellation completed")
                    elif payload["verified"] and verified and payload["score"] == score:
                        database.add(ExperimentResult(
                            submission_id=submission.id, user_id=submission.user_id, score=score, verified=True,
                            source_digest=payload["source_digest"], benchmark_version=payload["benchmark_version"],
                            evaluator_fingerprint=payload["evaluator_fingerprint"], hidden_suite_version=payload["hidden_suite_version"],
                            worker_class=payload["worker_class"], diagnostics=safe_diagnostics,
                        ))
                        attempt.status = "accepted"; job.status = "complete"
                        transition_submission(database, submission, SubmissionState.ACCEPTED)
                    else:
                        failure = payload["failure_class"] or "independent_verification_failed"
                        attempt.status = "rejected"; attempt.failure_class = failure
                        job.status = "complete"; submission.rejection_code = failure
                        transition_submission(database, submission, SubmissionState.REJECTED, "worker verification failed")
                    database.commit()
            except DomainError as exception:
                self._reject(database, submission, job, attempt, exception.code, exception.message)
            except (EnvelopeError, TimeoutError) as exception:
                self._reject(database, submission, job, attempt, "invalid_worker_output", str(exception))
            except (OSError, RuntimeError) as exception:
                attempt.status = "infrastructure_failed"; attempt.failure_class = type(exception).__name__
                attempt.log = sanitize_log(str(exception)); attempt.finished_at = utcnow(); job.status = "failed"
                transition_submission(database, submission, SubmissionState.INFRASTRUCTURE_FAILED, "evaluation platform failure")
                database.commit()
            return True

    def _instances(self):
        selections = []
        for suite in ("public", "hidden"):
            for profile, seeds in load_seed_suite(suite).items():
                selections.extend(generate_instance(seed, profile) for seed in seeds)
        return selections

    @staticmethod
    def _verify_results(instances, diagnostics):
        results = diagnostics.get("results") if isinstance(diagnostics, dict) else None
        if not isinstance(results, list) or len(results) != len(instances):
            return False, None, {}
        score = 0; wall = 0.0
        for instance, item in zip(instances, results, strict=True):
            try:
                if item["instance_id"] != instance.instance_id:
                    return False, None, {}
                candidate = Candidate(tuple(item["coefficients"]))
                if not verify(instance, candidate).valid:
                    return False, None, {}
                cost = item["cost"]
                snapshot = CostSnapshot(cost["version"], *(cost[name] for name in CATEGORIES))
                if cost.get("total") != snapshot.weighted_total or cost.get("raw_total") != snapshot.raw_total:
                    return False, None, {}
                score += snapshot.weighted_total
                wall += float(item["wall_seconds"])
            except (KeyError, TypeError, ValueError, OverflowError):
                return False, None, {}
        return True, score, {"total_wall_seconds": wall, "instance_count": len(instances)}

    @staticmethod
    def _reject(database, submission, job, attempt, code, message):
        attempt.status = "rejected"; attempt.failure_class = code; attempt.log = sanitize_log(message); attempt.finished_at = utcnow()
        job.status = "complete"; submission.rejection_code = code
        current = SubmissionState(submission.state)
        if current in {SubmissionState.VALIDATING, SubmissionState.RUNNING}:
            transition_submission(database, submission, SubmissionState.REJECTED, code)
        database.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    config = CoordinatorConfig(
        database_url=os.environ["MLDSAFAIL_DATABASE_URL"], trusted_checkout=Path(os.environ.get("MLDSAFAIL_TRUSTED_CHECKOUT", "/opt/mldsafail")),
        hidden_seeds=Path(os.environ["MLDSAFAIL_HIDDEN_SEEDS_PATH"]), worker_image=os.environ["MLDSAFAIL_WORKER_IMAGE"],
        benchmark_version=os.environ.get("MLDSAFAIL_BENCHMARK_VERSION", "0.3.0"), evaluator_fingerprint=os.environ["MLDSAFAIL_EVALUATOR_FINGERPRINT"],
        hidden_suite_version=os.environ["MLDSAFAIL_HIDDEN_SUITE_VERSION"], worker_class=os.environ.get("MLDSAFAIL_WORKER_CLASS", "rootless-docker-v1"),
        work_root=Path(os.environ.get("MLDSAFAIL_EVALUATOR_WORK_ROOT", "/srv/mldsafail-evaluator")),
    )
    coordinator = Coordinator(config)
    while True:
        worked = coordinator.run_once()
        if args.once:
            return 0
        if not worked:
            time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
