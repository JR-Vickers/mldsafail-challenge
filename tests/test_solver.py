from __future__ import annotations

import pytest

from mldsafail.models import CostCounter, ToyInstance
from mldsafail.solver import SolverError, solve


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


def test_singular_matrix_is_reported():
    with pytest.raises(SolverError, match="singular"):
        solve(instance(matrix=((1, 1), (2, 2)), target=(1, 2)), CostCounter())


def test_invalid_shape_is_reported():
    with pytest.raises(SolverError, match="square"):
        solve(instance(matrix=((1,), (2,))), CostCounter())
