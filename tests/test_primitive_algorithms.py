"""Independent tiny-fixture comparisons for the v2 research algorithms."""

from __future__ import annotations

import itertools
import random
from dataclasses import replace

import pytest

from research.primitive_selection.embedding import coefficient_matrix, derive_bkz, mlwe_primal_basis
from research.primitive_selection.generator import generate_mlwe, generate_msis
from research.primitive_selection.models import MLWEInstance, RecoveredSecret, digest
from research.primitive_selection.simple_baselines import affine_modular_solutions, solve_mlwe_direct, solve_msis_direct, solve_msis_sparse
from research.primitive_selection.solvers import Instrumentation, run_solver, solve_mlwe_exhaustive
from research.primitive_selection.verify import determinant, verify_bkz, verify_mlwe, verify_msis


def _fixture(a, t, q, eta=1):
    draft = MLWEInstance("fixture", len(a), q, 1, 1, eta, ((a,),), (t,))
    return replace(draft, instance_id=digest(draft.payload()))


def _naive_mul(a, b, q):
    n = len(a)
    out = [0] * n
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[(i + j) % n] += (-1 if i + j >= n else 1) * x * y
    return tuple(x % q for x in out)


@pytest.mark.parametrize("n,q", [(1, 3), (2, 5), (4, 17), (8, 97)])
def test_coefficient_embedding_matches_independent_ring_multiplication(n, q):
    rng = random.Random(991 + n)
    for _ in range(12):
        a = tuple(rng.randrange(q) for _ in range(n))
        secret = tuple(rng.randrange(-2, 3) for _ in range(n))
        instance = _fixture(a, (0,) * n, q)
        matrix = coefficient_matrix(instance)
        assert tuple(sum(x * y for x, y in zip(row, secret, strict=True)) % q for row in matrix) == _naive_mul(a, secret, q)
        assert abs(determinant(mlwe_primal_basis(instance))) == q ** n


def test_affine_modular_solver_matches_every_tiny_linear_system():
    q = 3
    vectors = tuple(itertools.product(range(q), repeat=2))
    for matrix in itertools.product(vectors, repeat=2):
        for target in vectors:
            expected = {x for x in vectors if tuple(sum(a * b for a, b in zip(row, x, strict=True)) % q
                                                   for row in matrix) == target}
            result = affine_modular_solutions(matrix, target, q)
            if result is None:
                assert not expected
                continue
            constant, directions = result
            actual = {tuple((constant[j] + sum(x * direction[j] for x, direction in zip(values, directions, strict=True))) % q
                            for j in range(2)) for values in itertools.product(range(q), repeat=len(directions))}
            assert actual == expected


def test_bounded_mlwe_exhaustive_matches_every_tiny_evaluator_fixture():
    q = 5
    short = tuple(itertools.product(range(-1, 2), repeat=2))
    for a in itertools.product(range(q), repeat=2):
        attainable = {tuple((p + e) % q for p, e in zip(_naive_mul(a, s1, q), s2, strict=True))
                      for s1 in short for s2 in short}
        for t in itertools.product(range(q), repeat=2):
            instance = _fixture(a, t, q)
            candidate = solve_mlwe_exhaustive(instance, {"max_candidates": 9}, Instrumentation({}, {}))
            assert (candidate is not None) == (t in attainable)
            if candidate is not None:
                assert verify_mlwe(instance, candidate)["verified"]


def test_exhaustive_cap_counts_only_independent_secret_coefficients():
    instance = generate_mlwe("small", 2, 2).public
    metrics = Instrumentation({}, {})
    candidate = solve_mlwe_exhaustive(instance, {"max_candidates": 625}, metrics)
    assert verify_mlwe(instance, candidate)["verified"]
    assert 1 <= metrics.counters["exhaustive_candidates"] <= 625
    capped = Instrumentation({}, {})
    assert solve_mlwe_exhaustive(instance, {"max_candidates": 624}, capped) is None
    assert capped.counters["search_space_skipped"] == 625


@pytest.mark.parametrize("profile", ["small", "medium", "large"])
@pytest.mark.parametrize("eta", [1, 2])
def test_public_matrix_alone_exposes_planted_msis_shortcut(profile, eta):
    instance = generate_msis(profile, 0, eta).public
    assert not hasattr(instance, "seed")
    candidate, counters = solve_msis_direct(instance)
    assert verify_msis(instance, candidate)["verified"]
    assert counters["linear_free_variables"] >= 0
    sparse, _ = solve_msis_sparse(instance)
    if sparse is not None:
        assert verify_msis(instance, sparse)["verified"]


def test_modular_mlwe_answer_does_not_bypass_shortness():
    instance = generate_mlwe("medium", 0, 2).public
    candidate, _ = solve_mlwe_direct(instance)
    assert candidate is not None
    assert not verify_mlwe(instance, candidate)["verified"]
    complete_candidate, _, metrics = run_solver("mlwe", "direct-linear", instance)
    assert complete_candidate is None
    assert metrics.counters["algebraic_candidate_outside_bound"] == 1
    assert "search_space_skipped" not in metrics.counters


def test_simple_baselines_enter_full_portfolio_without_lattice_backend():
    instance = generate_msis("medium", 2, 2).public
    candidate, _, metrics = run_solver("msis", "direct-linear", instance)
    assert verify_msis(instance, candidate)["verified"]
    assert metrics.counters["solver_backend"] == "python"
    assert "reduction" not in metrics.phases
    sparse, _, sparse_metrics = run_solver("msis", "sparse-relation", instance)
    assert sparse is None or verify_msis(instance, sparse)["verified"]
    assert sparse_metrics.counters["solver_backend"] == "python"


@pytest.mark.parametrize("profile", ["small", "medium"])
@pytest.mark.parametrize("eta", [1, 2])
@pytest.mark.parametrize("solver", ["primal-lll", "primal-bkz", "hybrid-bdd"])
def test_distinct_cvp_and_babai_decoders_are_correct_on_calibrated_profiles(profile, eta, solver):
    pytest.importorskip("fpylll")
    instance = generate_mlwe(profile, 0, eta).public
    candidate, _, metrics = run_solver("mlwe", solver, instance)
    assert verify_mlwe(instance, candidate)["verified"]
    if solver == "hybrid-bdd":
        assert metrics.counters["babai_candidates"] >= 1
        assert "enumeration_candidates" not in metrics.counters
        assert metrics.counters["bkz_calls"] == 1


@pytest.mark.parametrize("solver", ["lll-only", "fixed-bkz", "progressive-bkz"])
def test_all_reduction_families_preserve_exact_unimodular_basis(solver):
    pytest.importorskip("fpylll")
    instance = derive_bkz(generate_mlwe("small", 1, 1).public)
    candidate, _, _ = run_solver("bkz", solver, instance)
    assert verify_bkz(instance, candidate)["verified"]


def test_out_of_bound_mlwe_witness_rejected_on_tiny_fixture():
    instance = _fixture((1, 0), (0, 0), 5)
    assert not verify_mlwe(instance, RecoveredSecret(((5, 0),), ((0, 0),)))["verified"]
