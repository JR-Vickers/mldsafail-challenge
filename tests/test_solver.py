from __future__ import annotations

import pytest

from mldsafail.benchmark.cost_model import OperationMeter
from mldsafail.models import ChallengeInstance
from mldsafail.solver import SolverError, solve
from mldsafail.solver.lazy import solve as lazy_solve
from mldsafail.solver.reference import solve as reference_solve
from mldsafail.trusted.generator import generate_instance
from mldsafail.trusted.verifier import verify


def instance(matrix=((2, 1), (1, 1)), target=(96, 96)) -> ChallengeInstance:
    return ChallengeInstance(
        instance_id="test", seed=1, profile="small", dimension=2,
        modulus=97, eta=2, matrix=matrix, target=target,
    )


def test_baseline_solves_and_centers_modular_system():
    cost = OperationMeter()
    candidate = solve(instance(), cost)
    assert candidate.coefficients == (0, -1)
    snapshot = cost.snapshot()
    assert snapshot.weighted_total > 0
    assert snapshot.modular_reductions > 0
    assert snapshot.basis_updates > 0


def test_cost_is_deterministic():
    first, second = OperationMeter(), OperationMeter()
    solve(instance(), first)
    solve(instance(), second)
    assert first.snapshot() == second.snapshot()


def test_cost_accumulates_into_existing_counter():
    baseline = OperationMeter()
    solve(instance(), baseline)
    accumulated = OperationMeter()
    accumulated.additions(10)
    accumulated.memory_reads(20)
    solve(instance(), accumulated)
    assert accumulated.snapshot().additions == baseline.snapshot().additions + 10
    assert accumulated.snapshot().memory_reads == baseline.snapshot().memory_reads + 20


def test_canonical_public_input_is_not_reduced_again():
    cost = OperationMeter()
    solve(instance(matrix=((1, 0), (0, 1)), target=(1, 96)), cost)
    # Only the two back-substitution assignments need reductions; copying the
    # six public residues requires none.
    assert cost.snapshot().modular_reductions == 2


def test_forward_elimination_solves_system_requiring_back_substitution():
    toy = instance(
        matrix=((1, 2, 1), (0, 1, 3), (2, 1, 1)),
        target=(6, 5, 5),
    )
    toy = ChallengeInstance(**{**toy.__dict__, "dimension": 3, "eta": 4})
    cost = OperationMeter()
    assert solve(toy, cost).coefficients == (1, 2, 1)
    assert cost.snapshot().multiplications > 0
    assert cost.snapshot().additions > 0


@pytest.mark.parametrize("profile", ("small", "medium", "large"))
@pytest.mark.parametrize("seed", (0, 17, 12345, 987654321))
def test_solver_remains_correct_for_generic_generated_seeds(profile, seed):
    generated = generate_instance(seed, profile)
    candidate = solve(generated, OperationMeter())
    assert verify(generated, candidate).valid


@pytest.mark.parametrize(
    "solver", (reference_solve, solve, lazy_solve), ids=("reference", "balanced", "lazy")
)
@pytest.mark.parametrize("profile", ("small", "medium", "large"))
@pytest.mark.parametrize("seed", (0, 17, 12345))
def test_all_solvers_remain_correct_across_profiles(solver, profile, seed):
    generated = generate_instance(seed, profile)
    assert verify(generated, solver(generated, OperationMeter())).valid


def test_lazy_solver_handles_noncanonical_public_values_by_residue():
    q = 97
    shifted = instance(
        matrix=((2 + 3 * q, 1 - 2 * q), (1 + q, 1 + 4 * q)),
        target=(96 + 5 * q, 96 - 3 * q),
    )
    assert lazy_solve(shifted, OperationMeter()).coefficients == (0, -1)


def test_singular_matrix_is_reported():
    with pytest.raises(SolverError, match="singular"):
        solve(instance(matrix=((1, 1), (2, 2)), target=(1, 2)), OperationMeter())


def test_invalid_shape_is_reported():
    with pytest.raises(SolverError, match="square"):
        solve(instance(matrix=((1,), (2,))), OperationMeter())
