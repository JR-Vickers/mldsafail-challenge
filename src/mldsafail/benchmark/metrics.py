"""Correctness-first measurement and aggregation."""

from __future__ import annotations

import statistics
import time
import tracemalloc
from collections.abc import Callable, Iterable

from mldsafail.benchmark.cost_model import OperationMeter
from mldsafail.models import (
    Candidate,
    ChallengeInstance,
    InstanceMetrics,
    ProfileMetrics,
    VerificationResult,
)

Solver = Callable[[ChallengeInstance, OperationMeter], Candidate]
Verifier = Callable[[ChallengeInstance, Candidate], VerificationResult]


def measure_instance(instance: ChallengeInstance, solver: Solver, verifier: Verifier) -> InstanceMetrics:
    """Measure one solve and independently verify its output."""

    cost = OperationMeter()
    tracemalloc.start()
    started = time.perf_counter()
    try:
        candidate = solver(instance, cost)
        verification = verifier(instance, candidate)
        failure = None if verification.valid else verification.reason
        correct = verification.valid
        quality = verification.solution_quality if verification.valid else None
    except Exception as exc:  # benchmark failures are data, not runner crashes
        correct = False
        quality = None
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    return InstanceMetrics(
        instance_id=instance.instance_id,
        correct=correct,
        wall_seconds=elapsed,
        peak_memory_bytes=peak,
        solution_quality=quality,
        cost=cost.snapshot().to_dict(),
        failure_reason=failure,
    )


def aggregate_profile(profile: str, instances: Iterable[InstanceMetrics]) -> ProfileMetrics:
    """Aggregate metrics without assigning a score to an invalid profile."""

    measured = list(instances)
    correct = bool(measured) and all(item.correct for item in measured)
    qualities = [item.solution_quality for item in measured if item.solution_quality is not None]
    return ProfileMetrics(
        profile=profile,
        instances=measured,
        correct=correct,
        total_wall_seconds=sum(item.wall_seconds for item in measured),
        median_instance_seconds=statistics.median(item.wall_seconds for item in measured) if measured else 0.0,
        peak_memory_bytes=max((item.peak_memory_bytes for item in measured), default=0),
        # Invalid output has no scored cost or quality, as required by the
        # benchmark contract.
        abstract_cost=sum(int(item.cost["total"]) for item in measured) if correct else 0,
        solution_quality=int(statistics.median(qualities)) if correct and qualities else None,
    )


def measure_profile(
    profile: str,
    instances: Iterable[ChallengeInstance],
    solver: Solver,
    verifier: Verifier,
) -> ProfileMetrics:
    return aggregate_profile(
        profile,
        (measure_instance(instance, solver, verifier) for instance in instances),
    )
