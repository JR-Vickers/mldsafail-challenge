"""Independent complete MLWE equation and bound verification."""
from __future__ import annotations
from typing import Any
from .models import MLWEInstance, RecoveredSecret, candidate_from_dict
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
    except (AttributeError, TypeError, ValueError) as exc:
        return {"verified": False, "failure_reason": str(exc)}

def verify_candidate(instance, value):
    if value is None:
        return {"verified": False, "failure_reason": "solver returned no candidate"}
    try:
        return verify_mlwe(instance, candidate_from_dict(value))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        return {"verified": False, "failure_reason": f"malformed candidate: {exc}"}
