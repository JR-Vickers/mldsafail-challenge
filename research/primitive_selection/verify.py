"""Independent candidate verification and basis-quality measurement."""

from __future__ import annotations

import math
from typing import Any

from .models import BKZInstance, MLWEInstance, MSISInstance, RecoveredSecret, ReducedBasis, ShortRelation
from .ring import add, mat_vec_mul


def verify_mlwe(instance: MLWEInstance, candidate: RecoveredSecret) -> dict[str, Any]:
    try:
        instance.validate()
        if candidate.tag != "recovered_secret":
            raise ValueError("wrong candidate tag")
        if len(candidate.s1) != instance.l or len(candidate.s2) != instance.k:
            raise ValueError("secret dimensions do not match instance")
        coeffs = [x for poly in candidate.s1 + candidate.s2 for x in poly]
        if any(len(poly) != instance.n for poly in candidate.s1 + candidate.s2):
            raise ValueError("secret polynomial dimensions do not match instance")
        if any(type(x) is not int or abs(x) > instance.eta for x in coeffs):
            raise ValueError("secret coefficient outside bound")
        actual = tuple(add(p, e, instance.q) for p, e in zip(
            mat_vec_mul(instance.A, candidate.s1, instance.q), candidate.s2, strict=True))
        if actual != instance.t:
            raise ValueError("candidate does not satisfy complete MLWE relation")
        return {"verified": True, "failure_reason": None,
                "norm_squared": sum(x * x for x in coeffs),
                "norm_infinity": max(abs(x) for x in coeffs)}
    except (TypeError, ValueError) as exc:
        return {"verified": False, "failure_reason": str(exc)}


def verify_msis(instance: MSISInstance, candidate: ShortRelation) -> dict[str, Any]:
    try:
        instance.validate()
        if candidate.tag != "short_relation" or len(candidate.z) != instance.columns:
            raise ValueError("relation dimensions do not match instance")
        if any(len(poly) != instance.n for poly in candidate.z):
            raise ValueError("relation polynomial dimensions do not match instance")
        coeffs = [x for poly in candidate.z for x in poly]
        if any(type(x) is not int for x in coeffs):
            raise ValueError("relation coefficients must be integers")
        if not any(coeffs):
            raise ValueError("zero relation is not accepted")
        actual = mat_vec_mul(instance.A, candidate.z, instance.q)
        if any(value % instance.q for poly in actual for value in poly):
            raise ValueError("candidate is not a relation modulo q")
        norm_squared = sum(x * x for x in coeffs)
        norm_infinity = max(abs(x) for x in coeffs)
        return {"verified": True, "failure_reason": None, "norm_squared": norm_squared,
                "norm_infinity": norm_infinity,
                "meets_target": norm_squared <= instance.target_norm_squared}
    except (TypeError, ValueError) as exc:
        return {"verified": False, "failure_reason": str(exc)}


def determinant(matrix: tuple[tuple[int, ...], ...]) -> int:
    """Exact fraction-free Bareiss determinant."""
    n = len(matrix)
    if any(len(row) != n for row in matrix):
        raise ValueError("determinant requires a square matrix")
    if n == 0:
        return 1
    work = [list(row) for row in matrix]
    sign = 1
    previous = 1
    for col in range(n - 1):
        pivot = next((row for row in range(col, n) if work[row][col]), None)
        if pivot is None:
            return 0
        if pivot != col:
            work[pivot], work[col] = work[col], work[pivot]
            sign *= -1
        pivot_value = work[col][col]
        for row in range(col + 1, n):
            for j in range(col + 1, n):
                numerator = work[row][j] * pivot_value - work[row][col] * work[col][j]
                work[row][j] = numerator // previous
            work[row][col] = 0
        previous = pivot_value
    return sign * work[-1][-1]


def _matmul(left: tuple[tuple[int, ...], ...], right: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(sum(x * right[k][j] for k, x in enumerate(row)) for j in range(len(right))) for row in left)


def basis_quality(basis: tuple[tuple[int, ...], ...]) -> dict[str, float | int]:
    d = len(basis)
    det_abs = abs(determinant(basis))
    first_norm_squared = sum(x * x for x in basis[0])
    if not det_abs:
        raise ValueError("basis is singular")
    # delta_0 = (||b1|| / det(L)^(1/d))^(1/d), evaluated in logs.
    log_rhf = (0.5 * math.log(first_norm_squared) - math.log(det_abs) / d) / d
    return {"dimension": d, "determinant_abs": det_abs,
            "first_vector_norm_squared": first_norm_squared,
            "root_hermite_factor": math.exp(log_rhf)}


def verify_bkz(instance: BKZInstance, candidate: ReducedBasis) -> dict[str, Any]:
    try:
        instance.validate()
        if candidate.tag != "reduced_basis":
            raise ValueError("wrong candidate tag")
        d = len(instance.basis)
        if (len(candidate.basis) != d or len(candidate.transformation) != d or
                any(len(row) != d for row in candidate.basis + candidate.transformation)):
            raise ValueError("basis or transformation dimensions do not match")
        if any(type(x) is not int for row in candidate.basis + candidate.transformation for x in row):
            raise ValueError("basis and transformation must be integral")
        det_u = determinant(candidate.transformation)
        if abs(det_u) != 1:
            raise ValueError("transformation is not unimodular")
        if _matmul(candidate.transformation, instance.basis) != candidate.basis:
            raise ValueError("claimed basis is not U times the source basis")
        quality = basis_quality(candidate.basis)
        quality.update({"verified": True, "failure_reason": None, "transformation_determinant": det_u})
        return quality
    except (TypeError, ValueError, OverflowError) as exc:
        return {"verified": False, "failure_reason": str(exc)}
