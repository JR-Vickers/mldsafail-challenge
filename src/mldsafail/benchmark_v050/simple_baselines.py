from __future__ import annotations
from .embedding import coefficient_matrix
from .models import MLWEInstance, RecoveredSecret

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
