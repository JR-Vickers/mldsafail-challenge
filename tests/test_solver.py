from __future__ import annotations

import pytest

from mldsafail.models import CostCounter, ToyInstance
from mldsafail.solver import SolverError, solve
from mldsafail.trusted.generator import generate_instance
from mldsafail.trusted.verifier import verify


def instance(matrix=((2, 1), (1, 1)), target=(96, 96)) -> ToyInstance:
    return ToyInstance(
        instance_id="test", seed=1, profile="toy-small", dimension=2,
        modulus=97, eta=2, matrix=matrix, target=target,
    )


def test_baseline_solves_and_centers_modular_system():
    cost = CostCounter()
    candidate = solve(instance(), cost)
    assert candidate.coefficients == (0, -1)
    assert cost.total > 0
    assert cost.modular_reductions > 0
    assert cost.basis_updates > 0


def test_cost_is_deterministic():
    first, second = CostCounter(), CostCounter()
    solve(instance(), first)
    solve(instance(), second)
    assert first.to_dict() == second.to_dict()


def test_cost_accumulates_into_existing_counter():
    baseline = CostCounter()
    solve(instance(), baseline)
    accumulated = CostCounter(additions=10, memory_reads=20)
    solve(instance(), accumulated)
    assert accumulated.additions == baseline.additions + 10
    assert accumulated.memory_reads == baseline.memory_reads + 20


def test_canonical_public_input_is_not_reduced_again():
    cost = CostCounter()
    solve(instance(matrix=((1, 0), (0, 1)), target=(1, 96)), cost)
    # Only the two back-substitution assignments need reductions; copying the
    # six public residues requires none.
    assert cost.modular_reductions == 2


def test_forward_elimination_solves_system_requiring_back_substitution():
    toy = instance(
        matrix=((1, 2, 1), (0, 1, 3), (2, 1, 1)),
        target=(6, 5, 5),
    )
    toy = ToyInstance(**{**toy.__dict__, "dimension": 3, "eta": 4})
    cost = CostCounter()
    assert solve(toy, cost).coefficients == (1, 2, 1)
    assert cost.multiplications > 0
    assert cost.additions > 0


@pytest.mark.parametrize("profile", ("toy-small", "toy-medium", "toy-large"))
@pytest.mark.parametrize("seed", (0, 17, 12345, 987654321))
def test_solver_remains_correct_for_generic_generated_seeds(profile, seed):
    generated = generate_instance(seed, profile)
    candidate = solve(generated, CostCounter())
    assert verify(generated, candidate).valid


def test_singular_matrix_is_reported():
    with pytest.raises(SolverError, match="singular"):
        solve(instance(matrix=((1, 1), (2, 2)), target=(1, 2)), CostCounter())


def test_invalid_shape_is_reported():
    with pytest.raises(SolverError, match="square"):
        solve(instance(matrix=((1,), (2,))), CostCounter())
