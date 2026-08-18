"""Candidate C: guessing + reduced Gaussian solve.

Enumerates k coefficients, substitutes into the system, solves the
reduced (n-k) x (n-k) system via Gaussian elimination, checks bounds.
"""

from __future__ import annotations

import itertools
import time
from typing import Optional, Tuple

from mldsafail.benchmark.cost_model import OperationMeter
from mldsafail.models import Candidate, ChallengeInstance


class CandidateCError(RuntimeError):
    """Raised when Candidate C cannot recover a valid bounded vector."""


def _gaussian_solve(
    A: list[list[int]],
    b: list[int],
    q: int,
    cost: OperationMeter,
) -> list[int]:
    """Solve A*x = b (mod q) via Gaussian elimination.

    Returns residues in [0, q-1].
    """
    n = len(A)
    if n == 0:
        return []

    # Build augmented matrix [A | b]
    augmented: list[list[int]] = []
    for row, target in zip(A, b, strict=True):
        cost.memory_reads(n)
        cost.memory_reads(1)
        augmented.append(list(row) + [target])
        cost.memory_writes(n + 1)

    # Forward elimination
    for col in range(n):
        # Find pivot
        pivot = col
        while pivot < n and augmented[pivot][col] == 0:
            pivot += 1
            cost.memory_reads(1)
        if pivot == n:
            raise CandidateCError(f"singular matrix at column {col}")

        if pivot != col:
            cost.memory_reads(2 * (n + 1))
            cost.memory_writes(2 * (n + 1))
            augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
            cost.basis_updates(1)

        pivot_row = augmented[col]
        pivot_val = pivot_row[col]
        cost.memory_reads(1)

        inv = pow(pivot_val, -1, q)
        cost.modular_reductions(1)
        cost.multiplications(1)

        trailing = n - col
        for row_idx in range(col + 1, n):
            row_vals = augmented[row_idx]
            factor = row_vals[col]
            cost.memory_reads(1)
            if factor == 0:
                continue
            factor = (factor * inv) % q
            cost.multiplications(1)
            cost.modular_reductions(1)
            row_vals[col] = 0
            cost.memory_writes(1)
            for j in range(col + 1, n + 1):
                row_vals[j] = (row_vals[j] - factor * pivot_row[j]) % q
            cost.memory_reads(2 * (trailing - 1))
            cost.memory_writes(trailing - 1)
            cost.multiplications(trailing - 1)
            cost.additions(trailing - 1)
            cost.modular_reductions(trailing - 1)
            cost.basis_updates(1)

    # Back substitution
    residues = [0] * n
    cost.memory_writes(n)
    for row_idx in range(n - 1, -1, -1):
        row_vals = augmented[row_idx]
        remainder = row_vals[n]
        cost.memory_reads(1)
        width = n - row_idx - 1
        for col in range(row_idx + 1, n):
            remainder -= row_vals[col] * residues[col]
        cost.memory_reads(2 * width)
        cost.multiplications(width)
        cost.additions(width)
        pivot_val = row_vals[row_idx]
        cost.memory_reads(1)
        inv = pow(pivot_val, -1, q)
        cost.modular_reductions(1)
        cost.multiplications(1)
        residues[row_idx] = (remainder * inv) % q
        cost.multiplications(1)
        cost.modular_reductions(1)
        cost.memory_writes(1)

    return residues


def _center(residues: list[int], q: int) -> list[int]:
    """Map residues from [0, q-1] to centered [-q//2, q//2]."""
    midpoint = q // 2
    return [v - q if v > midpoint else v for v in residues]


def _mat_vec_mul(A: tuple[tuple[int, ...], ...], c: tuple[int, ...], q: int) -> list[int]:
    """Compute A * c mod q."""
    n = len(A)
    result = []
    for row in A:
        s = 0
        for a, v in zip(row, c):
            s = (s + a * v) % q
        result.append(s)
    return result


def solve(
    instance: ChallengeInstance,
    cost: OperationMeter,
    k: int,
    timeout_sec: float = 60.0,
) -> Tuple[Candidate, int, Optional[int]]:
    """Run Candidate C: guessing + reduced Gaussian solve.

    Args:
        instance: The challenge instance.
        cost: Operation meter.
        k: Number of coefficients to guess.
        timeout_sec: Wall-clock timeout.

    Returns:
        Tuple of (Candidate, guesses_tried, first_guess_hit_index).
    """
    n = instance.dimension
    q = instance.modulus
    eta = instance.eta
    A = instance.matrix
    t = instance.target

    if k <= 0 or k > n:
        raise CandidateCError(f"k must be in [1, n], got {k}")

    coeff_range = list(range(-eta, eta + 1))
    space_size = len(coeff_range) ** k
    guess_indices = list(range(k))
    solve_indices = list(range(k, n))

    guesses_tried = 0
    first_hit_index: Optional[int] = None
    start_time = time.time()

    for guess_assignment in itertools.product(coeff_range, repeat=k):
        if time.time() - start_time > timeout_sec:
            raise TimeoutError(
                f"Enumeration timed out after {timeout_sec}s "
                f"(tried {guesses_tried} of {space_size} guesses)"
            )

        guesses_tried += 1

        # Build reduced system
        A_reduced: list[list[int]] = []
        t_reduced: list[int] = []

        for row_idx in range(k, n):
            row = A[row_idx]
            rhs = t[row_idx]

            # Subtract contribution from guessed coefficients (disjoint from solve set).
            for gi, gval in zip(guess_indices, guess_assignment):
                cost.memory_reads(1)
                cost.memory_reads(1)
                cost.multiplications(1)
                cost.additions(1)
                cost.modular_reductions(1)
                rhs = (rhs - row[gi] * gval) % q

            # Extract columns for unknown coefficients.
            reduced_row: list[int] = []
            for si in solve_indices:
                cost.memory_reads(1)
                reduced_row.append(row[si])
            A_reduced.append(reduced_row)
            t_reduced.append(rhs)

        # Solve reduced system
        try:
            reduced_residues = _gaussian_solve(A_reduced, t_reduced, q, cost)
        except CandidateCError:
            continue

        # Center and check bounds
        centered = _center(reduced_residues, q)
        cost.memory_reads(len(centered))

        in_bounds = True
        for v in centered:
            cost.memory_reads(1)
            if abs(v) > eta:
                in_bounds = False
                break

        if not in_bounds:
            continue

        # Build full coefficient vector
        full_c = list(guess_assignment) + centered

        # Final verification: A * c == t (mod q)
        cost.memory_reads(n * n)
        cost.memory_reads(n)
        verification = _mat_vec_mul(A, tuple(full_c), q)
        cost.memory_writes(n)
        cost.memory_reads(n)

        if verification == list(t):
            if first_hit_index is None:
                first_hit_index = guesses_tried - 1

            return Candidate(coefficients=tuple(full_c)), guesses_tried, first_hit_index

    raise CandidateCError(
        f"Exhausted enumeration space ({space_size} guesses) without finding valid solution"
    )
