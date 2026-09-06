from __future__ import annotations

import copy
import json
import random
import statistics

import pytest

from research.primitive_selection.constants import ETAS, PROFILES
from research.primitive_selection.embedding import derive_bkz, mlwe_embedding, msis_embedding
from research.primitive_selection.generator import generate_mlwe, generate_msis
from research.primitive_selection.models import (
    BKZInstance,
    MLWEInstance,
    RecoveredSecret,
    ReducedBasis,
    ShortRelation,
    canonical_json,
    digest,
    instance_from_dict,
)
from research.primitive_selection.ring import add, mat_vec_mul, negacyclic_mul
from research.primitive_selection.verify import verify_bkz, verify_mlwe, verify_msis


def naive_mul(a, b, q):
    n = len(a)
    result = [0] * n
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            sign = -1 if i + j >= n else 1
            result[(i + j) % n] = (result[(i + j) % n] + sign * x * y) % q
    return tuple(result)


@pytest.mark.parametrize("n,q", [(8, 97), (16, 193), (32, 257)])
def test_ring_arithmetic_properties(n, q):
    rng = random.Random(n)
    for _ in range(10):
        a = tuple(rng.randrange(q) for _ in range(n))
        b = tuple(rng.randrange(q) for _ in range(n))
        c = tuple(rng.randrange(q) for _ in range(n))
        assert add(a, b, q) == add(b, a, q)
        assert negacyclic_mul(a, b, q) == naive_mul(a, b, q)
        assert negacyclic_mul(add(a, b, q), c, q) == add(
            negacyclic_mul(a, c, q), negacyclic_mul(b, c, q), q
        )


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("eta", ETAS)
def test_generators_are_deterministic_serializable_and_valid(profile, eta):
    mlwe = generate_mlwe(profile, 4, eta)
    msis = generate_msis(profile, 4, eta)
    assert mlwe == generate_mlwe(profile, 4, eta)
    assert msis == generate_msis(profile, 4, eta)
    assert instance_from_dict(json.loads(canonical_json(mlwe.public.to_dict()))) == mlwe.public
    assert instance_from_dict(json.loads(canonical_json(msis.public.to_dict()))) == msis.public
    assert verify_mlwe(mlwe.public, RecoveredSecret(mlwe.planted_s1, mlwe.planted_s2))["verified"]
    assert verify_msis(msis.public, ShortRelation(msis.planted_relation))["verified"]


def test_domain_separation_changes_public_objects():
    objects = {
        generate_mlwe("small", 0, 1).public.instance_id,
        generate_mlwe("small", 1, 1).public.instance_id,
        generate_mlwe("medium", 0, 1).public.instance_id,
        generate_msis("small", 0, 1).public.instance_id,
        generate_msis("small", 1, 1).public.instance_id,
    }
    assert len(objects) == 5
    # Matrix and secret streams are independently domain separated.
    generated = generate_mlwe("small", 0, 1)
    assert generated.public.A[0][0] != generated.planted_s1[0]


