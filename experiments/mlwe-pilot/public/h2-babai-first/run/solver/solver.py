"""Primal LLL with bounded Babai decoding and exact CVP fallback."""
from fpylll import CVP, GSO, IntegerMatrix, LLL

from mldsafail.benchmark_v050.embedding import mlwe_primal_basis
from mldsafail.benchmark_v050.models import instance_from_dict


def solve(public_instance):
    instance = instance_from_dict(public_instance)
    dimension = (instance.l + instance.k) * instance.n
    if dimension > 128 or (instance.eta == 2 and dimension > 64):
        return None
    basis = IntegerMatrix.from_matrix(mlwe_primal_basis(instance))
    LLL.reduction(basis, delta=0.99)
    variables = instance.l * instance.n
    target_flat = tuple(x for poly in instance.t for x in poly)
    target = (0,) * variables + target_flat
    gso = GSO.Mat(basis)
    gso.update_gso()
    closest = tuple(int(x) for x in basis.multiply_left(gso.babai(target)))
    candidate = decode(instance, closest, variables, target_flat)
    if candidate is not None:
        return candidate
    closest = tuple(int(x) for x in CVP.closest_vector(basis, target, method="fast"))
    return decode(instance, closest, variables, target_flat)


def decode(instance, closest, variables, target_flat):
    s1 = closest[:variables]
    s2 = tuple((target_flat[i] - closest[variables + i]) % instance.q
               for i in range(len(target_flat)))
    s2 = tuple(x - instance.q if x > instance.q // 2 else x for x in s2)
    if any(abs(x) > instance.eta for x in s1 + s2):
        return None
    return {"tag": "recovered_secret",
            "s1": tuple(s1[i:i + instance.n] for i in range(0, variables, instance.n)),
            "s2": tuple(s2[i:i + instance.n] for i in range(0, len(s2), instance.n))}
