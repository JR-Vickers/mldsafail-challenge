"""Reproduce review probes against the immutable v1 revision, using generated toys only.

Run from the repository root: python research/primitive_selection/review/adversarial_v1.py
No external instances or general-purpose target-input interface are accepted.
"""

from __future__ import annotations

import hashlib
import importlib
import itertools
import json
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

REVISION = "c60e1d069b97006aa22793921e9a2c5a64100edf"
ROOT = Path(__file__).resolve().parents[3]
PREFIX = "research/primitive_selection/"


def committed(name):
    return subprocess.check_output(["git", "show", f"{REVISION}:{PREFIX}{name}"], cwd=ROOT)


def modular_solve(matrix, target, q):
    """Plain modular elimination; decline singular matrices without searching."""
    n = len(matrix)
    work = [[x % q for x in row] + [target[i] % q] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if work[r][col]), None)
        if pivot is None:
            return None
        work[col], work[pivot] = work[pivot], work[col]
        inv = pow(work[col][col], -1, q)
        work[col] = [(x * inv) % q for x in work[col]]
        for row in range(col + 1, n):
            factor = work[row][col]
            if factor:
                work[row][col:] = [(x - factor * y) % q for x, y in
                                  zip(work[row][col:], work[col][col:], strict=True)]
    answer = [0] * n
    for row in range(n - 1, -1, -1):
        answer[row] = (work[row][-1] - sum(work[row][j] * answer[j]
                                         for j in range(row + 1, n))) % q
    return answer