def test_embeddings_contain_planted_vectors_and_have_provenance():
    mlwe = generate_mlwe("small", 0, 1)
    basis = mlwe_embedding(mlwe.public)
    x = tuple(v for poly in mlwe.planted_s1 + mlwe.planted_s2 for v in poly)
    preliminary = tuple(-v for v in x) + (0,) * (mlwe.public.k * mlwe.public.n) + (1,)
    residual = tuple(sum(c * row[j] for c, row in zip(preliminary, basis, strict=True)) for j in range(len(basis)))
    q_coeffs = tuple(-v // mlwe.public.q for v in residual[len(x):-1])
    coefficients = tuple(-v for v in x) + q_coeffs + (1,)
    vector = tuple(sum(c * row[j] for c, row in zip(coefficients, basis, strict=True)) for j in range(len(basis)))
    assert vector == tuple(-v for v in x) + (0,) * (mlwe.public.k * mlwe.public.n) + (1,)

    msis = generate_msis("small", 0, 1)
    basis = msis_embedding(msis.public)
    z = tuple(v for poly in msis.planted_relation for v in poly)
    preliminary = z + (0,) * (msis.public.rows * msis.public.n)
    residual = tuple(sum(c * row[j] for c, row in zip(preliminary, basis, strict=True)) for j in range(len(basis)))
    quotients = tuple(-v // msis.public.q for v in residual[len(z):])
    coefficients = z + quotients
    vector = tuple(sum(c * row[j] for c, row in zip(coefficients, basis, strict=True)) for j in range(len(basis)))
    assert vector == z + (0,) * (msis.public.rows * msis.public.n)
    derived = derive_bkz(msis.public)
    assert derived.source_instance_id == msis.public.instance_id
    assert derived.source_track == "msis"


def test_verifiers_reject_malformed_and_invalid_candidates():
    generated = generate_mlwe("small", 0, 1)
    wrong = list(generated.planted_s1)
    wrong[0] = (2,) + wrong[0][1:]
    assert "outside bound" in verify_mlwe(
        generated.public, RecoveredSecret(tuple(wrong), generated.planted_s2)
    )["failure_reason"]
    altered = copy.deepcopy(json.loads(canonical_json(generated.public.to_dict())))
    altered["instance_id"] = "0" * 64
    with pytest.raises(ValueError, match="instance id"):
        instance_from_dict(altered)

    msis = generate_msis("small", 0, 1).public
    zero = ShortRelation(((0,) * msis.n,) * msis.columns)
    assert "zero relation" in verify_msis(msis, zero)["failure_reason"]
    invalid = ShortRelation(((1,) + (0,) * (msis.n - 1),) + ((0,) * msis.n,) * (msis.columns - 1))
    assert "not a relation" in verify_msis(msis, invalid)["failure_reason"]


def test_bkz_verifier_checks_exact_transformation_and_unimodularity():
    instance = derive_bkz(generate_msis("small", 2, 1).public)
    d = len(instance.basis)
    identity = tuple(tuple(int(i == j) for j in range(d)) for i in range(d))
    assert verify_bkz(instance, ReducedBasis(instance.basis, identity))["verified"]
    non_unimodular = list(map(list, identity))
    non_unimodular[0][0] = 2
    result = verify_bkz(instance, ReducedBasis(instance.basis, tuple(map(tuple, non_unimodular))))
    assert not result["verified"]

    altered_basis = list(map(list, instance.basis))
    altered_basis[0][0] += 1
    result = verify_bkz(instance, ReducedBasis(tuple(map(tuple, altered_basis)), identity))
    assert "not U times" in result["failure_reason"]


def test_known_tiny_mlwe_fixture_is_solved_by_brute_force_and_lattice():
    pytest.importorskip("fpylll")
    from research.primitive_selection.solvers import run_solver

    A = ((((1, 0),),))
    t = ((0, 1),)
    draft = MLWEInstance("fixture", 0, 2, 5, 1, 1, 1, A, t)
    instance = MLWEInstance("fixture", 0, 2, 5, 1, 1, 1, A, t, digest(draft.payload()))
    for solver in ("exhaustive", "primal-lll"):
        candidate, _, _ = run_solver("mlwe", solver, instance)
        assert verify_mlwe(instance, candidate)["verified"]


def test_public_solver_payloads_exclude_planted_witnesses():
    mlwe = generate_mlwe("small", 7, 1)
    msis = generate_msis("small", 7, 1)
    mlwe_json = canonical_json(mlwe.public.to_dict())
    msis_json = canonical_json(msis.public.to_dict())
    assert b"planted" not in mlwe_json and b"s1" not in mlwe_json and b"s2" not in mlwe_json
    assert b"planted" not in msis_json and b"relation" not in msis_json.replace(b"relation_quality_target", b"")


def test_validation_seed_derivation_requires_nonce_and_is_profile_separated():
    from research.primitive_selection.runner import validation_seeds

    with pytest.raises(ValueError, match="nonce"):
        validation_seeds("short", "small")
    small = validation_seeds("reviewer-nonce-0001", "small")
    assert small == validation_seeds("reviewer-nonce-0001", "small")
    assert len(small) == len(set(small)) == 20
    assert set(small).isdisjoint(validation_seeds("reviewer-nonce-0001", "medium"))


def test_result_audit_detects_output_tampering(tmp_path):
    from research.primitive_selection.audit import audit

    repetitions = [{"cpu_seconds": value, "candidate": None} for value in (0.3, 0.1, 0.2)]
    record = {
        "schema_version": "1", "study_version": "primitive-selection-v1", "git_revision": "a" * 40,
        "container_image_digest": "sha256:test", "host": {}, "track": "mlwe", "profile": "small",
        "seed": 0, "eta": 1, "solver": "x", "solver_parameters": {}, "verification_result": False,
        "failure_reason": "no candidate", "median_wall_seconds": 0.3,
        "median_cpu_seconds": statistics.median(r["cpu_seconds"] for r in repetitions),
        "peak_rss_bytes": 1, "answer_quality": {}, "timeout": False, "memory_limit": False,
        "diagnostic_counters": {}, "input_digest": "b" * 64,
        "output_digest": digest([None, None, None]), "source_digest": "c" * 64,
        "repetitions": repetitions, "cohort": "development", "validation_nonce": None,
    }
    path = tmp_path / "results.jsonl"
    path.write_text(json.dumps(record) + "\n")
    assert audit([path])["records"] == 1
    record["output_digest"] = "0" * 64
    path.write_text(json.dumps(record) + "\n")
    with pytest.raises(ValueError, match="output digest"):
        audit([path])
