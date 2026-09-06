"""Thin fpylll adapters and baseline strategy portfolio."""

from __future__ import annotations

import itertools
import random
import time
from dataclasses import dataclass
from typing import Any

from .embedding import coefficient_matrix, mlwe_primal_basis, msis_embedding
from .models import BKZInstance, MLWEInstance, MSISInstance, RecoveredSecret, ReducedBasis, ShortRelation


@dataclass
class Instrumentation:
    phases: dict[str, float]
    counters: dict[str, int | float | str]

    def timed(self, name: str):
        return _Timer(self, name)


class _Timer:
    def __init__(self, metrics: Instrumentation, name: str):
        self.metrics = metrics
        self.name = name

    def __enter__(self):
        self.start = time.process_time()

    def __exit__(self, *_args):
        self.metrics.phases[self.name] = self.metrics.phases.get(self.name, 0.0) + time.process_time() - self.start


def _fpylll():
    try:
        from fpylll import BKZ, GSO, IntegerMatrix, LLL
        from fpylll.fplll.enumeration import Enumeration, EnumerationError, EvaluatorStrategy
    except ImportError as exc:  # pragma: no cover - exercised in the container
        raise RuntimeError("fpylll is required; run through the pinned study container") from exc
    return BKZ, GSO, IntegerMatrix, LLL, Enumeration, EnumerationError, EvaluatorStrategy


def _matrix(rows):
    _, _, IntegerMatrix, _, _, _, _ = _fpylll()
    return IntegerMatrix.from_matrix(rows)


def _tuples(matrix) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(matrix[i, j]) for j in range(matrix.ncols)) for i in range(matrix.nrows))


def _identity(d: int):
    _, _, IntegerMatrix, _, _, _, _ = _fpylll()
    return IntegerMatrix.identity(d)


def _reduce(rows, strategy: str, params: dict[str, Any], metrics: Instrumentation):
    BKZ, _, _, LLL, _, _, _ = _fpylll()
    B = _matrix(rows)
    U = _identity(B.nrows)
    with metrics.timed("reduction"):
        if strategy == "lll":
            LLL.reduction(B, U, delta=float(params.get("delta", 0.99)))
            metrics.counters["lll_calls"] = 1
        elif strategy == "bkz":
            block_size = min(int(params.get("block_size", 10)), B.nrows)
            BKZ.reduction(B, BKZ.Param(block_size=block_size, max_loops=int(params.get("max_loops", 2))), U=U)
            metrics.counters.update({"bkz_calls": 1, "bkz_block_size": block_size,
                                     "bkz_tours_requested": int(params.get("max_loops", 2))})
        elif strategy == "progressive":
            schedule = [b for b in params.get("schedule", [5, 10, 15]) if b <= B.nrows]
            if not schedule:
                schedule = [B.nrows]
            total = tuple(tuple(int(i == j) for j in range(B.nrows)) for i in range(B.nrows))
            for block_size in schedule:
                step = _identity(B.nrows)
                BKZ.reduction(B, BKZ.Param(block_size=block_size, max_loops=1), U=step)
                step_rows = _tuples(step)
                total = tuple(tuple(sum(step_rows[i][k] * total[k][j] for k in range(B.nrows))
                                    for j in range(B.nrows)) for i in range(B.nrows))
            U = _matrix(total)
            metrics.counters.update({"bkz_calls": len(schedule), "bkz_block_size": schedule[-1],
                                     "bkz_tours_requested": len(schedule)})
        else:
            raise ValueError(f"unknown reduction strategy: {strategy}")
    return B, U


