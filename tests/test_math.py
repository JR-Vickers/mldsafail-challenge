import pytest

from mldsafail.math.lattice import is_invertible, mat_vec_mul, solve_linear_system
from mldsafail.math.modular import add_mod, inverse_mod, multiply_mod, normalize
from mldsafail.math.polynomial import add_polynomials, multiply_negacyclic


def test_modular_arithmetic() -> None:
    assert normalize(-1, 7) == 6
    assert add_mod(6, 3, 7) == 2
    assert multiply_mod(5, 3, 7) == 1
    assert inverse_mod(5, 7) == 3


def test_modular_inverse_rejects_non_unit() -> None:
    with pytest.raises(ValueError, match="no inverse"):
        inverse_mod(2, 4)


def test_polynomial_arithmetic_in_negacyclic_ring() -> None:
    assert add_polynomials((1, 2), (4, 4), 5) == (0, 1)
    # (1 + x)^2 = 1 + 2x + x^2 = 0 + 2x modulo x^2 + 1.
    assert multiply_negacyclic((1, 1), (1, 1), 17) == (0, 2)


def test_matrix_vector_and_linear_solver() -> None:
    matrix = ((2, 1), (1, 1))
    vector = (3, 4)
    target = mat_vec_mul(matrix, vector, 7)
    assert target == (3, 0)
    assert solve_linear_system(matrix, target, 7) == vector
    assert is_invertible(matrix, 7)
    assert not is_invertible(((1, 2), (2, 4)), 7)


def test_math_rejects_dimension_mismatches() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        mat_vec_mul(((1, 2),), (1,), 7)
    with pytest.raises(ValueError, match="square"):
        solve_linear_system(((1, 2),), (1,), 7)
    with pytest.raises(ValueError, match="same non-zero"):
        multiply_negacyclic((1,), (1, 2), 7)
