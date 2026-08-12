"""Validated baseline-v1 Gauss-Jordan reference solver.

Kept unchanged in spirit so improvements remain reproducible under the latest
benchmark harness. New optimization work should target the balanced solver.
"""

from __future__ import annotations

from mldsafail.models import Candidate, CostCounter, ToyInstance
from mldsafail.solver.baseline import SolverError


def solve(instance: ToyInstance, cost: CostCounter) -> Candidate:
    n, q = instance.dimension, instance.modulus
    if n <= 0 or q <= 2:
        raise SolverError("invalid instance dimensions or modulus")
    if len(instance.matrix) != n or len(instance.target) != n:
        raise SolverError("instance shape does not match its dimension")
    if any(len(row) != n for row in instance.matrix):
        raise SolverError("matrix must be square")

    augmented: list[list[int]] = []
    for row, target in zip(instance.matrix, instance.target, strict=True):
        cost.memory_reads += n + 1
        augmented.append([value % q for value in row] + [target % q])
        cost.modular_reductions += n + 1
        cost.memory_writes += n + 1

    for column in range(n):
        pivot = next((row for row in range(column, n) if augmented[row][column] % q), None)
        cost.memory_reads += (pivot - column + 1) if pivot is not None else n - column
        if pivot is None:
            raise SolverError(f"singular matrix at column {column}")
        if pivot != column:
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
            cost.basis_updates += 1
            cost.memory_reads += 2 * (n + 1)
            cost.memory_writes += 2 * (n + 1)

        try:
            inverse = pow(augmented[column][column], -1, q)
        except ValueError as exc:
            raise SolverError(f"non-invertible pivot at column {column}") from exc
        cost.memory_reads += 1
        for index in range(column, n + 1):
            cost.memory_reads += 1
            augmented[column][index] = (augmented[column][index] * inverse) % q
            cost.multiplications += 1
            cost.modular_reductions += 1
            cost.memory_writes += 1
        cost.basis_updates += 1

        for row in range(n):
            if row == column:
                continue
            cost.memory_reads += 1
            factor = augmented[row][column]
            if factor == 0:
                continue
            for index in range(column, n + 1):
                cost.memory_reads += 2
                augmented[row][index] = (
                    augmented[row][index] - factor * augmented[column][index]
                ) % q
                cost.multiplications += 1
                cost.additions += 1
                cost.modular_reductions += 1
                cost.memory_writes += 1
            cost.basis_updates += 1

    residues = [augmented[row][n] for row in range(n)]
    cost.memory_reads += n
    midpoint = q // 2
    coefficients = tuple(value - q if value > midpoint else value for value in residues)
    cost.memory_writes += n
    return Candidate(coefficients=coefficients)
