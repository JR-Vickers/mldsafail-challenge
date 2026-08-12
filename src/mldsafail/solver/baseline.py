"""Clear deterministic baseline for the toy modular linear systems."""

from __future__ import annotations

from mldsafail.models import Candidate, CostCounter, ToyInstance


class SolverError(RuntimeError):
    """Raised when a toy instance has no uniquely recoverable solution."""


def solve(instance: ToyInstance, cost: CostCounter) -> Candidate:
    """Solve ``matrix * coefficients == target (mod modulus)``.

    The implementation uses forward elimination followed by back substitution.
    It assumes the repository generator creates a square, invertible public
    matrix. Every counted operation is deterministic and independent of
    wall-clock behaviour.
    """

    n, q = instance.dimension, instance.modulus
    if n <= 0 or q <= 2:
        raise SolverError("invalid instance dimensions or modulus")
    if len(instance.matrix) != n or len(instance.target) != n:
        raise SolverError("instance shape does not match its dimension")
    if any(len(row) != n for row in instance.matrix):
        raise SolverError("matrix must be square")

    # Accumulate cost deltas locally so instrumentation does not dominate the
    # actual row operations under tracemalloc. The finally block preserves the
    # version-1 counter semantics, including partial work on failure paths.
    additions = multiplications = modular_reductions = basis_updates = 0
    memory_reads = memory_writes = 0
    try:
        augmented: list[list[int]] = []
        for row, target in zip(instance.matrix, instance.target, strict=True):
            memory_reads += n + 1
            augmented.append([value % q for value in row] + [target % q])
            modular_reductions += n + 1
            memory_writes += n + 1

        for column in range(n):
            pivot = column
            while pivot < n and augmented[pivot][column] == 0:
                pivot += 1
            memory_reads += (pivot - column + 1) if pivot < n else n - column
            if pivot == n:
                raise SolverError(f"singular matrix at column {column}")
            if pivot != column:
                augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
                basis_updates += 1
                memory_reads += 2 * (n + 1)
                memory_writes += 2 * (n + 1)

            pivot_row = augmented[column]
            memory_reads += 1
            try:
                inverse = pow(pivot_row[column], -1, q)
            except ValueError as exc:
                raise SolverError(f"non-invertible pivot at column {column}") from exc

            # Only rows below the pivot need updating. Keeping the pivot row
            # unnormalised avoids an otherwise redundant write of its tail.
            width = n - column
            for row in range(column + 1, n):
                row_values = augmented[row]
                factor = row_values[column]
                memory_reads += 1
                if factor == 0:
                    continue
                factor = (factor * inverse) % q
                multiplications += 1
                modular_reductions += 1
                row_values[column] = 0
                memory_writes += 1
                for j in range(column + 1, n + 1):
                    row_values[j] = (row_values[j] - factor * pivot_row[j]) % q
                memory_reads += 2 * width
                memory_writes += width
                multiplications += width
                additions += width
                modular_reductions += width
                basis_updates += 1

        # Solve the upper-triangular system. Inner products are reduced once
        # per row; Python's exact integers keep this mathematically equivalent.
        residues = [0] * n
        memory_writes += n
        for row in range(n - 1, -1, -1):
            row_values = augmented[row]
            remainder = row_values[n]
            memory_reads += 1
            width = n - row - 1
            for column in range(row + 1, n):
                remainder -= row_values[column] * residues[column]
            memory_reads += 2 * width
            multiplications += width
            additions += width
            memory_reads += 1
            try:
                inverse = pow(row_values[row], -1, q)
            except ValueError as exc:
                raise SolverError(f"non-invertible pivot at row {row}") from exc
            residues[row] = (remainder * inverse) % q
            multiplications += 1
            modular_reductions += 1
            memory_writes += 1

        midpoint = q // 2
        coefficients = tuple(value - q if value > midpoint else value for value in residues)
        memory_reads += n
        memory_writes += n
        return Candidate(coefficients=coefficients)
    finally:
        cost.additions += additions
        cost.multiplications += multiplications
        cost.modular_reductions += modular_reductions
        cost.basis_updates += basis_updates
        cost.memory_reads += memory_reads
        cost.memory_writes += memory_writes