def _enumerated_vectors(B, metrics: Instrumentation, limit: int = 16, radius_squared: int | None = None):
    _, GSO, _, _, Enumeration, EnumerationError, EvaluatorStrategy = _fpylll()
    vectors = [_tuples(B)[i] for i in range(min(B.nrows, 32))]
    with metrics.timed("enumeration"):
        gso = GSO.Mat(B)
        gso.update_gso()
        first_bound = sum(int(B[0, j]) ** 2 for j in range(B.ncols))
        bound = float(max(first_bound, radius_squared or 0))
        try:
            solutions = Enumeration(gso, nr_solutions=limit,
                                    strategy=EvaluatorStrategy.BEST_N_SOLUTIONS).enumerate(
                                        0, B.nrows, bound, 0)[:limit]
        except EnumerationError:
            solutions = []
        metrics.counters["enumeration_candidates"] = len(solutions)
        for _distance, coefficients in solutions:
            vector = tuple(sum(int(round(coefficients[i])) * int(B[i, j]) for i in range(B.nrows))
                           for j in range(B.ncols))
            vectors.append(vector)
    return vectors


def _secret_from_vector(instance: MLWEInstance, vector: tuple[int, ...]) -> RecoveredSecret | None:
    variables = (instance.l + instance.k) * instance.n
    equations = instance.k * instance.n
    if len(vector) != variables + equations + 1 or vector[-1] not in (-1, 1):
        return None
    if any(vector[variables:variables + equations]):
        return None
    flat = tuple(-vector[-1] * value for value in vector[:variables])
    if any(abs(value) > instance.eta for value in flat):
        return None
    s1 = tuple(flat[i:i + instance.n] for i in range(0, instance.l * instance.n, instance.n))
    offset = instance.l * instance.n
    s2 = tuple(flat[i:i + instance.n] for i in range(offset, variables, instance.n))
    return RecoveredSecret(s1, s2)


