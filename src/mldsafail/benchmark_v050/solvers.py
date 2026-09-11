"""Frozen MLWE reference and example algorithms; no evaluator imports."""
from __future__ import annotations
import itertools
import time
from dataclasses import dataclass
from typing import Any
from .embedding import coefficient_matrix, mlwe_primal_basis
from .models import MLWEInstance, RecoveredSecret

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


def solve_mlwe_primal(instance: MLWEInstance, strategy: str, params: dict[str, Any], metrics: Instrumentation):
    dimension = (instance.l + instance.k) * instance.n
    if dimension > int(params.get("max_basis_dimension", 128)):
        metrics.counters["dimension_cap_exceeded"] = dimension
        return None
    if instance.eta == 2 and dimension > int(params.get("max_eta2_basis_dimension", 64)):
        metrics.counters["difficulty_cap_exceeded"] = f"eta=2,dimension={dimension}"
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
    """Enumerate bounded s1; the public equation uniquely determines s2."""
    unknowns = instance.l * instance.n
    search_space = (2 * instance.eta + 1) ** unknowns
    cap = int(params.get("max_candidates", 1_000_000))
    if search_space > cap:
        metrics.counters["search_space_skipped"] = search_space
        return None
    H = coefficient_matrix(instance)
    rows = instance.k * instance.n
    target = tuple(x for poly in instance.t for x in poly)
    with metrics.timed("enumeration"):
        for index, values in enumerate(itertools.product(range(-instance.eta, instance.eta + 1), repeat=unknowns), 1):
            error = []
            for row in range(rows):
                residue = (target[row] - sum(H[row][col] * values[col] for col in range(unknowns))) % instance.q
                centered = residue - instance.q if residue > instance.q // 2 else residue
                if abs(centered) > instance.eta:
                    break
                error.append(centered)
            if len(error) == rows:
                metrics.counters["exhaustive_candidates"] = index
                return RecoveredSecret(
                    tuple(values[i:i + instance.n] for i in range(0, unknowns, instance.n)),
                    tuple(tuple(error[i:i + instance.n]) for i in range(0, rows, instance.n)),
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
    """Guess a bounded coefficient prefix, then use approximate Babai decoding.

    The lattice is independent of the guess and is reduced exactly once. Unlike
    primal CVP this approach uses no closest-vector enumeration; the returned
    approximate answer must still pass the same complete relation verifier.
    """
    M = coefficient_matrix(instance)
    equations = instance.k * instance.n
    full_H = M
    dimension = len(full_H[0]) - min(int(params.get("guess_coefficients", 1)), len(full_H[0]) - 1) + equations
    if dimension > int(params.get("max_basis_dimension", 128)):
        metrics.counters["dimension_cap_exceeded"] = dimension
        return None
    target = tuple(x for poly in instance.t for x in poly)
    guessed = min(int(params.get("guess_coefficients", 1)), len(full_H[0]) - 1)
    guess_values = (0,) + tuple(x for magnitude in range(1, instance.eta + 1) for x in (-magnitude, magnitude))
    with metrics.timed("surrounding"):
        reduced_H = tuple(row[guessed:] for row in full_H)
        basis = _generic_primal_basis(reduced_H, instance.q)
    B, _ = _reduce(basis, "bkz", params, metrics)
    _, GSO, _, _, _, _, _ = _fpylll()
    with metrics.timed("decoding"):
        gso = GSO.Mat(B)
        gso.update_gso()
    for guess in itertools.product(guess_values, repeat=guessed):
        residual = tuple((target[r] - sum(full_H[r][c] * guess[c] for c in range(guessed))) % instance.q
                         for r in range(equations))
        variables = len(full_H[0]) - guessed
        with metrics.timed("decoding"):
            coefficients = gso.babai((0,) * variables + residual)
            closest = tuple(sum(int(coefficients[i]) * int(B[i, j]) for i in range(B.nrows))
                            for j in range(B.ncols))
            metrics.counters["babai_candidates"] = metrics.counters.get("babai_candidates", 0) + 1
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

DEFAULT_PARAMETERS = {'primal-lll': {'delta': 0.99, 'cvp_method': 'fast', 'max_basis_dimension': 128, 'max_eta2_basis_dimension': 64}, 'hybrid-bdd': {'guess_coefficients': 1, 'block_size': 12, 'max_loops': 1, 'decoder': 'babai', 'max_basis_dimension': 128}, 'exhaustive': {'max_candidates': 1000000}, 'direct-linear': {'max_candidates': 1000000}}

def run_solver(name, instance):
    params = dict(DEFAULT_PARAMETERS[name])
    metrics = Instrumentation({}, {"solver_backend": "python" if name in ("exhaustive", "direct-linear") else "fpylll"})
    if name == "primal-lll":
        candidate = solve_mlwe_primal(instance, "lll", params, metrics)
    elif name == "hybrid-bdd":
        candidate = solve_mlwe_hybrid(instance, params, metrics)
    elif name == "exhaustive":
        candidate = solve_mlwe_exhaustive(instance, params, metrics)
    else:
        from .simple_baselines import solve_mlwe_direct
        with metrics.timed("linear_solving"):
            candidate, counters = solve_mlwe_direct(instance)
            if candidate is not None and any(abs(x) > instance.eta for poly in candidate.s1 + candidate.s2 for x in poly):
                candidate = None
                counters["algebraic_candidate_outside_bound"] = 1
        metrics.counters.update(counters)
    return candidate, params, metrics
