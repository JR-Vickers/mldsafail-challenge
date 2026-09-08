"""Run with python -m research.primitive_selection.review.contract_probe_v2."""

from __future__ import annotations

import itertools
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from research.primitive_selection.constants import DEVELOPMENT_SEEDS, ETAS, PROFILES
from research.primitive_selection.embedding import derive_bkz
from research.primitive_selection.generator import generate_mlwe, generate_msis
from research.primitive_selection.models import (
    MLWEInstance, RecoveredSecret, ShortRelation, canonical_json, digest, instance_from_dict,
)
from research.primitive_selection.runner import _source_digest
from research.primitive_selection.verify import verify_mlwe, verify_msis

ROOT = Path(__file__).resolve().parents[3]


def main():
    counts = {"public_roundtrips": 0, "seed_injections_rejected": 0,
              "q_unit_rejected": 0, "zero_relation_rejected": 0,
              "planted_mlwe_valid": 0, "planted_msis_valid": 0,
              "exhaustive_tiny_candidate_comparisons": 0}
    ids = []
    for profile, eta, seed in itertools.product(PROFILES, ETAS, DEVELOPMENT_SEEDS):
        mlwe, msis = generate_mlwe(profile, seed, eta), generate_msis(profile, seed, eta)
        for instance in (mlwe.public, msis.public, derive_bkz(mlwe.public), derive_bkz(msis.public)):
            public = json.loads(canonical_json(instance.to_dict()))
            assert not hasattr(instance, "seed")
            assert "seed" not in public and "nonce" not in public
            assert instance_from_dict(public) == instance
            ids.append(instance.instance_id)
            counts["public_roundtrips"] += 1
            public["seed"] = seed
            try:
                instance_from_dict(public)
            except ValueError:
                counts["seed_injections_rejected"] += 1
            else:
                raise AssertionError("seed-bearing public object accepted")
        assert verify_mlwe(mlwe.public, RecoveredSecret(mlwe.planted_s1, mlwe.planted_s2))["verified"]
        assert verify_msis(msis.public, ShortRelation(msis.planted_relation))["verified"]
        counts["planted_mlwe_valid"] += 1
        counts["planted_msis_valid"] += 1
        i = msis.public
        q_unit = ShortRelation(((i.q,) + (0,) * (i.n - 1),) + ((0,) * i.n,) * (i.columns - 1))
        zero = ShortRelation(((0,) * i.n,) * i.columns)
        assert not verify_msis(i, q_unit)["verified"]
        assert not verify_msis(i, zero)["verified"]
        counts["q_unit_rejected"] += 1
        counts["zero_relation_rejected"] += 1
    # Independent coefficient equations for A=(1+2x), x^2=-1 modulo5.
    for target in itertools.product(range(5), repeat=2):
        A = (((1, 2),),)
        draft = MLWEInstance("fixture", 2, 5, 1, 1, 1, A, (target,))
        instance = MLWEInstance("fixture", 2, 5, 1, 1, 1, A, (target,), digest(draft.payload()))
        for a, b, c, d in itertools.product(range(-2, 3), repeat=4):
            expected = (max(abs(a), abs(b), abs(c), abs(d)) <= 1
                        and ((a - 2*b + c) % 5, (2*a + b + d) % 5) == target)
            actual = verify_mlwe(instance, RecoveredSecret(((a, b),), ((c, d),)))["verified"]
            assert actual == expected
            counts["exhaustive_tiny_candidate_comparisons"] += 1
    print(json.dumps({"created_at": datetime.now(UTC).isoformat(), "reviewer_session": "/root/primitive_review",
                      "reviewed_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
                      "source_digest": _source_digest(),
                      "scope": "working-source development diagnostics; not freeze acceptance or validation",
                      "counts": counts, "deterministic_instance_ids_digest": digest(ids)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