def main():
    with tempfile.TemporaryDirectory(prefix="primitive-review-v1-") as temporary:
        package = Path(temporary) / "review_snapshot"
        package.mkdir()
        (package / "__init__.py").write_text("")
        for name in ("constants", "models", "ring", "generator", "embedding", "verify"):
            (package / f"{name}.py").write_bytes(committed(f"{name}.py"))
        sys.path.insert(0, temporary)
        c, m, ring, gen, emb, ver = [importlib.import_module(f"review_snapshot.{name}") for name in
                                  ("constants", "models", "ring", "generator", "embedding", "verify")]
        records = []
        for profile, eta, seed in itertools.product(c.PROFILES, c.ETAS, c.DEVELOPMENT_SEEDS):
            generated = gen.generate_msis(profile, seed, eta)
            instance = generated.public
            public = instance.to_dict()
            replay = gen.generate_msis(public["profile"], public["seed"], public["eta"])
            secret = gen.generate_mlwe(profile, seed, eta)
            mp = secret.public.to_dict()
            replay_mlwe = gen.generate_mlwe(mp["profile"], mp["seed"], mp["eta"])
            matrix = emb.coefficient_matrix(instance)
            width = instance.rows * instance.n
            square = [row[:width] for row in matrix]
            target = [-row[width] for row in matrix]  # C(last_poly) * coefficient-one.
            start = time.process_time()
            solution = modular_solve(square, target, instance.q)
            elapsed = time.process_time() - start
            exact_recovery = False
            verification = None
            if solution is not None:
                flat = [ring.center(x, instance.q) for x in solution]
                z = tuple(tuple(flat[i:i + instance.n]) for i in range(0, width, instance.n))
                z += ((1,) + (0,) * (instance.n - 1),)
                exact_recovery = z == generated.planted_relation
                verification = ver.verify_msis(instance, m.ShortRelation(z))
            trivial = m.ShortRelation(((instance.q,) + (0,) * (instance.n - 1),) +
                                      ((0,) * instance.n,) * (instance.columns - 1))
            mlwe_basis = emb.mlwe_embedding(secret.public)
            error_row = mlwe_basis[secret.public.l * secret.public.n]
            records.append({
                "profile": profile, "eta": eta, "seed": seed,
                "instance_id": instance.instance_id,
                "msis_public_seed_reconstruction": ver.verify_msis(
                    instance, m.ShortRelation(replay.planted_relation))["verified"],
                "mlwe_public_seed_reconstruction": ver.verify_mlwe(
                    secret.public, m.RecoveredSecret(replay_mlwe.planted_s1, replay_mlwe.planted_s2))["verified"],
                "modular_recovery": exact_recovery,
                "modular_singular_decline": solution is None,
                "modular_cpu_seconds": elapsed,
                "modular_verification": verification,
                "q_unit_verification": ver.verify_msis(instance, trivial),
                "mlwe_embedding_explicit_error_row_norm_squared": sum(x * x for x in error_row),
            })
        # Independent polynomial product then high-degree reduction, not coefficient blocks.
        differential_count = 0
        for a, b in itertools.product(itertools.product(range(5), repeat=2), repeat=2):
            expanded = [0] * 3
            for i, x in enumerate(a):
                for j, y in enumerate(b):
                    expanded[i + j] += x * y
            expected = ((expanded[0] - expanded[2]) % 5, expanded[1] % 5)
            assert ring.negacyclic_mul(a, b, 5) == expected
            C = ring.convolution_matrix(a, 5)
            assert tuple(sum(x * y for x, y in zip(row, b, strict=True)) % 5 for row in C) == expected
            differential_count += 1
        determinant_count = 0
        for flat in itertools.product((-1, 0, 1), repeat=9):
            matrix = tuple(tuple(flat[3*i:3*i+3]) for i in range(3))
            expected = sum((-1 if sum(p[i] > p[j] for i in range(3) for j in range(i+1, 3)) % 2 else 1)
                           * matrix[0][p[0]] * matrix[1][p[1]] * matrix[2][p[2]]
                           for p in itertools.permutations(range(3)))
            assert ver.determinant(matrix) == expected
            determinant_count += 1
        raw = committed("results/development.jsonl")
        cohort = [json.loads(line) for line in raw.splitlines()]
        shares = {}
        for track, solver in (("mlwe", "primal-bkz"), ("mlwe", "hybrid-bdd"),
                              ("msis", "progressive-bkz"), ("msis", "restart-bkz")):
            successful = [r for r in cohort if r["track"] == track and r["solver"] == solver
                          and r["verification_result"]]
            shares[f"{track}/{solver}"] = {
                "successful_cases": len(successful),
                "median_phase_share": statistics.median(r["phase_cpu_seconds"]["reduction"] /
                                                         sum(r["phase_cpu_seconds"].values()) for r in successful),
                "median_complete_worker_cpu_share": statistics.median(
                    r["phase_cpu_seconds"]["reduction"] / r["median_cpu_seconds"] for r in successful),
            }
        summary = {}
        for profile in c.PROFILES:
            selected = [r for r in records if r["profile"] == profile]
            summary[profile] = {
                "cases": len(selected),
                "modular_exact_recoveries": sum(r["modular_recovery"] for r in selected),
                "modular_singular_declines": sum(r["modular_singular_decline"] for r in selected),
                "median_modular_cpu_seconds": statistics.median(r["modular_cpu_seconds"] for r in selected),
                "msis_seed_recoveries": sum(r["msis_public_seed_reconstruction"] for r in selected),
                "mlwe_seed_recoveries": sum(r["mlwe_public_seed_reconstruction"] for r in selected),
                "q_unit_accepted": sum(r["q_unit_verification"]["verified"] for r in selected),
            }
        output = {
            "reviewed_revision": REVISION,
            "created_at": datetime.now(UTC).isoformat(),
            "review_session": "/root/primitive_review",
            "evidence_kind": "adversarial development probes; not a comparison or validation cohort",
            "protocol": "one untuned modular solve per development instance; timing is diagnostic only",
            "cohort_sha256": hashlib.sha256(raw).hexdigest(),
            "cohort_original_revision": sorted({r["git_revision"] for r in cohort}),
            "cohort_original_source_digest": sorted({r["source_digest"] for r in cohort}),
            "differential_ring_and_embedding_fixtures": differential_count,
            "exhaustive_3x3_determinant_fixtures": determinant_count,
            "reduction_shares": shares,
            "summary": summary,
            "records": records,
        }
        print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
