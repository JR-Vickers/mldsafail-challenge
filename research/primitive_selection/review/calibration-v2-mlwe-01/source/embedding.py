"""Canonical integer embeddings derived only from study instances."""

from __future__ import annotations

from .models import BKZInstance, MLWEInstance, MSISInstance, digest
from .ring import convolution_matrix


def coefficient_matrix(instance: MLWEInstance | MSISInstance) -> tuple[tuple[int, ...], ...]:
    rows = instance.k if isinstance(instance, MLWEInstance) else instance.rows
    columns = instance.l if isinstance(instance, MLWEInstance) else instance.columns
    n = instance.n
    result = [[0] * (columns * n) for _ in range(rows * n)]
    for i in range(rows):
        for j in range(columns):
            block = convolution_matrix(instance.A[i][j], instance.q)
            for u in range(n):
                for v in range(n):
                    result[i * n + u][j * n + v] = block[u][v]
    return tuple(tuple(row) for row in result)


def mlwe_embedding(instance: MLWEInstance) -> tuple[tuple[int, ...], ...]:
    """Kannan embedding containing (-s1,-s2,0,1) for every solution."""
    instance.validate()
    M = coefficient_matrix(instance)
    equations = instance.k * instance.n
    variables = (instance.l + instance.k) * instance.n
    H = [list(row) + [1 if i == j else 0 for j in range(equations)] for i, row in enumerate(M)]
    dimension = variables + equations + 1
    basis = []
    for col in range(variables):
        row = [0] * dimension
        row[col] = 1
        for eq in range(equations):
            row[variables + eq] = H[eq][col]
        basis.append(row)
    for eq in range(equations):
        row = [0] * dimension
        row[variables + eq] = instance.q
        basis.append(row)
    row = [0] * dimension
    target = tuple(x for poly in instance.t for x in poly)
    row[variables:variables + equations] = target
    row[-1] = 1
    basis.append(row)
    return tuple(tuple(row) for row in basis)


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


def msis_embedding(instance: MSISInstance) -> tuple[tuple[int, ...], ...]:
    """q-ary relation lattice containing (z,0) when A*z = 0 mod q."""
    instance.validate()
    H = coefficient_matrix(instance)
    equations = instance.rows * instance.n
    variables = instance.columns * instance.n
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
        row[variables + eq] = instance.q
        basis.append(row)
    return tuple(tuple(row) for row in basis)


def derive_bkz(instance: MLWEInstance | MSISInstance) -> BKZInstance:
    basis = mlwe_embedding(instance) if isinstance(instance, MLWEInstance) else msis_embedding(instance)
    draft = BKZInstance(instance.profile, instance.track, instance.instance_id, basis)
    result = BKZInstance(instance.profile, instance.track, instance.instance_id,
                         basis, digest(draft.payload()))
    result.validate()
    return result
