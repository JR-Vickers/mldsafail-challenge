"""Tiny polynomial-ring helpers inspired by ML-DSA's ring structure."""

from collections.abc import Sequence


def _same_nonempty_length(left: Sequence[int], right: Sequence[int]) -> int:
    if not left or len(left) != len(right):
        raise ValueError("polynomials must have the same non-zero degree bound")
    return len(left)


def add_polynomials(
    left: Sequence[int], right: Sequence[int], modulus: int
) -> tuple[int, ...]:
    _same_nonempty_length(left, right)
    if modulus <= 1:
        raise ValueError("modulus must be greater than one")
    return tuple((a + b) % modulus for a, b in zip(left, right))


def multiply_negacyclic(
    left: Sequence[int], right: Sequence[int], modulus: int
) -> tuple[int, ...]:
    """Multiply in ``Z_modulus[x] / (x^n + 1)``."""
    size = _same_nonempty_length(left, right)
    if modulus <= 1:
        raise ValueError("modulus must be greater than one")
    result = [0] * size
    for left_index, left_value in enumerate(left):
        for right_index, right_value in enumerate(right):
            degree = left_index + right_index
            sign = 1
            if degree >= size:
                degree -= size
                sign = -1
            result[degree] += sign * left_value * right_value
    return tuple(value % modulus for value in result)
