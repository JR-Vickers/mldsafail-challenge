"""Adversarial public-input baselines, included in the v2 comparison portfolio.

The standalone calibration command records attempted algebraic candidates;
the complete-solver adapters reject out-of-bound attempts as no-candidate.
These routines accept only bounded research instances. They do not import the
generator or inspect evaluator diagnostics. Their role is to detect an easy
algebraic formulation before giving credit to lattice reduction.
"""

from __future__ import annotations

import itertools

from .embedding import coefficient_matrix
from .models import MLWEInstance, MSISInstance, RecoveredSecret, ShortRelation


def affine_modular_solutions(matrix, target, q):
    """Return an RREF affine parameterization over the prime field Z/qZ.

    The returned pair is (constant, free-variable directions); None means the
    system is inconsistent. No boundedness assumption is used in elimination.
    """
    if not matrix or len(matrix) != len(target):
        raise ValueError("invalid linear-system dimensions")
    columns = len(matrix[0])
    if any(len(row) != columns for row in matrix):
        raise ValueError("ragged linear system")
    work = [[int(x) % q for x in row] + [int(t) % q] for row, t in zip(matrix, target, strict=True)]
    pivots = []
    for column in range(columns):
        pivot = next((r for r in range(len(pivots), len(work)) if work[r][column]), None)
        if pivot is None:
            continue
        row_index = len(pivots)
        work[row_index], work[pivot] = work[pivot], work[row_index]
        inverse = pow(work[row_index][column], -1, q)
        work[row_index] = [(x * inverse) % q for x in work[row_index]]
        for r in range(len(work)):
            if r != row_index and work[r][column]:
                multiplier = work[r][column]
                work[r] = [(x - multiplier * y) % q for x, y in zip(work[r], work[row_index], strict=True)]
        pivots.append(column)
        if len(pivots) == len(work):
            break
    if any(not any(row[:columns]) and row[-1] for row in work):
        return None
    constant = [0] * columns
    for r, column in enumerate(pivots):
        constant[column] = work[r][-1]
    directions = []
    for free in sorted(set(range(columns)) - set(pivots)):
        direction = [0] * columns
        direction[free] = 1
        for r, column in enumerate(pivots):
            direction[column] = -work[r][free] % q
        directions.append(tuple(direction))
    return tuple(constant), tuple(directions)


def _center(values, q):
    return tuple(x % q - q if x % q > q // 2 else x % q for x in values)


def solve_mlwe_direct(instance: MLWEInstance):
    """Solve [A | I](s1,s2)=t by modular elimination with free variables zero.

    This baseline deliberately ignores shortness during elimination; returning
    an algebraic answer does not imply that the bounded verifier accepts it.
    """
    instance.validate()
    matrix = coefficient_matrix(instance)
    equations = instance.k * instance.n
    augmented = tuple(row + tuple(int(i == j) for j in range(equations)) for i, row in enumerate(matrix))
    result = affine_modular_solutions(augmented, tuple(x for p in instance.t for x in p), instance.q)
    if result is None:
        return None, {"linear_system_inconsistent": 1}
    constant, directions = result
    flat = _center(constant, instance.q)
    variables = instance.l * instance.n
    candidate = RecoveredSecret(tuple(flat[i:i + instance.n] for i in range(0, variables, instance.n)),
                                tuple(flat[i:i + instance.n] for i in range(variables, len(flat), instance.n)))
    return candidate, {"linear_free_variables": len(directions)}


def solve_msis_direct(instance: MSISInstance, max_candidates: int = 1_000_000):
    """Exploit the documented last-polynomial-one planting using only A.

    Set the last relation polynomial to one, then solve the public square
    prefix. If singular, enumerate only its free coefficients in [-eta,eta].
    For an invertible prefix there is exactly one modular answer, and centered
    recovery gives the planted short relation without lattice reduction.
    """
    instance.validate()
    matrix = coefficient_matrix(instance)
    prefix = (instance.columns - 1) * instance.n
    target = tuple(-row[prefix] % instance.q for row in matrix)
    result = affine_modular_solutions(tuple(row[:prefix] for row in matrix), target, instance.q)
    if result is None:
        return None, {"linear_system_inconsistent": 1}
    constant, directions = result
    space = (2 * instance.eta + 1) ** len(directions)
    counters = {"linear_free_variables": len(directions), "bounded_free_search_space": space}
    if space > max_candidates:
        counters["search_space_skipped"] = space
        return None, counters
    for index, values in enumerate(itertools.product(range(-instance.eta, instance.eta + 1),
                                                     repeat=len(directions)), 1):
        flat = _center(tuple(constant[j] + sum(x * direction[j] for x, direction in
                                              zip(values, directions, strict=True)) for j in range(prefix)), instance.q)
        complete = flat + (1,) + (0,) * (instance.n - 1)
        if max(abs(x) for x in complete) <= instance.target_norm_infinity and (
                sum(x * x for x in complete) <= instance.target_norm_squared):
            counters["bounded_free_candidates"] = index
            return ShortRelation(tuple(complete[i:i + instance.n] for i in range(0, len(complete), instance.n))), counters
    counters["bounded_free_candidates"] = space
    return None, counters


def solve_msis_sparse(instance: MSISInstance):
    """Search every relation with one or two coefficients in {-1,+1}."""
    instance.validate()
    matrix = coefficient_matrix(instance)
    columns = tuple(tuple(row[j] % instance.q for row in matrix) for j in range(instance.columns * instance.n))
    seen = {}
    for j, column in enumerate(columns):
        if not any(column):
            support = ((j, 1),)
        elif column in seen:
            support = ((seen[column], 1), (j, -1))
        elif tuple(-x % instance.q for x in column) in seen:
            support = ((seen[tuple(-x % instance.q for x in column)], 1), (j, 1))
        else:
            seen[column] = j
            continue
        flat = [0] * len(columns)
        for index, value in support:
            flat[index] = value
        if sum(x * x for x in flat) <= instance.target_norm_squared:
            return ShortRelation(tuple(tuple(flat[i:i + instance.n]) for i in range(0, len(flat), instance.n))), {
                "sparse_columns_checked": j + 1}
    return None, {"sparse_columns_checked": len(columns)}


def main():
    """Fresh-process calibration boundary, sharing the research resource caps."""
    import json
    import sys
    import time

    from .models import instance_from_dict
    from .verify import verify_mlwe, verify_msis
    from .worker import _limits, _peak_rss_bytes

    limits = _limits()
    started = time.process_time()
    request = json.load(sys.stdin)
    instance = instance_from_dict(request["instance"])
    solver = request["solver"]
    if solver == "direct-linear" and isinstance(instance, MLWEInstance):
        candidate, counters = solve_mlwe_direct(instance)
    elif solver == "direct-linear" and isinstance(instance, MSISInstance):
        candidate, counters = solve_msis_direct(instance)
    elif solver == "sparse-relation" and isinstance(instance, MSISInstance):
        candidate, counters = solve_msis_sparse(instance)
    else:
        raise ValueError("unsupported simple baseline")
    verifier = verify_mlwe if isinstance(instance, MLWEInstance) else verify_msis
    verification = ({"verified": False, "failure_reason": "no candidate"} if candidate is None
                    else verifier(instance, candidate))
    json.dump({"candidate": None if candidate is None else candidate.to_dict(), "verification": verification,
               "diagnostic_counters": counters, "cpu_seconds": time.process_time() - started,
               "peak_rss_bytes": _peak_rss_bytes(), "limits": limits}, sys.stdout, sort_keys=True)


if __name__ == "__main__":
    main()
