"""Independent verifier that consumes public instance data only."""

from __future__ import annotations

import hashlib
import json

from mldsafail.math.lattice import mat_vec_mul
from mldsafail.models import Candidate, ChallengeInstance, VerificationResult
from mldsafail.trusted.generator import load_profiles


def verify(instance: ChallengeInstance, candidate: Candidate) -> VerificationResult:
    """Validate the public modular relation and the configured short bound."""
    if not isinstance(instance, ChallengeInstance):
        return VerificationResult(False, "instance has the wrong type")
    if not isinstance(candidate, Candidate):
        return VerificationResult(False, "candidate has the wrong type")
    try:
        configured_profile = load_profiles()[instance.profile]
    except (KeyError, TypeError, ValueError):
        return VerificationResult(False, "instance profile is not a configured toy profile")
    if (
        isinstance(instance.seed, bool)
        or not isinstance(instance.seed, int)
        or instance.seed < 0
        or isinstance(instance.dimension, bool)
        or not isinstance(instance.dimension, int)
        or instance.dimension < 1
        or isinstance(instance.modulus, bool)
        or not isinstance(instance.modulus, int)
        or instance.modulus <= 1
        or isinstance(instance.eta, bool)
        or not isinstance(instance.eta, int)
        or instance.eta < 1
    ):
        return VerificationResult(False, "instance parameters are malformed")
    if (
        instance.dimension != configured_profile.dimension
        or instance.modulus != configured_profile.modulus
        or instance.eta != configured_profile.eta
    ):
        return VerificationResult(False, "instance parameters do not match its fixed toy profile")
    coefficients = candidate.coefficients
    if not isinstance(coefficients, tuple):
        return VerificationResult(False, "candidate coefficients must be a tuple")
    if len(coefficients) != instance.dimension:
        return VerificationResult(False, "candidate dimension does not match instance")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in coefficients):
        return VerificationResult(False, "candidate coefficients must be integers")
    if any(abs(value) > instance.eta for value in coefficients):
        return VerificationResult(False, "candidate exceeds the short-vector bound")
    try:
        if (
            not isinstance(instance.matrix, tuple)
            or not isinstance(instance.target, tuple)
            or len(instance.matrix) != instance.dimension
            or len(instance.target) != instance.dimension
            or any(not isinstance(row, tuple) for row in instance.matrix)
            or any(len(row) != instance.dimension for row in instance.matrix)
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for row in instance.matrix
                for value in row
            )
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in instance.target
            )
            or any(
                not 0 <= value < instance.modulus
                for row in instance.matrix
                for value in row
            )
            or any(not 0 <= value < instance.modulus for value in instance.target)
        ):
            return VerificationResult(False, "instance dimensions are malformed")
        public_payload = {
            "seed": instance.seed,
            "profile": instance.profile,
            "dimension": instance.dimension,
            "modulus": instance.modulus,
            "eta": instance.eta,
            "matrix": instance.matrix,
            "target": instance.target,
        }
        expected_id = hashlib.sha256(
            json.dumps(public_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:24]
        if instance.instance_id != expected_id:
            return VerificationResult(False, "instance identifier does not match public data")
        actual = mat_vec_mul(instance.matrix, coefficients, instance.modulus)
    except (TypeError, ValueError):
        return VerificationResult(False, "instance data is malformed")
    if actual != instance.target:
        return VerificationResult(False, "candidate does not satisfy the public relation")
    return VerificationResult(True, "candidate satisfies the public relation", max(map(abs, coefficients)))
