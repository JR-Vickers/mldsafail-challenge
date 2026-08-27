"""Experimental triangular solver with lazy modular reduction — with pivot-scan skip."""

from __future__ import annotations

from mldsafail.benchmark.cost_model import OperationMeter
from mldsafail.models import Candidate, ChallengeInstance
from mldsafail.solver.baseline import SolverError


def solve(instance: ChallengeInstance, cost: OperationMeter) -> Candidate:
    """Solve a toy system while deferring reductions in trailing row updates.

    This preserves exact intermediate Python integers and reduces only values
    that affect pivot selection, elimination factors, or final residues.

    The trusted generator emits canonical residues in [0, q). The pivot row
    is never modified during elimination, so the first non-zero pivot candidate
    encountered is already canonical — skip the % q when 0 < raw_pivot < q.
    """

    n, q = instance.dimension, instance.modulus
    if n <= 0 or q <= 2:
        raise SolverError("invalid instance dimensions or modulus")
    if len(instance.matrix) != n or len(instance.target) != n:
        raise SolverError("instance shape does not match its dimension")
    if any(len(row) != n for row in instance.matrix):
        raise SolverError("matrix must be square")

    additions = multiplications = modular_reductions = basis_updates = 0
    memory_reads = memory_writes = 0
    try:
        augmented: list[list[int]] = []
        for row, target in zip(instance.matrix, instance.target, strict=True):
            memory_reads += n + 1
            # Trusted instances already contain canonical residues. Copy them
            # directly instead of reducing every public coefficient again.
            augmented.append([value for value in row] + [target])
            memory_writes += n + 1

        for column in range(n):
            # Trailing updates are exact integers rather than canonical
            # residues, so reduce only pivot candidates affecting control flow.
            pivot = None
            pivot_value = None
            for row in range(column, n):
                memory_reads += 1
                raw_pivot = augmented[row][column]
                if raw_pivot == 0:
                    continue
                # Trusted instances start canonical; the pivot row is never
                # modified during elimination. When the exact value already sits
                # in (0, q), the % q would be a no-op — skip it.
                if 0 < raw_pivot < q:
                    pivot = row
                    pivot_value = raw_pivot
                    break
                residue = raw_pivot % q
                modular_reductions += 1
                if residue:
                    pivot = row
                    pivot_value = residue
                    break
            if pivot is None:
                raise SolverError(f"singular matrix at column {column}")
            if pivot != column:
                augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
                basis_updates += 1
                memory_reads += 2 * (n + 1)
                memory_writes += 2 * (n + 1)

            pivot_row = augmented[column]
            try:
                inverse = pow(pivot_value, -1, q)
            except ValueError as exc:
                raise SolverError(f"non-invertible pivot at column {column}") from exc

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
                # A nonzero exact value may be zero modulo q.
                if factor == 0:
                    row_values[column] = 0
                    memory_writes += 1
                    continue
                row_values[column] = 0
                memory_writes += 1
                for j in range(column + 1, n + 1):
                    row_values[j] -= factor * pivot_row[j]
                memory_reads += 2 * width
                memory_writes += width
                multiplications += width
                additions += width
                basis_updates += 1

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
        cost.additions(additions)
        cost.multiplications(multiplications)
        cost.modular_reductions(modular_reductions)
        cost.basis_updates(basis_updates)
        cost.memory_reads(memory_reads)
        cost.memory_writes(memory_writes)
