"""Candidate B: bounded short-vector recovery via LLL lattice reduction.

Solves A * c == t (mod q) with |c_i| <= eta using LLL on a 2n x 2n
lattice basis, then extracting a short vector via Babai's nearest-plane
algorithm whose left half satisfies the modular relation and the eta bound.

Lattice construction:
    M = [I_n,   A  ]   (2n x 2n matrix, rows are basis vectors)
        [0_n,   q*I_n]

A lattice point v = a*(first n rows) + b*(last n rows) = (a, A*a + b*q).
The planted solution s satisfies A*s ≡ t (mod q), so t = A*s - q*k for
some integer vector k.  Thus (s, t) = s*(first n rows) + k*(last n rows)
is in the lattice.

Cost instrumentation follows the version-2 shared meter.
"""

from __future__ import annotations

import math
from itertools import combinations, product
from typing import Optional, Tuple, List

from mldsafail.benchmark.cost_model import OperationMeter
from mldsafail.math.lattice import mat_vec_mul
from mldsafail.models import Candidate, ChallengeInstance


class CandidateBError(RuntimeError):
    """Raised when Candidate B cannot recover a valid bounded vector."""


def _build_lattice_basis(instance: ChallengeInstance) -> List[List[int]]:
    """Build the 2n x 2n lattice basis M = [I_n, A; 0, q*I_n]."""
    n = instance.dimension
    q = instance.modulus
    A = instance.matrix

    m = 2 * n
    basis: List[List[int]] = [[0] * m for _ in range(m)]

    for i in range(n):
        basis[i][i] = 1
        for j in range(n):
            basis[i][n + j] = A[j][i]   # column i of A (transposed)

    for i in range(n):
        basis[n + i][n + i] = q

    return basis


def _dot(a: List[int], b: List[int]) -> int:
    s = 0
    for x, y in zip(a, b):
        s += x * y
    return s


def _norm_sq(v: List[int]) -> int:
    s = 0
    for x in v:
        s += x * x
    return s


def lll_reduce(
    basis: List[List[int]],
    delta: float = 0.75,
    cost: Optional[OperationMeter] = None,
) -> Tuple[List[List[int]], int]:
    """LLL reduction with correct incremental Gram-Schmidt updates."""
    n = len(basis)
    m = len(basis[0])

    B = [row[:] for row in basis]
    if cost is not None:
        cost.memory_reads(n * m)

    mu: List[List[float]] = [[0.0] * i for i in range(n)]
    B_star: List[List[int]] = [None] * n

    def update_mu(k: int, j: int) -> None:
        if cost is not None:
            cost.memory_reads(m)
            cost.memory_reads(m)
        denom = float(_norm_sq(B_star[j]))
        if denom == 0.0:
            mu[k][j] = 0.0
            return
        num = float(_dot(B[k], B_star[j]))
        if cost is not None:
            cost.additions(m)
            cost.multiplications(m)
        mu[k][j] = num / denom

    def size_reduce(k: int, j: int) -> bool:
        if cost is not None:
            cost.memory_reads(m)
        if abs(mu[k][j]) <= 0.5:
            return False
        r = round(mu[k][j])
        if cost is not None:
            cost.memory_reads(m)
            cost.memory_writes(m)
            cost.multiplications(m)
            cost.additions(m)
        for idx in range(m):
            B[k][idx] -= r * B_star[j][idx]
        mu[k][j] -= r
        for l in range(j + 1, k):
            update_mu(k, l)
        return True

    def update_bs(k: int) -> None:
        b = B[k][:]
        for j in range(k):
            r = round(mu[k][j])
            if r != 0:
                for idx in range(m):
                    b[idx] -= r * B_star[j][idx]
        B_star[k] = b

    for i in range(n):
        B_star[i] = B[i][:]
        for j in range(i):
            update_mu(i, j)
            size_reduce(i, j)
        update_bs(i)

    passes = 0
    k = 1

    while k < n and passes < 100000:
        passes += 1
        if cost is not None:
            cost.memory_reads(m)
            cost.memory_reads(m)
        norm_k = float(_norm_sq(B_star[k]))
        norm_prev = float(_norm_sq(B_star[k - 1]))
        mu_kk1 = mu[k][k - 1]

        if norm_k >= (delta - mu_kk1 * mu_kk1) * norm_prev:
            k += 1
        else:
            B[k], B[k - 1] = B[k - 1], B[k]
            if cost is not None:
                cost.basis_updates(1)
                cost.memory_reads(2 * m)
                cost.memory_writes(2 * m)

            # Rebuild mu for k-1 (entries 0..k-2) and k (entries 0..k-1)
            # using current B_star[0..k-2] which are unchanged by the swap.
            # B_star[k-1] and B_star[k] will be recomputed below.
            mu[k] = [0.0] * k
            for j in range(k):
                update_mu(k, j)
            mu[k - 1] = [0.0] * (k - 1)
            for j in range(k - 1):
                update_mu(k - 1, j)

            # Do NOT swap B_star — both will be recomputed by update_bs.
            # Recompute B_star[k-1] first (uses B[k-1]=old B[k] and
            # B_star[0..k-2] which are correct).
            update_bs(k - 1)

            # Now recompute mu[k][k-1] against the NEW B_star[k-1],
            # since it was just rebuilt from old B[k] (not old B[k-1]).
            update_mu(k, k - 1)

            # Recompute B_star[k] using the corrected mu[k][k-1].
            update_bs(k)

            if k + 1 < n:
                update_mu(k + 1, k - 1)
                update_mu(k + 1, k)
                size_reduce(k + 1, k - 1)
                size_reduce(k + 1, k)
                update_bs(k + 1)

            size_reduce(k, k - 1)
            update_bs(k)
            k = max(1, k - 1)

    return B, passes