def solve_mlwe_primal(instance: MLWEInstance, strategy: str, params: dict[str, Any], metrics: Instrumentation):
    dimension = (instance.l + instance.k) * instance.n
    if dimension > int(params.get("max_basis_dimension", 128)):
        metrics.counters["dimension_cap_exceeded"] = dimension
        return None
    with metrics.timed("surrounding"):
        basis = mlwe_primal_basis(instance)
    B, _ = _reduce(basis, strategy, params, metrics)
    _, _, _, _, _, _, _ = _fpylll()
    from fpylll import CVP
    variables = instance.l * instance.n
    target_flat = tuple(x for poly in instance.t for x in poly)
    target = (0,) * variables + target_flat
    with metrics.timed("enumeration"):
        closest = tuple(int(x) for x in CVP.closest_vector(B, target, method=str(params.get("cvp_method", "fast"))))
        metrics.counters["enumeration_candidates"] = 1
    with metrics.timed("surrounding"):
        s1_flat = closest[:variables]
        s2_flat = tuple((target_flat[i] - closest[variables + i]) % instance.q for i in range(len(target_flat)))
        s2_flat = tuple(x - instance.q if x > instance.q // 2 else x for x in s2_flat)
        if any(abs(x) > instance.eta for x in s1_flat + s2_flat):
            return None
        return RecoveredSecret(
            tuple(s1_flat[i:i + instance.n] for i in range(0, variables, instance.n)),
            tuple(s2_flat[i:i + instance.n] for i in range(0, len(s2_flat), instance.n)),
        )


def solve_mlwe_exhaustive(instance: MLWEInstance, params: dict[str, Any], metrics: Instrumentation):
    unknowns = (instance.l + instance.k) * instance.n
    cap = int(params.get("max_unknowns", 12))
    if unknowns > cap:
        metrics.counters["search_space_skipped"] = (2 * instance.eta + 1) ** unknowns
        return None
    H = coefficient_matrix(instance)
    rows = instance.k * instance.n
    H = tuple(tuple(row) + tuple(int(i == j) for j in range(rows)) for i, row in enumerate(H))
    target = tuple(x for poly in instance.t for x in poly)
    with metrics.timed("enumeration"):
        for index, values in enumerate(itertools.product(range(-instance.eta, instance.eta + 1), repeat=unknowns), 1):
            if all(sum(H[row][col] * values[col] for col in range(unknowns)) % instance.q == target[row]
                   for row in range(rows)):
                metrics.counters["exhaustive_candidates"] = index
                s1_end = instance.l * instance.n
                return RecoveredSecret(
                    tuple(values[i:i + instance.n] for i in range(0, s1_end, instance.n)),
                    tuple(values[i:i + instance.n] for i in range(s1_end, unknowns, instance.n)),
                )
        metrics.counters["exhaustive_candidates"] = index
    return None


def _generic_primal_basis(H, q):
    equations = len(H)
    variables = len(H[0])
    dimension = variables + equations
    basis = []
    for col in range(variables):
        row = [0] * dimension
        row[col] = 1
        for eq in range(equations):
            row[variables + eq] = H[eq][col]
        basis.append(row)
    for eq in range(equations):
        row = [0] * dimension
        row[variables + eq] = q
        basis.append(row)
    return tuple(tuple(row) for row in basis)


def solve_mlwe_hybrid(instance: MLWEInstance, params: dict[str, Any], metrics: Instrumentation):
    """Guess a coefficient prefix, then reduce the residual BDD embedding."""
    M = coefficient_matrix(instance)
    equations = instance.k * instance.n
    full_H = M
    dimension = len(full_H[0]) - min(int(params.get("guess_coefficients", 1)), len(full_H[0]) - 1) + equations
    if dimension > int(params.get("max_basis_dimension", 64)):
        metrics.counters["dimension_cap_exceeded"] = dimension
        return None
    target = tuple(x for poly in instance.t for x in poly)
    guessed = min(int(params.get("guess_coefficients", 1)), len(full_H[0]) - 1)
    guess_values = (0,) + tuple(x for magnitude in range(1, instance.eta + 1) for x in (-magnitude, magnitude))
    for guess in itertools.product(guess_values, repeat=guessed):
        residual = tuple((target[r] - sum(full_H[r][c] * guess[c] for c in range(guessed))) % instance.q
                         for r in range(equations))
        reduced_H = tuple(row[guessed:] for row in full_H)
        basis = _generic_primal_basis(reduced_H, instance.q)
        B, _ = _reduce(basis, "bkz", params, metrics)
        from fpylll import CVP
        variables = len(full_H[0]) - guessed
        with metrics.timed("enumeration"):
            closest = tuple(int(x) for x in CVP.closest_vector(
                B, (0,) * variables + residual, method=str(params.get("cvp_method", "fast"))))
            metrics.counters["enumeration_candidates"] = metrics.counters.get("enumeration_candidates", 0) + 1
        remainder = closest[:variables]
        s1_flat = guess + remainder
        error = tuple((residual[i] - closest[variables + i]) % instance.q for i in range(equations))
        error = tuple(x - instance.q if x > instance.q // 2 else x for x in error)
        if any(abs(x) > instance.eta for x in s1_flat + error):
            continue
        split = instance.l * instance.n
        return RecoveredSecret(tuple(s1_flat[i:i + instance.n] for i in range(0, split, instance.n)),
                               tuple(error[i:i + instance.n] for i in range(0, len(error), instance.n)))
    return None


def _relation_from_vector(instance: MSISInstance, vector: tuple[int, ...]) -> ShortRelation | None:
    variables = instance.columns * instance.n
    if len(vector) != variables + instance.rows * instance.n or any(vector[variables:]) or not any(vector[:variables]):
        return None
    flat = vector[:variables]
    return ShortRelation(tuple(flat[i:i + instance.n] for i in range(0, variables, instance.n)))


def solve_msis(instance: MSISInstance, strategy: str, params: dict[str, Any], metrics: Instrumentation):
    basis = msis_embedding(instance)
    if len(basis) > int(params.get("max_basis_dimension", 160)):
        metrics.counters["dimension_cap_exceeded"] = len(basis)
        return None
    attempts = int(params.get("restarts", 1))
    rng = random.Random(f"{instance.instance_id}:{strategy}:{attempts}")
    best = None
    for attempt in range(attempts):
        working = [list(row) for row in basis]
        if attempt:
            # Deterministic unimodular row mixing gives each restart a distinct basis.
            for _ in range(min(2 * len(working), 128)):
                i, j = rng.sample(range(len(working)), 2)
                sign = rng.choice((-1, 1))
                working[i] = [x + sign * y for x, y in zip(working[i], working[j], strict=True)]
        B, _ = _reduce(tuple(tuple(row) for row in working), strategy, params, metrics)
        for vector in _enumerated_vectors(B, metrics, int(params.get("enumeration_limit", 16)),
                                          instance.target_norm_squared):
            candidate = _relation_from_vector(instance, vector)
            if candidate is not None:
                norm = sum(x * x for poly in candidate.z for x in poly)
                if best is None or norm < best[0]:
                    best = (norm, candidate)
    return None if best is None else best[1]


def solve_bkz(instance: BKZInstance, strategy: str, params: dict[str, Any], metrics: Instrumentation):
    if len(instance.basis) > int(params.get("max_basis_dimension", 160)):
        metrics.counters["dimension_cap_exceeded"] = len(instance.basis)
        return None
    B, U = _reduce(instance.basis, strategy, params, metrics)
    return ReducedBasis(_tuples(B), _tuples(U))


SOLVERS = {
    "mlwe": {
        "exhaustive": lambda i, p, m: solve_mlwe_exhaustive(i, p, m),
        "primal-lll": lambda i, p, m: solve_mlwe_primal(i, "lll", p, m),
        "primal-bkz": lambda i, p, m: solve_mlwe_primal(i, "bkz", p, m),
        "hybrid-bdd": solve_mlwe_hybrid,
    },
    "msis": {
        "lll-short-vector": lambda i, p, m: solve_msis(i, "lll", p, m),
        "progressive-bkz": lambda i, p, m: solve_msis(i, "progressive", p, m),
        "restart-bkz": lambda i, p, m: solve_msis(i, "bkz", {**p, "restarts": p.get("restarts", 3)}, m),
    },
    "bkz": {
        "lll-only": lambda i, p, m: solve_bkz(i, "lll", p, m),
        "fixed-bkz": lambda i, p, m: solve_bkz(i, "bkz", p, m),
        "progressive-bkz": lambda i, p, m: solve_bkz(i, "progressive", p, m),
    },
}


DEFAULT_PARAMETERS = {
    "exhaustive": {"max_unknowns": 12},
    "primal-lll": {"delta": 0.99, "cvp_method": "fast", "max_basis_dimension": 128},
    "primal-bkz": {"block_size": 12, "max_loops": 2, "cvp_method": "fast", "max_basis_dimension": 128},
    "hybrid-bdd": {"guess_coefficients": 1, "block_size": 12, "max_loops": 1, "cvp_method": "fast",
                   "max_basis_dimension": 64},
    "lll-short-vector": {"delta": 0.99, "enumeration_limit": 16, "max_basis_dimension": 160},
    "progressive-bkz": {"schedule": [5, 10, 15], "enumeration_limit": 16, "max_basis_dimension": 160},
    "restart-bkz": {"block_size": 12, "max_loops": 1, "restarts": 3, "enumeration_limit": 8,
                    "max_basis_dimension": 160},
    "lll-only": {"delta": 0.99, "max_basis_dimension": 160},
    "fixed-bkz": {"block_size": 12, "max_loops": 2, "max_basis_dimension": 160},
}


def run_solver(track: str, solver: str, instance, parameters: dict[str, Any] | None = None):
    if track not in SOLVERS or solver not in SOLVERS[track]:
        raise ValueError(f"unknown solver {solver!r} for track {track!r}")
    params = dict(DEFAULT_PARAMETERS.get(solver, {}))
    if parameters:
        params.update(parameters)
    metrics = Instrumentation({}, {"fplll_backend": "fpylll"})
    candidate = SOLVERS[track][solver](instance, params, metrics)
    return candidate, params, metrics
