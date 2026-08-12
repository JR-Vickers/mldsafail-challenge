from __future__ import annotations

import json

import pytest

from mldsafail.benchmark import runner
from mldsafail.benchmark.comparison import best_per_metric, dominates, pareto_frontier
from mldsafail.benchmark.metrics import aggregate_profile, measure_instance
from mldsafail.benchmark.suites import load_seed_suite, selected_suites
from mldsafail.benchmark import suites as suites_module
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


def test_seed_suites_fall_back_to_packaged_resources(monkeypatch):
    monkeypatch.setattr(
        suites_module,
        "SUITE_FILES",
        {name: suites_module.PROJECT_ROOT / "missing" / path.name
         for name, path in suites_module.SUITE_FILES.items()},
    )
    assert load_seed_suite("hidden", "toy-medium") == {"toy-medium": (9201, 9202)}


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


def test_cli_serializes_solver_exception_as_unscored_failure(tmp_path, monkeypatch, capsys):
    def broken_solver(_instance, _cost):
        raise RuntimeError("solver exploded")

    monkeypatch.setattr(runner, "solve", broken_solver)
    monkeypatch.setattr(
        runner,
        "_integrity_status",
        lambda baseline: {
            "trusted_fingerprint": "trusted",
            "baseline_fingerprint": baseline,
            "matches_baseline": None,
        },
    )
    output = tmp_path / "experiments.jsonl"
    result = runner.main([
        "--profile", "toy-small", "--seed", "12345", "--output", str(output)
    ])
    printed = json.loads(capsys.readouterr().out)
    persisted = json.loads(output.read_text())
    assert result == 1
    assert printed == persisted
    assert persisted["correct"] is False
    assert persisted["solver"] == "balanced"
    assert persisted["aggregate"]["abstract_cost"] is None
    assert persisted["failure_reason"] == "RuntimeError: solver exploded"


def test_cli_records_integrity_mismatch_without_running_benchmark(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runner,
        "_integrity_status",
        lambda baseline: {
            "trusted_fingerprint": "current",
            "baseline_fingerprint": baseline,
            "matches_baseline": False,
        },
    )
    monkeypatch.setattr(
        runner, "run_benchmark", lambda **_kwargs: pytest.fail("benchmark should not run")
    )
    output = tmp_path / "experiments.jsonl"
    result = runner.main(["--baseline-fingerprint", "expected", "--output", str(output)])
    record = json.loads(output.read_text())
    assert result == 1
    assert record["integrity"]["matches_baseline"] is False
    assert "fingerprint" in record["failure_reason"]


def test_cli_selects_lazy_solver_and_records_name(tmp_path, monkeypatch, capsys):
    selected = {}

    def fake_run_benchmark(**kwargs):
        selected.update(kwargs)
        return {}, dict(runner.UNSCORED_AGGREGATE), False

    monkeypatch.setattr(runner, "run_benchmark", fake_run_benchmark)
    monkeypatch.setattr(
        runner,
        "_integrity_status",
        lambda baseline: {
            "trusted_fingerprint": "current",
            "baseline_fingerprint": baseline,
            "matches_baseline": None,
        },
    )
    output = tmp_path / "experiments.jsonl"
    assert runner.main(["--solver", "lazy", "--output", str(output)]) == 1
    capsys.readouterr()
    record = json.loads(output.read_text())
    assert selected["solver_name"] == "lazy"
    assert record["solver"] == "lazy"


def test_lazy_selection_runs_a_distinct_cost_model():
    _balanced_suites, balanced, balanced_correct = runner.run_benchmark(
        suite="public", profile="toy-medium", solver_name="balanced"
    )
    _lazy_suites, lazy, lazy_correct = runner.run_benchmark(
        suite="public", profile="toy-medium", solver_name="lazy"
    )
    assert balanced_correct and lazy_correct
    assert lazy["abstract_cost"] < balanced["abstract_cost"]


@pytest.mark.parametrize(
    "arguments",
    [
        ["--seed", "1"],
        ["--profile", "not-a-profile"],
        ["--solver", "not-a-solver"],
        ["--profile", "toy-small", "--seed", "1", "--suite", "hidden"],
        ["--profile", "toy-small", "--seed", "1", "--suite", "full"],
    ],
)
def test_cli_rejects_invalid_flag_combinations(arguments):
    with pytest.raises(SystemExit) as raised:
        runner.main(arguments)
    assert raised.value.code == 2