def _babai_closest(
    reduced_basis: List[List[int]],
    target: List[int],
    cost: Optional[OperationMeter] = None,
) -> List[int]:
    """Babai nearest-plane: find lattice vector closest to target."""
    m = len(reduced_basis)
    n = len(reduced_basis[0])

    bs: List[List[int]] = []
    for i in range(m):
        bi_star = reduced_basis[i][:]
        for j in range(i):
            denom = float(_norm_sq(bs[j]))
            if denom == 0.0:
                continue
            num = float(_dot(reduced_basis[i], bs[j]))
            mu = num / denom
            if abs(mu) > 0.5:
                r = round(mu)
                if r != 0:
                    for idx in range(n):
                        bi_star[idx] -= r * bs[j][idx]
        bs.append(bi_star)

    coeffs = [0] * m
    residual = target[:]

    for i in range(m - 1, -1, -1):
        denom = float(_norm_sq(bs[i]))
        if denom == 0.0:
            continue
        num = float(_dot(residual, bs[i]))
        c = round(num / denom)
        coeffs[i] = c
        if cost is not None:
            cost.memory_reads(n * 2)
            cost.multiplications(n)
            cost.additions(n)
        for j in range(n):
            residual[j] -= c * reduced_basis[i][j]

    result = [0] * n
    for i in range(m):
        ci = coeffs[i]
        if ci != 0:
            for j in range(n):
                result[j] += ci * reduced_basis[i][j]

    return result


def _check_x(
    x_part: List[int],
    instance: ChallengeInstance,
    cost: Optional[OperationMeter] = None,
) -> bool:
    n = instance.dimension
    q = instance.modulus
    eta = instance.eta
    A = instance.matrix
    t = instance.target

    if any(abs(v) > eta for v in x_part):
        return False
    if cost is not None:
        cost.memory_reads(n)
    Ax = mat_vec_mul(A, tuple(x_part), q)
    if cost is not None:
        cost.memory_reads(n * n)
        cost.additions(n)
        cost.multiplications(n)
        cost.modular_reductions(n)
    return Ax == t


