"""Independent small-fixture correctness and seedless research boundary checks."""

import dataclasses
import itertools
import json

import pytest

from research.primitive_selection.constants import ETAS, PROFILES
from research.primitive_selection.embedding import coefficient_matrix, derive_bkz
from research.primitive_selection.generator import _rng, generate_mlwe, generate_msis
from research.primitive_selection.models import (
    MLWEInstance, RecoveredSecret, ShortRelation, candidate_from_dict,
    canonical_json, digest, instance_from_dict,
)
from research.primitive_selection.verify import verify_mlwe, verify_msis


def test_exhaustive_scalar_mlwe_verification_against_definition():
    # All matrices, targets, and in/out-of-bound candidates on evaluator-only R_5.
    for a, target in itertools.product(range(5), repeat=2):
        draft = MLWEInstance("fixture", 1, 5, 1, 1, 1, (((a,),),), ((target,),))
        instance = dataclasses.replace(draft, instance_id=digest(draft.payload()))
        for s, e in itertools.product(range(-2, 3), repeat=2):
            expected = abs(s) <= 1 and abs(e) <= 1 and (a * s + e) % 5 == target
            actual = verify_mlwe(instance, RecoveredSecret(((s,),), ((e,),)))
            assert actual["verified"] == expected


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("eta", ETAS)
def test_coefficient_embedding_against_independent_polynomial_convolution(profile, eta):
    instance = generate_mlwe(profile, 2, eta).public
    H = coefficient_matrix(instance)
    vector = tuple((i % 5) - 2 for i in range(instance.l * instance.n))
    for row in range(instance.k):
        for out in range(instance.n):
            expected = 0
            for col in range(instance.l):
                for i, a in enumerate(instance.A[row][col]):
                    for j in range(instance.n):
                        if (i + j) % instance.n == out:
                            expected += a * vector[col * instance.n + j] * (-1 if i+j >= instance.n else 1)
            assert sum(x*y for x, y in zip(H[row*instance.n+out], vector)) % instance.q == expected % instance.q


def test_seed_and_evaluator_metadata_absent_and_rejected_at_boundary():
    mlwe = generate_mlwe("small", 7, 1).public
    msis = generate_msis("small", 7, 1).public
    for instance in (mlwe, msis, derive_bkz(mlwe), derive_bkz(msis)):
        assert not hasattr(instance, "seed")
        payload = json.loads(canonical_json(instance.to_dict()))
        assert "seed" not in payload and "nonce" not in payload
        assert instance_from_dict(payload) == instance
        for field in ("seed", "validation_nonce", "planted_s1", "planted_relation", "run_id"):
            altered = {**payload, field: 7}
            with pytest.raises(ValueError, match="fields"):
                instance_from_dict(altered)
    for field in ("seed", "nonce"):
        altered = msis.to_dict()
        altered["relation_quality_target"][field] = 7
        with pytest.raises(ValueError, match="fields"):
            instance_from_dict(altered)


def test_stream_domain_separation_covers_every_parameter_and_purpose():
    labels = [(t, p, s, purpose, e)
              for t in ("mlwe", "msis") for p in PROFILES for s in (0, 1)
              for purpose in ("matrix", "secret-s1", "secret-s2", "relation") for e in ETAS]
    outputs = [_rng(*label).getrandbits(256) for label in labels]
    assert len(set(outputs)) == len(outputs)
    assert outputs == [_rng(*label).getrandbits(256) for label in labels]
    for seed in (-1, True, 2**256, "7"):
        with pytest.raises(ValueError, match="seed"):
            generate_mlwe("small", seed, 1)


def test_msis_rejects_trivial_q_unit_and_bound_violations():
    generated = generate_msis("small", 0, 1)
    i = generated.public
    q_unit = ((i.q,) + (0,)*(i.n-1),) + ((0,)*i.n,)*(i.columns-1)
    assert not verify_msis(i, ShortRelation(q_unit))["verified"]
    doubled = tuple(tuple(2*x for x in p) for p in generated.planted_relation)
    assert not verify_msis(i, ShortRelation(doubled))["verified"]
    assert not verify_msis(i, ShortRelation(((True,)*i.n,)*i.columns))["verified"]
    assert not verify_msis(i, None)["verified"]
    assert not verify_mlwe(generate_mlwe("small", 0, 1).public, None)["verified"]
    with pytest.raises(ValueError, match="fields"):
        candidate_from_dict({"tag": "short_relation", "z": q_unit, "cost": 0})


def test_v1_regeneration_shortcut_is_preserved_as_regression_evidence():
    from research.primitive_selection.legacy_v1.generator import generate_mlwe as old_generate
    from research.primitive_selection.legacy_v1.models import RecoveredSecret as OldSecret
    from research.primitive_selection.legacy_v1.verify import verify_mlwe as old_verify
    old = old_generate("small", 7, 1)
    payload = old.public.to_dict()
    recovered = old_generate(payload["profile"], payload["seed"], payload["eta"])
    assert old_verify(old.public, OldSecret(recovered.planted_s1, recovered.planted_s2))["verified"]
    assert "seed" not in generate_mlwe("small", 7, 1).public.to_dict()
