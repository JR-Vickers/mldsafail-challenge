"""Matrix helpers used by the synthetic modular-lattice challenge."""

from collections.abc import Sequence

from .modular import inverse_mod


def _validate_square(matrix: Sequence[Sequence[int]]) -> int:
    if not matrix:
        raise ValueError("matrix must not be empty")
    size = len(matrix)
    if any(len(row) != size for row in matrix):
        raise ValueError("matrix must be square")
    return size


def mat_vec_mul(
    matrix: Sequence[Sequence[int]], vector: Sequence[int], modulus: int
) -> tuple[int, ...]:
    """Multiply a rectangular matrix by a vector modulo ``modulus``."""
    if modulus <= 1:
        raise ValueError("modulus must be greater than one")
    if any(len(row) != len(vector) for row in matrix):
        raise ValueError("matrix and vector dimensions do not match")
    return tuple(sum(entry * value for entry, value in zip(row, vector)) % modulus for row in matrix)


def solve_linear_system(
    matrix: Sequence[Sequence[int]], target: Sequence[int], modulus: int
) -> tuple[int, ...]:
    """Solve ``matrix * x = target (mod modulus)`` using elimination.

    The benchmark moduli are prime. A missing pivot therefore means the
    matrix is singular for the configured field.
    """
    size = _validate_square(matrix)
    if len(target) != size:
        raise ValueError("matrix and target dimensions do not match")
    augmented = [
        [entry % modulus for entry in row] + [target[index] % modulus]
        for index, row in enumerate(matrix)
    ]
    for column in range(size):
        pivot = next((row for row in range(column, size) if augmented[row][column]), None)
        if pivot is None:
            raise ValueError("matrix is singular modulo the configured modulus")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = inverse_mod(augmented[column][column], modulus)
        augmented[column] = [(value * scale) % modulus for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    (value - factor * pivot_value) % modulus
                    for value, pivot_value in zip(augmented[row], augmented[column])
                ]
    return tuple(row[-1] for row in augmented)


def is_invertible(matrix: Sequence[Sequence[int]], modulus: int) -> bool:
    """Return whether a square matrix is invertible modulo ``modulus``."""
    try:
        size = _validate_square(matrix)
        solve_linear_system(matrix, (0,) * size, modulus)
    except (TypeError, ValueError):
        return False
    return True