def _search_short_vector(
    reduced_basis: List[List[int]],
    instance: ChallengeInstance,
    cost: Optional[OperationMeter] = None,
) -> Optional[Tuple[int, ...]]:
    """Search reduced basis for valid c via Babai + pair/triple fallback."""
    n = instance.dimension
    t = instance.target
    m = 2 * n

    # Babai nearest-plane to target (0, t)
    target = [0] * n + list(t)
    candidate_vec = _babai_closest(reduced_basis, target, cost)
    x_part = candidate_vec[:n]
    if _check_x(x_part, instance, cost):
        return tuple(x_part)

    # Individual basis vectors
    for row in reduced_basis:
        x_part = row[:n]
        if _check_x(x_part, instance, cost):
            return tuple(x_part)

    # Pairs
    k = len(reduced_basis)
    coeff_range = (-2, -1, 0, 1, 2)
    for i, j in combinations(range(k), 2):
        for ci, cj in product(coeff_range, repeat=2):
            if ci == 0 and cj == 0:
                continue
            x_part = [
                ci * reduced_basis[i][dim] + cj * reduced_basis[j][dim]
                for dim in range(n)
            ]
            if _check_x(x_part, instance, cost):
                return tuple(x_part)

    # Triples
    coeff_range3 = (-1, 0, 1)
    limit = min(k, 20)
    for i, j, l in combinations(range(limit), 3):
        for ci, cj, cl in product(coeff_range3, repeat=3):
            if ci == 0 and cj == 0 and cl == 0:
                continue
            x_part = [
                ci * reduced_basis[i][dim]
                + cj * reduced_basis[j][dim]
                + cl * reduced_basis[l][dim]
                for dim in range(n)
            ]
            if _check_x(x_part, instance, cost):
                return tuple(x_part)

    # Small-instance exhaustive search
    if n <= 8:
        indexed = sorted(enumerate(reduced_basis), key=lambda p: _norm_sq(p[1]))
        short_indices = [idx for idx, _ in indexed[:n]]
        coeff_range_full = tuple(range(-instance.eta, instance.eta + 1))
        for combo in combinations(short_indices, min(n, 6)):
            for coeffs in product(coeff_range_full, repeat=len(combo)):
                if all(c == 0 for c in coeffs):
                    continue
                x_part = [
                    sum(coeffs[idx] * reduced_basis[combo[idx]][dim]
                        for idx in range(len(combo)))
                    for dim in range(n)
                ]
                if _check_x(x_part, instance, cost):
                    return tuple(x_part)

    return None


def solve(instance: ChallengeInstance, cost: OperationMeter) -> Candidate:
    """Recover c with |c_i| <= eta and A*c == t (mod q) via LLL."""
    n = instance.dimension
    q = instance.modulus

    if n <= 0 or q <= 2:
        raise CandidateBError("invalid instance dimensions or modulus")
    if len(instance.matrix) != n or len(instance.target) != n:
        raise CandidateBError("instance shape does not match its dimension")
    if any(len(row) != n for row in instance.matrix):
        raise CandidateBError("matrix must be square")

    basis = _build_lattice_basis(instance)
    if cost is not None:
        cost.memory_writes(len(basis) * len(basis[0]))
        cost.memory_reads(instance.dimension * instance.dimension)

    reduced_basis, passes = lll_reduce(basis, delta=0.75, cost=cost)

    max_norm_sq = 0
    for row in reduced_basis:
        ns = _norm_sq(row)
        if ns > max_norm_sq:
            max_norm_sq = ns
    basis_quality_max_norm = math.sqrt(float(max_norm_sq))

    result_x = _search_short_vector(reduced_basis, instance, cost=cost)

    if result_x is None:
        raise CandidateBError(
            f"LLL reduction did not yield a short vector in {passes} passes "
            f"(reduced basis max norm = {basis_quality_max_norm:.1f})"
        )

    return Candidate(coefficients=result_x)


def build_diagnostics(
    passes: int,
    basis_quality_max_norm: float,
    dimension: int,
    modulus: int,
    eta: int,
) -> dict:
    """Build the candidate_diagnostics object for one Candidate B run."""
    return {
        "reduction_passes": passes,
        "basis_quality_max_norm": basis_quality_max_norm,
        "lattice_dimension": dimension * 2,
        "original_dimension": dimension,
        "modulus": modulus,
        "eta": eta,
        "approach": (
            "LLL lattice reduction on the 2n x 2n basis M = [I_n, A; 0, q*I_n]. "
            "After LLL, Babai's nearest-plane algorithm finds the lattice vector "
            "closest to (0, t); its left half (c) is checked against |c_i| <= eta "
            "and A*c == t (mod q). Falls back to pair/triple enumeration. "
            "If the LLL fails to converge, extraction fails despite correct lattice."
        ),
    }
