from __future__ import annotations
from .models import MLWEInstance
from .ring import convolution_matrix

def coefficient_matrix(instance: MLWEInstance) -> tuple[tuple[int, ...], ...]:
    rows = instance.k
    columns = instance.l
    n = instance.n
    result = [[0] * (columns * n) for _ in range(rows * n)]
    for i in range(rows):
        for j in range(columns):
            block = convolution_matrix(instance.A[i][j], instance.q)
            for u in range(n):
                for v in range(n):
                    result[i * n + u][j * n + v] = block[u][v]
    return tuple(tuple(row) for row in result)


def mlwe_primal_basis(instance: MLWEInstance) -> tuple[tuple[int, ...], ...]:
    """q-ary primal basis used for BDD/CVP secret recovery."""
    instance.validate()
    M = coefficient_matrix(instance)
    equations = instance.k * instance.n
    variables = instance.l * instance.n
    dimension = variables + equations
    basis = []
    for col in range(variables):
        row = [0] * dimension
        row[col] = 1
        for eq in range(equations):
            row[variables + eq] = M[eq][col]
        basis.append(row)
    for eq in range(equations):
        row = [0] * dimension
        row[variables + eq] = instance.q
        basis.append(row)
    return tuple(tuple(row) for row in basis)
