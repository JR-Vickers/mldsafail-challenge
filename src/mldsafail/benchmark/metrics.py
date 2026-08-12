"""Correctness-first measurement with frozen per-instance resource limits."""

from __future__ import annotations

import multiprocessing
import queue
import resource
import statistics
import sys
import time
import tomllib
import tracemalloc
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mldsafail import __version__
from mldsafail.benchmark.cost_model import COST_MODEL_VERSION, OperationMeter
from mldsafail.models import (
    Candidate,
    ChallengeInstance,
    InstanceMetrics,
    ProfileMetrics,
    VerificationResult,
)

Solver = Callable[[ChallengeInstance, OperationMeter], Candidate]
Verifier = Callable[[ChallengeInstance, Candidate], VerificationResult]

_SOURCE_CONTRACT = Path(__file__).resolve().parents[3] / "config" / "benchmark.toml"
_PACKAGED_CONTRACT = Path(__file__).with_name("contract.toml")


@dataclass(frozen=True)
class ResourceLimits:
    wall_seconds: float
    peak_memory_bytes: int


def load_resource_limits(path: str | Path | None = None) -> ResourceLimits:
    contract_path = Path(path) if path else (
        _SOURCE_CONTRACT if _SOURCE_CONTRACT.is_file() else _PACKAGED_CONTRACT
    )
    with contract_path.open("rb") as stream:
        values = tomllib.load(stream)
    if values.get("benchmark_version") != __version__:
        raise ValueError("resource contract benchmark version does not match the package")
    if values.get("cost_model_version") != COST_MODEL_VERSION:
        raise ValueError("resource contract cost-model version does not match the package")
    wall = values.get("per_instance_wall_seconds")
    memory = values.get("per_instance_peak_memory_bytes")
    if (
        isinstance(wall, bool) or not isinstance(wall, (int, float)) or wall <= 0
        or isinstance(memory, bool) or not isinstance(memory, int) or memory <= 0
    ):
        raise ValueError("resource limits must be positive numbers")
    return ResourceLimits(float(wall), memory)


DEFAULT_RESOURCE_LIMITS = load_resource_limits()


def _peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Darwin reports bytes; Linux and most BSDs report KiB.
    return int(value if sys.platform == "darwin" else value * 1024)


def _run_solve(
    instance: ChallengeInstance, solver: Solver, verifier: Verifier
) -> InstanceMetrics:
    meter = OperationMeter()
    tracemalloc.start()
    started = time.perf_counter()
    try:
        candidate = solver(instance, meter)
        verification = verifier(instance, candidate)
        failure = None if verification.valid else verification.reason
        correct = verification.valid
        quality = verification.solution_quality if verification.valid else None
    except Exception as exc:
        correct = False
        quality = None
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        elapsed = time.perf_counter() - started
        _, traced_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    return InstanceMetrics(
        instance_id=instance.instance_id,
        correct=correct,
        wall_seconds=elapsed,
        peak_memory_bytes=max(traced_peak, _peak_rss_bytes()),
        solution_quality=quality,
        cost=meter.snapshot().to_dict(),
        failure_reason=failure,
    )


def _worker(
    output: multiprocessing.Queue[Any],
    instance: ChallengeInstance,
    solver: Solver,
    verifier: Verifier,
) -> None:
    output.put(_run_solve(instance, solver, verifier))


def measure_instance(
    instance: ChallengeInstance,
    solver: Solver,
    verifier: Verifier,
    limits: ResourceLimits | None = None,
) -> InstanceMetrics:
    """Measure one solve; use a terminable worker when limits are requested."""

    if limits is None:
        return _run_solve(instance, solver, verifier)
    context = multiprocessing.get_context("fork")
    output: multiprocessing.Queue[Any] = context.Queue(maxsize=1)
    process = context.Process(target=_worker, args=(output, instance, solver, verifier))
    process.start()
    process.join(limits.wall_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        output.close()
        return InstanceMetrics(
            instance_id=instance.instance_id,
            correct=False,
            wall_seconds=limits.wall_seconds,
            peak_memory_bytes=0,
            solution_quality=None,
            cost=OperationMeter().snapshot().to_dict(),
            failure_reason=f"resource limit exceeded: wall time > {limits.wall_seconds:g}s",
            resource_status="time_exceeded",
        )
    try:
        measured = output.get(timeout=1)
    except queue.Empty:
        return InstanceMetrics(
            instance_id=instance.instance_id,
            correct=False,
            wall_seconds=0.0,
            peak_memory_bytes=0,
            solution_quality=None,
            cost=OperationMeter().snapshot().to_dict(),
            failure_reason=f"benchmark worker exited without a result (code {process.exitcode})",
            resource_status="worker_failed",
        )
    finally:
        output.close()
    if measured.peak_memory_bytes > limits.peak_memory_bytes:
        measured.correct = False
        measured.solution_quality = None
        measured.failure_reason = (
            "resource limit exceeded: peak memory "
            f"{measured.peak_memory_bytes} > {limits.peak_memory_bytes} bytes"
        )
        measured.resource_status = "memory_exceeded"
    return measured


def aggregate_profile(profile: str, instances: Iterable[InstanceMetrics]) -> ProfileMetrics:
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
        abstract_cost=sum(int(item.cost["total"]) for item in measured) if correct else 0,
        solution_quality=int(statistics.median(qualities)) if correct and qualities else None,
    )


def measure_profile(
    profile: str,
    instances: Iterable[ChallengeInstance],
    solver: Solver,
    verifier: Verifier,
    limits: ResourceLimits = DEFAULT_RESOURCE_LIMITS,
) -> ProfileMetrics:
    return aggregate_profile(
        profile,
        (measure_instance(instance, solver, verifier, limits) for instance in instances),
    )
