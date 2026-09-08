"""Canonical JSON contracts for primitive-selection inputs and outputs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from .constants import (
    MAX_MATRIX_ENTRIES,
    MAX_MODULE_RANK,
    MAX_N,
    MAX_Q,
    MAX_SERIALIZED_BYTES,
    PROFILES,
    SCHEMA_VERSION,
    STUDY_VERSION,
)

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
class MSISInstance:
    profile: str
    n: int
    q: int
    rows: int
    columns: int
    eta: int
    A: PolyMatrix
    target_norm_squared: int
    target_norm_infinity: int
    instance_id: str = ""
    schema_version: str = SCHEMA_VERSION
    study_version: str = STUDY_VERSION
    track: Literal["msis"] = "msis"

    def payload(self) -> dict[str, Any]:
        value = _base(self.track, self.profile)
        value.update({"ring": {"modulus": self.q, "degree": self.n, "polynomial": "x^n+1"},
                      "dimensions": {"rows": self.rows, "columns": self.columns}, "eta": self.eta,
                      "A": self.A, "relation_quality_target": {
                          "norm_squared": self.target_norm_squared,
                          "norm_infinity": self.target_norm_infinity,
                      }})
        return value

    def validate(self) -> None:
        _check_ring(self.n, self.q)
        if not (type(self.rows) is int and type(self.columns) is int
                and 1 <= self.rows < self.columns <= MAX_MODULE_RANK):
            raise ValueError("MSIS requires bounded columns > rows")
        if type(self.eta) is not int or self.eta not in (1, 2):
            raise ValueError("eta outside study grid")
        _check_matrix(self.A, self.rows, self.columns, self.n, self.q)
        if (type(self.target_norm_squared) is not int or type(self.target_norm_infinity) is not int
                or not 0 < self.target_norm_infinity < self.q
                or not 0 < self.target_norm_squared < self.q ** 2):
            raise ValueError("invalid relation-quality target")
        if self.instance_id != digest(self.payload()):
            raise ValueError("instance id does not match canonical payload")

    def to_dict(self) -> dict[str, Any]:
        value = self.payload()
        value["instance_id"] = self.instance_id
        return value


@dataclass(frozen=True)
class BKZInstance:
    profile: str
    source_track: Literal["mlwe", "msis"]
    source_instance_id: str
    basis: tuple[tuple[int, ...], ...]
    instance_id: str = ""
    schema_version: str = SCHEMA_VERSION
    study_version: str = STUDY_VERSION
    track: Literal["bkz"] = "bkz"

    def payload(self) -> dict[str, Any]:
        value = _base(self.track, self.profile)
        value.update({"source": {"track": self.source_track, "instance_id": self.source_instance_id},
                      "basis": self.basis})
        return value

    def validate(self) -> None:
        if self.source_track not in ("mlwe", "msis") or len(self.source_instance_id) != 64:
            raise ValueError("invalid BKZ provenance")
        dimension = len(self.basis)
        if not dimension or dimension > 384 or any(len(row) != dimension for row in self.basis):
            raise ValueError("BKZ basis must be a bounded square matrix")
        if any(type(x) is not int for row in self.basis for x in row):
            raise ValueError("BKZ basis must be integral")
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


@dataclass(frozen=True)
class ShortRelation:
    z: PolyVector
    tag: Literal["short_relation"] = "short_relation"

    def to_dict(self) -> dict[str, Any]:
        return {"tag": self.tag, "z": self.z}


@dataclass(frozen=True)
class ReducedBasis:
    basis: tuple[tuple[int, ...], ...]
    transformation: tuple[tuple[int, ...], ...]
    tag: Literal["reduced_basis"] = "reduced_basis"

    def to_dict(self) -> dict[str, Any]:
        return {"tag": self.tag, "basis": self.basis, "transformation": self.transformation}


def instance_from_dict(value: dict[str, Any]) -> MLWEInstance | MSISInstance | BKZInstance:
    if not isinstance(value, dict):
        raise ValueError("instance must be a JSON object")
    if value.get("schema_version") != SCHEMA_VERSION or value.get("study_version") != STUDY_VERSION:
        raise ValueError("unsupported schema or study version")
    if value.get("profile") == "fixture":
        raise ValueError("evaluator-only fixtures cannot cross the solver boundary")
    canonical_json(value)
    if value.get("profile") not in PROFILES:
        raise ValueError("unknown research profile")
    ring = value.get("ring", {})
    dimensions = value.get("dimensions", {})
    track = value.get("track")
    common = (value["profile"],)
    allowed = {"schema_version", "study_version", "track", "profile", "instance_id"}
    extras = {"mlwe": {"ring", "dimensions", "eta", "A", "t"},
              "msis": {"ring", "dimensions", "eta", "A", "relation_quality_target"},
              "bkz": {"source", "basis"}}
    if track not in extras or set(value) != allowed | extras[track]:
        raise ValueError("unexpected or missing public instance fields")
    cfg = PROFILES[value["profile"]]
    if track in ("mlwe", "msis"):
        if ring != {"modulus": cfg["q"], "degree": cfg["n"], "polynomial": "x^n+1"}:
            raise ValueError("ring does not match fixed research profile")
        expected = {"rows": cfg["k"] if track == "mlwe" else cfg["msis_rows"],
                    "columns": cfg["l"] if track == "mlwe" else cfg["msis_cols"]}
        if dimensions != expected:
            raise ValueError("dimensions do not match fixed research profile")
    if track == "mlwe":
        result = MLWEInstance(*common, ring["degree"], ring["modulus"], dimensions["rows"],
                              dimensions["columns"], value["eta"], _poly_matrix(value["A"]),
                              _poly_vector(value["t"]), value["instance_id"])
    elif track == "msis":
        target = value["relation_quality_target"]
        if set(target) != {"norm_squared", "norm_infinity"}:
            raise ValueError("unexpected relation quality fields")
        result = MSISInstance(*common, ring["degree"], ring["modulus"], dimensions["rows"],
                              dimensions["columns"], value["eta"], _poly_matrix(value["A"]),
                              target["norm_squared"], target["norm_infinity"], value["instance_id"])
    elif track == "bkz":
        source = value["source"]
        if set(source) != {"track", "instance_id"}:
            raise ValueError("unexpected basis source fields")
        result = BKZInstance(*common, source["track"], source["instance_id"],
                             tuple(tuple(row) for row in value["basis"]), value["instance_id"])
    else:
        raise ValueError("unknown instance track")
    result.validate()
    return result


def candidate_from_dict(value: dict[str, Any]) -> RecoveredSecret | ShortRelation | ReducedBasis:
    if not isinstance(value, dict):
        raise ValueError("candidate must be a JSON object")
    tag = value.get("tag")
    fields = {"recovered_secret": {"tag", "s1", "s2"}, "short_relation": {"tag", "z"},
              "reduced_basis": {"tag", "basis", "transformation"}}
    if tag not in fields or set(value) != fields[tag]:
        raise ValueError("unexpected or missing candidate fields")
    canonical_json(value)
    if tag == "recovered_secret":
        return RecoveredSecret(_poly_vector(value["s1"]), _poly_vector(value["s2"]))
    if tag == "short_relation":
        return ShortRelation(_poly_vector(value["z"]))
    if tag == "reduced_basis":
        return ReducedBasis(tuple(tuple(row) for row in value["basis"]),
                            tuple(tuple(row) for row in value["transformation"]))
    raise ValueError("unknown candidate tag")
