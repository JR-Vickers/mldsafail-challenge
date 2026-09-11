"""Frozen MLWE public contracts (research v2 wire format)."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal
from .constants import *
Poly = tuple[int, ...]
PolyVector = tuple[Poly, ...]
PolyMatrix = tuple[PolyVector, ...]

def _poly_vector(value: Any) -> PolyVector:
    if not isinstance(value, list) or any(not isinstance(poly, list) for poly in value):
        raise ValueError("polynomial vector must be a JSON array")
    return tuple(tuple(poly) for poly in value)


def _poly_matrix(value: Any) -> PolyMatrix:
    if not isinstance(value, list):
        raise ValueError("polynomial matrix must be a JSON array")
    return tuple(_poly_vector(row) for row in value)


def canonical_json(value: Any) -> bytes:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    if len(encoded) > MAX_SERIALIZED_BYTES:
        raise ValueError("serialized object exceeds study size cap")
    return encoded


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _base(track: str, profile: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "study_version": STUDY_VERSION,
        "track": track,
        "profile": profile,
    }


def _check_ring(n: int, q: int) -> None:
    if type(n) is not int or not 1 <= n <= MAX_N:
        raise ValueError("n outside study bounds")
    if type(q) is not int or not 3 <= q <= MAX_Q:
        raise ValueError("q outside study bounds")
    if (q - 1) % (2 * n):
        raise ValueError("q must support the configured negacyclic ring")


def _check_matrix(matrix: PolyMatrix, rows: int, cols: int, n: int, q: int) -> None:
    if rows * cols * n > MAX_MATRIX_ENTRIES or len(matrix) != rows:
        raise ValueError("invalid matrix dimensions")
    for row in matrix:
        if len(row) != cols:
            raise ValueError("invalid matrix dimensions")
        for poly in row:
            if len(poly) != n or any(type(x) is not int or not 0 <= x < q for x in poly):
                raise ValueError("invalid polynomial coefficient")


@dataclass(frozen=True)
class MLWEInstance:
    profile: str
    n: int
    q: int
    k: int
    l: int
    eta: int
    A: PolyMatrix
    t: PolyVector
    instance_id: str = ""
    schema_version: str = SCHEMA_VERSION
    study_version: str = STUDY_VERSION
    track: Literal["mlwe"] = "mlwe"

    def payload(self) -> dict[str, Any]:
        value = _base(self.track, self.profile)
        value.update({"ring": {"modulus": self.q, "degree": self.n, "polynomial": "x^n+1"},
                      "dimensions": {"rows": self.k, "columns": self.l}, "eta": self.eta,
                      "A": self.A, "t": self.t})
        return value

    def validate(self) -> None:
        _check_ring(self.n, self.q)
        if not (type(self.k) is int and type(self.l) is int
                and 1 <= self.k <= MAX_MODULE_RANK and 1 <= self.l <= MAX_MODULE_RANK):
            raise ValueError("module rank outside study bounds")
        if type(self.eta) is not int or self.eta not in (1, 2):
            raise ValueError("eta outside study grid")
        _check_matrix(self.A, self.k, self.l, self.n, self.q)
        if len(self.t) != self.k or any(len(p) != self.n for p in self.t):
            raise ValueError("invalid target dimensions")
        if any(type(x) is not int or not 0 <= x < self.q for p in self.t for x in p):
            raise ValueError("invalid target coefficient")
        if self.instance_id != digest(self.payload()):
            raise ValueError("instance id does not match canonical payload")

    def to_dict(self) -> dict[str, Any]:
        value = self.payload()
        value["instance_id"] = self.instance_id
        return value


@dataclass(frozen=True)
class RecoveredSecret:
    s1: PolyVector
    s2: PolyVector
    tag: Literal["recovered_secret"] = "recovered_secret"

    def to_dict(self) -> dict[str, Any]:
        return {"tag": self.tag, "s1": self.s1, "s2": self.s2}

def instance_from_dict(value):
    if not isinstance(value, dict):
        raise ValueError("instance must be a JSON object")
    canonical_json(value)
    if set(value) != {"schema_version", "study_version", "track", "profile", "ring", "dimensions", "eta", "A", "t", "instance_id"}:
        raise ValueError("unexpected or missing public instance fields")
    if value["schema_version"] != SCHEMA_VERSION or value["study_version"] != STUDY_VERSION or value["track"] != "mlwe":
        raise ValueError("unsupported public contract")
    cfg = PROFILES.get(value["profile"])
    if cfg is None:
        raise ValueError("unknown research profile")
    ring, dimensions = value["ring"], value["dimensions"]
    if ring != {"modulus": cfg["q"], "degree": cfg["n"], "polynomial": "x^n+1"} or dimensions != {"rows": cfg["k"], "columns": cfg["l"]}:
        raise ValueError("parameters do not match fixed profile")
    result = MLWEInstance(value["profile"], ring["degree"], ring["modulus"], dimensions["rows"], dimensions["columns"], value["eta"], _poly_matrix(value["A"]), _poly_vector(value["t"]), value["instance_id"])
    result.validate()
    return result

def candidate_from_dict(value):
    if not isinstance(value, dict) or set(value) != {"tag", "s1", "s2"} or value["tag"] != "recovered_secret":
        raise ValueError("unexpected or missing candidate fields")
    canonical_json(value)
    return RecoveredSecret(_poly_vector(value["s1"]), _poly_vector(value["s2"]))
