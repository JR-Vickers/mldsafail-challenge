from __future__ import annotations

import json
import time

import pytest

from mldsafail.benchmark import runner
from mldsafail.benchmark.comparison import best_score_record, rankable_score, score_frontier
from mldsafail.benchmark.metrics import ResourceLimits, aggregate_profile, measure_instance
from mldsafail.benchmark.suites import load_seed_suite, selected_suites
from mldsafail.benchmark import suites as suites_module
from mldsafail.benchmark.cost_model import OperationMeter
from mldsafail.models import Candidate, ChallengeInstance, VerificationResult


INSTANCE = ChallengeInstance(
    instance_id="unit", seed=7, profile="small", dimension=1,
    modulus=97, eta=2, matrix=((1,),), target=(1,),
)


def good_solver(instance: ChallengeInstance, cost: OperationMeter) -> Candidate:
    cost.additions(2)
    return Candidate((1,))


def verifier(instance: ChallengeInstance, candidate: Candidate) -> VerificationResult:
    valid = candidate.coefficients == (1,)
    return VerificationResult(valid, "ok" if valid else "wrong", 1 if valid else None)


def test_measurement_verifies_and_aggregates():
    result = measure_instance(INSTANCE, good_solver, verifier)
    aggregate = aggregate_profile("small", [result])
    assert result.correct
    assert aggregate.correct
    assert aggregate.abstract_cost == result.cost["total"] == 2
    assert aggregate.solution_quality == 1


def test_invalid_output_has_no_scored_cost():
    result = measure_instance(INSTANCE, lambda _i, _c: Candidate((2,)), verifier)
    aggregate = aggregate_profile("small", [result])
    assert not aggregate.correct
    assert aggregate.abstract_cost == 0
    assert aggregate.solution_quality is None


def test_solver_exception_becomes_failure_metric():
    def fail(_instance, _cost):
        raise RuntimeError("expected")

    result = measure_instance(INSTANCE, fail, verifier)
    assert not result.correct
    assert result.failure_reason == "RuntimeError: expected"


def test_operation_meter_rejects_counter_fabrication():
    meter = OperationMeter()
    with pytest.raises(ValueError, match="non-negative"):
        meter.additions(-1)
    with pytest.raises(AttributeError):
        meter.additions = 0  # type: ignore[method-assign]


def test_wall_limit_terminates_and_unscored_instance():
    def slow_solver(_instance, _meter):
        time.sleep(0.05)
        return Candidate((1,))

    result = measure_instance(
        INSTANCE, slow_solver, verifier,
        ResourceLimits(wall_seconds=0.01, peak_memory_bytes=64 * 1024 * 1024),
    )
    assert not result.correct
    assert result.resource_status == "time_exceeded"
    assert "wall time" in result.failure_reason


def test_memory_limit_invalidates_otherwise_correct_instance():
    result = measure_instance(
        INSTANCE, good_solver, verifier,
        ResourceLimits(wall_seconds=1, peak_memory_bytes=1),
    )
    assert not result.correct
    assert result.resource_status == "memory_exceeded"
    assert "peak memory" in result.failure_reason


def test_seed_suites_and_full_semantics():
    assert selected_suites("full") == ("public", "hidden")
    assert set(load_seed_suite("public", "small")) == {"small"}


def test_public_suite_falls_back_but_hidden_requires_injected_secret(monkeypatch):
    monkeypatch.setattr(
        suites_module,
        "SUITE_FILES",
        {name: suites_module.PROJECT_ROOT / "missing" / path.name
         for name, path in suites_module.SUITE_FILES.items()},
    )
    assert set(load_seed_suite("public", "medium")) == {"medium"}
    with pytest.raises(suites_module.SuiteError, match="maintainer-only"):
        load_seed_suite("hidden", "medium")


def test_hidden_suite_can_be_injected_by_maintainer(tmp_path, monkeypatch):
    hidden = tmp_path / "hidden.json"
    hidden.write_text('{"small":[991]}')
    monkeypatch.setenv("MLDSAFAIL_HIDDEN_SEEDS_PATH", str(hidden))
    assert load_seed_suite("hidden", "small") == {"small": (991,)}


def record(identifier, score, correct=True, timestamp="2026-01-01"):
    return {
        "schema_version": "2", "experiment_id": identifier, "timestamp": timestamp,
        "correct": correct, "score": score if correct else None,
        "aggregate": {"score": score if correct else None},
    }


def test_single_score_frontier_ignores_diagnostics_and_invalid_runs():
    baseline = record("baseline", 100, timestamp="2026-01-01")
    regression = record("regression", 120, timestamp="2026-01-02")
    best = record("best", 80, timestamp="2026-01-03")
    invalid = record("invalid", 1, False, timestamp="2026-01-04")
    assert rankable_score(invalid) is None
    assert best_score_record([baseline, regression, best, invalid]) is best
    assert score_frontier([best, invalid, baseline, regression]) == [baseline, best]


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
        "--profile", "small", "--seed", "12345", "--solver", "balanced",
        "--output", str(output)
    ])
    printed = json.loads(capsys.readouterr().out)
    persisted = json.loads(output.read_text())
    assert result == 1
    assert printed == persisted
    assert persisted["correct"] is False
    assert persisted["solver"] == "balanced"
    assert persisted["score"] is None
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


def test_cli_defaults_to_current_best_lazy_solver():
    assert runner.build_parser().parse_args([]).solver == "lazy"


def test_lazy_selection_runs_a_distinct_cost_model():
    _balanced_suites, balanced, balanced_correct = runner.run_benchmark(
        suite="public", profile="medium", solver_name="balanced"
    )
    _lazy_suites, lazy, lazy_correct = runner.run_benchmark(
        suite="public", profile="medium", solver_name="lazy"
    )
    assert balanced_correct and lazy_correct
    assert lazy["abstract_cost"] < balanced["abstract_cost"]


@pytest.mark.parametrize(
    "arguments",
    [
        ["--seed", "1"],
        ["--profile", "not-a-profile"],
        ["--solver", "not-a-solver"],
        ["--profile", "small", "--seed", "1", "--suite", "hidden"],
        ["--profile", "small", "--seed", "1", "--suite", "full"],
    ],
)
def test_cli_rejects_invalid_flag_combinations(arguments):
    with pytest.raises(SystemExit) as raised:
        runner.main(arguments)
    assert raised.value.code == 2
