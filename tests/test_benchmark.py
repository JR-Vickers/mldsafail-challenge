from __future__ import annotations

from mldsafail.benchmark.comparison import best_per_metric, dominates, pareto_frontier
from mldsafail.benchmark.metrics import aggregate_profile, measure_instance
from mldsafail.benchmark.suites import load_seed_suite, selected_suites
from mldsafail.models import Candidate, CostCounter, ToyInstance, VerificationResult


INSTANCE = ToyInstance(
    instance_id="unit", seed=7, profile="toy-small", dimension=1,
    modulus=97, eta=2, matrix=((1,),), target=(1,),
)


def good_solver(instance: ToyInstance, cost: CostCounter) -> Candidate:
    cost.additions += 2
    return Candidate((1,))


def verifier(instance: ToyInstance, candidate: Candidate) -> VerificationResult:
    valid = candidate.coefficients == (1,)
    return VerificationResult(valid, "ok" if valid else "wrong", 1 if valid else None)


def test_measurement_verifies_and_aggregates():
    result = measure_instance(INSTANCE, good_solver, verifier)
    aggregate = aggregate_profile("toy-small", [result])
    assert result.correct
    assert aggregate.correct
    assert aggregate.abstract_cost == result.cost["total"] == 2
    assert aggregate.solution_quality == 1


def test_invalid_output_has_no_scored_cost():
    result = measure_instance(INSTANCE, lambda _i, _c: Candidate((2,)), verifier)
    aggregate = aggregate_profile("toy-small", [result])
    assert not aggregate.correct
    assert aggregate.abstract_cost == 0
    assert aggregate.solution_quality is None


def test_solver_exception_becomes_failure_metric():
    def fail(_instance, _cost):
        raise RuntimeError("expected")

    result = measure_instance(INSTANCE, fail, verifier)
    assert not result.correct
    assert result.failure_reason == "RuntimeError: expected"


def test_seed_suites_and_full_semantics():
    assert selected_suites("full") == ("public", "hidden")
    assert set(load_seed_suite("public", "toy-small")) == {"toy-small"}


def record(identifier, values, correct=True):
    return {"experiment_id": identifier, "correct": correct, "aggregate": values}


def test_pareto_and_best_per_metric_ignore_invalid():
    metrics = ("total_wall_seconds", "median_instance_seconds", "peak_memory_bytes", "abstract_cost", "solution_quality")
    fast = record("fast", dict(zip(metrics, (1, 1, 10, 10, 2), strict=True)))
    cheap = record("cheap", dict(zip(metrics, (2, 2, 9, 8, 1), strict=True)))
    worse = record("worse", dict(zip(metrics, (3, 3, 12, 12, 3), strict=True)))
    invalid = record("invalid", {}, False)
    assert dominates(fast["aggregate"], worse["aggregate"])
    assert {item["experiment_id"] for item in pareto_frontier([fast, cheap, worse, invalid])} == {"fast", "cheap"}
    assert best_per_metric([fast, cheap, invalid])["abstract_cost"] is cheap
