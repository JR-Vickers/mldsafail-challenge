"""Deterministic generator for bounded, repository-controlled toy instances."""

from __future__ import annotations

import hashlib
import json
import random
import tomllib
from pathlib import Path

from mldsafail.math.lattice import is_invertible, mat_vec_mul
from mldsafail.models import DiagnosticMetadata, ToyInstance, ToyProfile

PROFILE_NAMES = frozenset({"toy-small", "toy-medium", "toy-large"})
MAX_DIMENSION = 64
MAX_MODULUS = 4096
MAX_ETA = 8
_PROFILE_FIELDS = frozenset({"dimension", "modulus", "eta", "public_seeds", "hidden_seeds"})
_SOURCE_PROFILE_PATH = Path(__file__).resolve().parents[3] / "config" / "toy_profiles.toml"
_PACKAGED_PROFILE_PATH = Path(__file__).with_name("toy_profiles.toml")


def _default_profile_path() -> Path:
    """Use the editable repository config or the installed package resource."""
    return _SOURCE_PROFILE_PATH if _SOURCE_PROFILE_PATH.is_file() else _PACKAGED_PROFILE_PATH


def _is_prime(value: int) -> bool:
    if value < 2:
        return False
    divisor = 2
    while divisor * divisor <= value:
        if value % divisor == 0:
            return False
        divisor += 1
    return True


def load_profiles(path: str | Path | None = None) -> dict[str, ToyProfile]:
    """Load and strictly validate the fixed toy profile set.

    A custom path exists for validation tests and trusted administration; it
    does not permit callers to inject a profile into ``generate_instance``.
    """
    profile_path = Path(path) if path is not None else _default_profile_path()
    with profile_path.open("rb") as stream:
        raw = tomllib.load(stream)
    if set(raw) != PROFILE_NAMES:
        raise ValueError(f"profile file must define exactly {sorted(PROFILE_NAMES)}")

    profiles: dict[str, ToyProfile] = {}
    for name in sorted(PROFILE_NAMES):
        values = raw[name]
        if not isinstance(values, dict) or set(values) != _PROFILE_FIELDS:
            raise ValueError(f"profile {name!r} has malformed fields")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values.values()):
            raise ValueError(f"profile {name!r} values must be integers")
        dimension = values["dimension"]
        modulus = values["modulus"]
        eta = values["eta"]
        if not 1 <= dimension <= MAX_DIMENSION:
            raise ValueError(f"profile {name!r} exceeds the dimension cap")
        if not 3 <= modulus <= MAX_MODULUS or not _is_prime(modulus):
            raise ValueError(f"profile {name!r} modulus must be a bounded prime")
        if not 1 <= eta <= MAX_ETA or 2 * eta >= modulus:
            raise ValueError(f"profile {name!r} has an invalid short-vector bound")
        if values["public_seeds"] < 1 or values["hidden_seeds"] < 1:
            raise ValueError(f"profile {name!r} seed counts must be positive")
        profiles[name] = ToyProfile(name=name, **values)
    return profiles


def _rng_for(seed: int, profile: str) -> random.Random:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    domain_seed = hashlib.sha256(f"mldsafail:v1:{profile}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(domain_seed, "big"))


def _generate(seed: int, profile_name: str) -> tuple[ToyInstance, DiagnosticMetadata]:
    profiles = load_profiles()
    try:
        profile = profiles[profile_name]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unknown toy profile: {profile_name!r}") from exc
    rng = _rng_for(seed, profile_name)
    solution = tuple(rng.randint(-profile.eta, profile.eta) for _ in range(profile.dimension))
    if not any(solution):
        solution = (1,) + solution[1:]

    # Rejection sampling is deterministic and tiny at these dimensions. For a
    # random square matrix over a prime field, success is overwhelmingly likely.
    for _attempt in range(128):
        matrix = tuple(
            tuple(rng.randrange(profile.modulus) for _ in range(profile.dimension))
            for _ in range(profile.dimension)
        )
        if is_invertible(matrix, profile.modulus):
            break
    else:  # pragma: no cover - astronomically unlikely, but keeps failure explicit
        raise RuntimeError("could not deterministically construct an invertible toy matrix")

    target = mat_vec_mul(matrix, solution, profile.modulus)
    public_payload = {
        "seed": seed,
        "profile": profile.name,
        "dimension": profile.dimension,
        "modulus": profile.modulus,
        "eta": profile.eta,
        "matrix": matrix,
        "target": target,
    }
    instance_id = hashlib.sha256(
        json.dumps(public_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:24]
    instance = ToyInstance(instance_id=instance_id, **public_payload)
    diagnostic = DiagnosticMetadata(instance_id=instance_id, planted_solution=solution)
    return instance, diagnostic


def generate_instance(seed: int, profile: str) -> ToyInstance:
    """Generate public challenge data only for a named, bounded toy profile."""
    instance, _diagnostic = _generate(seed, profile)
    return instance


def generate_instance_with_diagnostics(
    seed: int, profile: str
) -> tuple[ToyInstance, DiagnosticMetadata]:
    """Trusted test/diagnostic entry point keeping planted data separate."""
    return _generate(seed, profile)
