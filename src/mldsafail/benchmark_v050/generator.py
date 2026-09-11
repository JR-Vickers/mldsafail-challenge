"""Evaluator-only frozen generation. Never included in worker images."""
from __future__ import annotations
import hashlib
import random
from dataclasses import dataclass
from .constants import PROFILES, STUDY_VERSION
from .models import MLWEInstance, digest
from .ring import add, mat_vec_mul

def _rng(track: str, profile: str, seed: int, purpose: str, eta: int = 1) -> random.Random:
    if type(seed) is not int or not 0 <= seed < 2**256:
        raise ValueError("generation seed must be an evaluator integer below 2^256")
    if type(eta) is not int or eta not in (1, 2):
        raise ValueError("eta outside study grid")
    material = f"{STUDY_VERSION}\0{track}\0{profile}\0{eta}\0{seed}\0{purpose}".encode()
    return random.Random(int.from_bytes(hashlib.sha256(material).digest()))


def _uniform_poly(rng: random.Random, n: int, q: int) -> tuple[int, ...]:
    return tuple(rng.randrange(q) for _ in range(n))


def _short_poly(rng: random.Random, n: int, eta: int) -> tuple[int, ...]:
    return tuple(rng.randrange(-eta, eta + 1) for _ in range(n))


@dataclass(frozen=True)
class GeneratedMLWE:
    public: MLWEInstance
    planted_s1: tuple[tuple[int, ...], ...]
    planted_s2: tuple[tuple[int, ...], ...]


def generate_mlwe(profile: str, seed: int, eta: int) -> GeneratedMLWE:
    cfg = PROFILES[profile]
    n, q, k, l = cfg["n"], cfg["q"], cfg["k"], cfg["l"]
    a_rng = _rng("mlwe", profile, seed, "matrix", eta)
    s1_rng = _rng("mlwe", profile, seed, "secret-s1", eta)
    s2_rng = _rng("mlwe", profile, seed, "secret-s2", eta)
    A = tuple(tuple(_uniform_poly(a_rng, n, q) for _ in range(l)) for _ in range(k))
    s1 = tuple(_short_poly(s1_rng, n, eta) for _ in range(l))
    s2 = tuple(_short_poly(s2_rng, n, eta) for _ in range(k))
    product = mat_vec_mul(A, s1, q)
    t = tuple(add(p, e, q) for p, e in zip(product, s2, strict=True))
    draft = MLWEInstance(profile, n, q, k, l, eta, A, t)
    public = MLWEInstance(profile, n, q, k, l, eta, A, t, digest(draft.payload()))
    public.validate()
    return GeneratedMLWE(public, s1, s2)
