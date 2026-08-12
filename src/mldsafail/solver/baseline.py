"""Clear deterministic baseline for the toy modular linear systems."""

from __future__ import annotations

from mldsafail.models import Candidate, CostCounter, ToyInstance


class SolverError(RuntimeError):
    """Raised when a toy instance has no uniquely recoverable solution."""


def _read(cost: CostCounter, count: int = 1) -> None:
    cost.memory_reads += count


def _write(cost: CostCounter, count: int = 1) -> None:
    cost.memory_writes += count


def solve(instance: ToyInstance, cost: CostCounter) -> Candidate:
    """Solve ``matrix * coefficients == target (mod modulus)``.

    The implementation is intentionally unsurprising Gauss-Jordan elimination.
    It assumes the repository generator creates a square, invertible public
    matrix.  Every counted operation is deterministic and independent of
    wall-clock behaviour.
    """

    n, q = instance.dimension, instance.modulus
    if n <= 0 or q <= 2:
        raise SolverError("invalid instance dimensions or modulus")
    if len(instance.matrix) != n or len(instance.target) != n:
        raise SolverError("instance shape does not match its dimension")
    if any(len(row) != n for row in instance.matrix):
        raise SolverError("matrix must be square")

    augmented: list[list[int]] = []
    for row, target in zip(instance.matrix, instance.target, strict=True):
        _read(cost, n + 1)
        augmented.append([value % q for value in row] + [target % q])
        cost.modular_reductions += n + 1
        _write(cost, n + 1)

    for column in range(n):
        pivot = next((r for r in range(column, n) if augmented[r][column] % q), None)
        _read(cost, (pivot - column + 1) if pivot is not None else n - column)
        if pivot is None:
            raise SolverError(f"singular matrix at column {column}")
        if pivot != column:
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
            cost.basis_updates += 1
            _read(cost, 2 * (n + 1))
            _write(cost, 2 * (n + 1))

        _read(cost)
        try:
            inverse = pow(augmented[column][column], -1, q)
        except ValueError as exc:
            raise SolverError(f"non-invertible pivot at column {column}") from exc

        for j in range(column, n + 1):
            _read(cost)
            augmented[column][j] = (augmented[column][j] * inverse) % q
            cost.multiplications += 1
            cost.modular_reductions += 1
            _write(cost)
        cost.basis_updates += 1

        for row in range(n):
            if row == column:
                continue
            _read(cost)
            factor = augmented[row][column]
            if factor == 0:
                continue
            for j in range(column, n + 1):
                _read(cost, 2)
                product = factor * augmented[column][j]
                augmented[row][j] = (augmented[row][j] - product) % q
                cost.multiplications += 1
                cost.additions += 1
                cost.modular_reductions += 1
                _write(cost)
            cost.basis_updates += 1

    residues = [augmented[row][n] for row in range(n)]
    _read(cost, n)
    # The generator plants small signed coefficients.  Convert their canonical
    # residues back to the centered representative expected by the verifier.
    midpoint = q // 2
    coefficients = tuple(value - q if value > midpoint else value for value in residues)
    _write(cost, n)
    return Candidate(coefficients=coefficients)
