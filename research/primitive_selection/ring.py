"""Small, auditable arithmetic for R_q = Z_q[x]/(x^n + 1)."""

from __future__ import annotations

from collections.abc import Sequence


def add(a: Sequence[int], b: Sequence[int], q: int) -> tuple[int, ...]:
    if len(a) != len(b):
        raise ValueError("polynomials must have equal degree")
    return tuple((x + y) % q for x, y in zip(a, b, strict=True))


def negacyclic_mul(a: Sequence[int], b: Sequence[int], q: int) -> tuple[int, ...]:
    if len(a) != len(b):
        raise ValueError("polynomials must have equal degree")
    n = len(a)
    out = [0] * n
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            degree = i + j
            if degree >= n:
                out[degree - n] -= x * y
            else:
                out[degree] += x * y
    return tuple(x % q for x in out)


def mat_vec_mul(
    matrix: Sequence[Sequence[Sequence[int]]],
    vector: Sequence[Sequence[int]],
    q: int,
) -> tuple[tuple[int, ...], ...]:
    if not matrix:
        return ()
    n = len(matrix[0][0])
    zero = (0,) * n
    result = []
    for row in matrix:
        if len(row) != len(vector):
            raise ValueError("matrix and vector dimensions do not match")
        acc = zero
        for entry, value in zip(row, vector, strict=True):
            acc = add(acc, negacyclic_mul(entry, value, q), q)
        result.append(acc)
    return tuple(result)


def convolution_matrix(poly: Sequence[int], q: int) -> tuple[tuple[int, ...], ...]:
    """Matrix C with C @ v equal to poly*v in the negacyclic ring."""
    n = len(poly)
    columns = []
    for j in range(n):
        unit = [0] * n
        unit[j] = 1
        columns.append(negacyclic_mul(poly, unit, q))
    return tuple(tuple(columns[j][i] for j in range(n)) for i in range(n))


def flatten_polys(polys: Sequence[Sequence[int]]) -> tuple[int, ...]:
    return tuple(value for poly in polys for value in poly)


def center(value: int, q: int) -> int:
    reduced = value % q
    return reduced - q if reduced > q // 2 else reduced
