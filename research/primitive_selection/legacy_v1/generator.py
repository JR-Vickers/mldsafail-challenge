"""Repository-controlled deterministic generators; diagnostics stay evaluator-side."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from .constants import PROFILES, STUDY_VERSION
from .models import MLWEInstance, MSISInstance, digest
from .ring import add, mat_vec_mul, negacyclic_mul


def _rng(track: str, profile: str, seed: int, purpose: str) -> random.Random:
    material = f"{STUDY_VERSION}\0{track}\0{profile}\0{seed}\0{purpose}".encode()
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


@dataclass(frozen=True)
class GeneratedMSIS:
    public: MSISInstance
    planted_relation: tuple[tuple[int, ...], ...]


def generate_mlwe(profile: str, seed: int, eta: int) -> GeneratedMLWE:
    cfg = PROFILES[profile]
    n, q, k, l = cfg["n"], cfg["q"], cfg["k"], cfg["l"]
    a_rng = _rng("mlwe", profile, seed, "matrix")
    s1_rng = _rng("mlwe", profile, seed, "secret-s1")
    s2_rng = _rng("mlwe", profile, seed, "secret-s2")
    A = tuple(tuple(_uniform_poly(a_rng, n, q) for _ in range(l)) for _ in range(k))
    s1 = tuple(_short_poly(s1_rng, n, eta) for _ in range(l))
    s2 = tuple(_short_poly(s2_rng, n, eta) for _ in range(k))
    product = mat_vec_mul(A, s1, q)
    t = tuple(add(p, e, q) for p, e in zip(product, s2, strict=True))
    draft = MLWEInstance(profile, seed, n, q, k, l, eta, A, t)
    public = MLWEInstance(profile, seed, n, q, k, l, eta, A, t, digest(draft.payload()))
    public.validate()
    return GeneratedMLWE(public, s1, s2)


def generate_msis(profile: str, seed: int, eta: int) -> GeneratedMSIS:
    cfg = PROFILES[profile]
    n, q = cfg["n"], cfg["q"]
    rows, columns = cfg["msis_rows"], cfg["msis_cols"]
    a_rng = _rng("msis", profile, seed, "matrix")
    z_rng = _rng("msis", profile, seed, "relation")
    prefix = tuple(tuple(_uniform_poly(a_rng, n, q) for _ in range(columns - 1)) for _ in range(rows))
    z_prefix = tuple(_short_poly(z_rng, n, eta) for _ in range(columns - 1))
    # A final relation component of 1 makes the planted relation primitive.
    z_last = (1,) + (0,) * (n - 1)
    last_column = []
    for row in prefix:
        acc = (0,) * n
        for entry, coeff in zip(row, z_prefix, strict=True):
            acc = add(acc, negacyclic_mul(entry, coeff, q), q)
        last_column.append(tuple((-x) % q for x in acc))
    A = tuple(tuple(row) + (last_column[i],) for i, row in enumerate(prefix))
    relation = z_prefix + (z_last,)
    flat = [x for poly in relation for x in poly]
    norm_squared = sum(x * x for x in flat)
    norm_infinity = max(abs(x) for x in flat)
    draft = MSISInstance(profile, seed, n, q, rows, columns, eta, A, norm_squared, norm_infinity)
    public = MSISInstance(profile, seed, n, q, rows, columns, eta, A,
                          norm_squared, norm_infinity, digest(draft.payload()))
    public.validate()
    return GeneratedMSIS(public, relation)
