"""Matrix helpers used by the synthetic modular-lattice challenge."""

from __future__ import annotations
from collections.abc import Sequence
from typing import Optional, Any
from .modular import inverse_mod


def _validate_square(matrix: Sequence[Sequence[int]]) -> int:
    if not matrix:
        raise ValueError("matrix must not be empty")
    size = len(matrix)
    if any(len(row) != size for row in matrix):
        raise ValueError("matrix must be square")
    return size


def mat_vec_mul(
    matrix: Sequence[Sequence[int]], vector: Sequence[int], modulus: int
) -> tuple[int, ...]:
    """Multiply a rectangular matrix by a vector modulo ``modulus``."""
    if modulus <= 1:
        raise ValueError("modulus must be greater than one")
    if any(len(row) != len(vector) for row in matrix):
        raise ValueError("matrix and vector dimensions do not match")
    return tuple(sum(entry * value for entry, value in zip(row, vector)) % modulus for row in matrix)


def solve_linear_system(
    matrix: Sequence[Sequence[int]], target: Sequence[int], modulus: int
) -> tuple[int, ...]:
    """Solve ``matrix * x = target (mod modulus)`` using elimination.

    The benchmark moduli are prime. A missing pivot therefore means the
    matrix is singular for the configured field.
    """
    size = _validate_square(matrix)
    if len(target) != size:
        raise ValueError("matrix and target dimensions do not match")
    augmented = [
        [entry % modulus for entry in row] + [target[index] % modulus]
        for index, row in enumerate(matrix)
    ]
    for column in range(size):
        pivot = next((row for row in range(column, size) if augmented[row][column]), None)
        if pivot is None:
            raise ValueError("matrix is singular modulo the configured modulus")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = inverse_mod(augmented[column][column], modulus)
        augmented[column] = [(value * scale) % modulus for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    (value - factor * pivot_value) % modulus
                    for value, pivot_value in zip(augmented[row], augmented[column])
                ]
    return tuple(row[-1] for row in augmented)


def is_invertible(matrix: Sequence[Sequence[int]], modulus: int) -> bool:
    """Return whether a square matrix is invertible modulo ``modulus``."""
    try:
        size = _validate_square(matrix)
        solve_linear_system(matrix, (0,) * size, modulus)
    except (TypeError, ValueError):
        return False
    return True


def _dot(a: Sequence[int], b: Sequence[int]) -> int:
    """Compute dot product of two vectors."""
    s = 0
    for x, y in zip(a, b):
        s += x * y
    return s


def _norm_sq(v: Sequence[int]) -> int:
    """Compute squared Euclidean norm of a vector."""
    s = 0
    for x in v:
        s += x * x
    return s


def schnorr_euchner_enum(
    basis: Sequence[Sequence[int]],
    target_norm_sq: int,
    max_depth: int = 100000,
    cost: Optional[Any] = None,
) -> Optional[tuple[int, ...]]:
    """Schnorr-Euchner enumeration to find a short vector in a reduced lattice.

    Given a reduced basis (typically LLL-reduced), enumerate lattice vectors
    within the given norm bound using the Schnorr-Euchner tree search.

    The algorithm:
    1. Compute Gram-Schmidt orthogonalization of the reduced basis.
    2. Enumerate coefficient combinations c_0, c_1, ..., c_{n-1} such that
       the resulting vector v = sum c_i * b_i has |v|^2 <= target_norm_sq.
    3. Use the GS coefficients to bound each coefficient at each level.
    4. Search in SE order: start from the center (best integer guess) and
       expand outward.

    Args:
        basis: Reduced lattice basis (list of vectors).
        target_norm_sq: Maximum squared norm for the search.
        max_depth: Maximum number of enumeration nodes to visit.
        cost: Optional OperationMeter for instrumentation.

    Returns:
        The shortest vector found (as a tuple of ints), or None if no vector
        within the norm bound was found.
    """
    n = len(basis)
    if n == 0:
        return None
    m = len(basis[0])

    # Compute Gram-Schmidt orthogonalization
    if cost is not None:
        cost.memory_reads(n * m)

    # Build GS vectors and mu coefficients incrementally
    B_star: list[list[int]] = []
    mu: list[list[float]] = []

    for i in range(n):
        bi = list(basis[i])
        bi_star = bi[:]
        mu_i: list[float] = [0.0] * i

        for j in range(i):
            denom = float(_norm_sq(B_star[j]))
            if denom == 0.0:
                continue
            num = float(_dot(basis[i], B_star[j]))
            mu_ij = num / denom
            mu_i[j] = mu_ij
            if abs(mu_ij) > 0.5:
                r = round(mu_ij)
                for k in range(m):
                    bi_star[k] -= r * B_star[j][k]

        B_star.append(bi_star)
        mu.append(mu_i)

    # Precompute GS norms
    gs_norms_sq = [_norm_sq(bs) for bs in B_star]

    best_vec: Optional[list[int]] = None
    best_norm_sq = target_norm_sq + 1
    nodes_visited = 0

    # Working array for coefficients (indexed 0..n-1)
    c: list[int] = [0] * n

    def search_level(k: int, budget_remaining: int) -> None:
        """Enumerate coefficient c_k and recurse to level k-1.

        At entry to level k, we have already fixed c_{k+1}, ..., c_{n-1}.
        The partial lattice vector from those higher levels is:
            partial_high = sum_{j=k+1}^{n-1} c_j * b_j
        We need to choose c_k, ..., c_0 to complete the vector within budget.
        """
        nonlocal best_vec, best_norm_sq, nodes_visited

        if nodes_visited >= max_depth:
            return

        nodes_visited += 1

        if k < 0:
            # All coefficients chosen: reconstruct the lattice vector
            vec = [0] * m
            for i in range(n):
                if c[i] != 0:
                    for j in range(m):
                        vec[j] += c[i] * basis[i][j]

            vec_norm_sq = _norm_sq(vec)
            if vec_norm_sq < best_norm_sq:
                best_norm_sq = vec_norm_sq
                best_vec = vec[:]
            return

        # Compute the offset for the GS coefficient at level k
        # coeff_k = c_k + sum_{j=k+1}^{n-1} mu[j][k] * c_j
        offset = 0.0
        for j in range(k + 1, n):
            offset += mu[j][k] * c[j]

        # Compute partial norm from levels > k
        partial = [0] * m
        for j in range(k + 1, n):
            if c[j] != 0:
                for idx in range(m):
                    partial[idx] += c[j] * basis[j][idx]
        partial_norm_sq = _norm_sq(partial)

        if partial_norm_sq > budget_remaining:
            return

        remaining = budget_remaining - partial_norm_sq

        # Determine search range for c_k
        if gs_norms_sq[k] == 0:
            c_vals = [0]
        else:
            # |c_k + offset|^2 * gs_norms_sq[k] <= remaining (approximately)
            # We can tolerate some slack because lower levels can help cancel
            max_offset = int((remaining / gs_norms_sq[k]) ** 0.5) + 2

            center = round(-offset)
            c_vals = []
            for d in range(max_offset + 1):
                if d == 0:
                    c_vals.append(center)
                else:
                    c_vals.append(center + d)
                    c_vals.append(center - d)

        for c_k in c_vals:
            c[k] = c_k

            # Compute actual new partial vector with this coefficient
            new_partial = partial[:]
            for idx in range(m):
                new_partial[idx] += c_k * basis[k][idx]
            new_partial_norm = _norm_sq(new_partial)

            if new_partial_norm > budget_remaining:
                continue

            # Also check GS-based bound for tighter pruning
            gs_coeff = c_k + offset
            gs_contribution = gs_coeff * gs_coeff * gs_norms_sq[k]
            if gs_contribution > remaining + 100:  # small tolerance
                # Can't prune here because lower levels might cancel via GS
                pass

            search_level(k - 1, budget_remaining)

            if nodes_visited >= max_depth:
                return

    search_level(n - 1, target_norm_sq)

    if best_vec is not None:
        return tuple(best_vec)
    return None


def schnorr_euchner_enum_last_coord(
    basis: Sequence[Sequence[int]],
    target_norm_sq: int,
    target_last_coord: int = 1,
    max_depth: int = 100000,
    cost: Optional[Any] = None,
    max_basis_vectors: Optional[int] = None,
) -> Optional[tuple[int, ...]]:
    """Schnorr-Euchner enumeration focused on vectors with a specific last coordinate.

    This is a specialized version of SE enumeration that only considers lattice
    vectors whose last coordinate equals target_last_coord (typically ±1).

    The algorithm works by:
    1. Computing the contribution of each basis vector to the last coordinate.
    2. During enumeration, tracking the accumulated last coordinate.
    3. Pruning branches that can't achieve the target last coordinate.

    Args:
        basis: Reduced lattice basis (list of vectors).
        target_norm_sq: Maximum squared norm for the search.
        target_last_coord: The desired value of the last coordinate (default 1).
        max_depth: Maximum number of enumeration nodes to visit.
        cost: Optional OperationMeter for instrumentation.
        max_basis_vectors: Maximum number of basis vectors to enumerate (sorted by norm).
            If None, uses all basis vectors. Use a small number to focus on short vectors.

    Returns:
        A lattice vector (as tuple) with the target last coordinate, or None.
    """
    n = len(basis)
    if n == 0:
        return None
    m = len(basis[0])

    # Optionally limit to the shortest basis vectors
    if max_basis_vectors is not None and max_basis_vectors < n:
        # Sort basis vectors by norm and take the shortest ones
        indexed = sorted(enumerate(basis), key=lambda p: _norm_sq(p[1]))
        short_indices = [idx for idx, _ in indexed[:max_basis_vectors]]
        basis = [basis[i] for i in short_indices]
        n = len(basis)
        if n == 0:
            return None

    # Extract last coordinates of each basis vector
    last_coords = [basis[i][m - 1] for i in range(n)]

    # Compute Gram-Schmidt orthogonalization
    if cost is not None:
        cost.memory_reads(n * m)

    B_star: list[list[int]] = []
    mu: list[list[float]] = []

    for i in range(n):
        bi = list(basis[i])
        bi_star = bi[:]
        mu_i: list[float] = [0.0] * i

        for j in range(i):
            denom = float(_norm_sq(B_star[j]))
            if denom == 0.0:
                continue
            num = float(_dot(basis[i], B_star[j]))
            mu_ij = num / denom
            mu_i[j] = mu_ij
            if abs(mu_ij) > 0.5:
                r = round(mu_ij)
                for idx in range(m):
                    bi_star[idx] -= r * B_star[j][idx]

        B_star.append(bi_star)
        mu.append(mu_i)

    # Precompute GS norms
    gs_norms_sq = [_norm_sq(bs) for bs in B_star]

    best_vec: Optional[list[int]] = None
    best_norm_sq = target_norm_sq + 1
    nodes_visited = 0

    # Working array for coefficients
    c: list[int] = [0] * n

    def search_level(k: int, budget_remaining: int, last_coord_acc: int) -> None:
        """Enumerate coefficient c_k with last-coordinate tracking."""
        nonlocal best_vec, best_norm_sq, nodes_visited

        if nodes_visited >= max_depth:
            return

        nodes_visited += 1

        if k < 0:
            # All coefficients chosen: check last coordinate
            if last_coord_acc != target_last_coord:
                return

            # Reconstruct the lattice vector
            vec = [0] * m
            for i in range(n):
                if c[i] != 0:
                    for j in range(m):
                        vec[j] += c[i] * basis[i][j]

            vec_norm_sq = _norm_sq(vec)
            if vec_norm_sq < best_norm_sq:
                best_norm_sq = vec_norm_sq
                best_vec = vec[:]
            return

        # Compute the offset for the GS coefficient at level k
        offset = 0.0
        for j in range(k + 1, n):
            offset += mu[j][k] * c[j]

        # Compute partial vector and norm from levels > k
        partial = [0] * m
        for j in range(k + 1, n):
            if c[j] != 0:
                for idx in range(m):
                    partial[idx] += c[j] * basis[j][idx]
        partial_norm_sq = _norm_sq(partial)

        if partial_norm_sq > budget_remaining:
            return

        # Check if we can still achieve the target last coordinate
        # The remaining last coordinate contribution is:
        #   sum_{i=0}^{k} c_i * last_coords[i]
        # We need: last_coord_acc + sum_{i=0}^{k} c_i * last_coords[i] = target_last_coord
        # So: sum_{i=0}^{k} c_i * last_coords[i] = target_last_coord - last_coord_acc
        needed_last = target_last_coord - last_coord_acc

        # Compute the maximum possible last coordinate contribution from levels 0..k
        max_last_contrib = 0
        for i in range(k + 1):
            if last_coords[i] != 0:
                # Estimate max coefficient based on norm budget
                if gs_norms_sq[i] > 0:
                    max_c = int((budget_remaining / gs_norms_sq[i]) ** 0.5) + 2
                    max_last_contrib += abs(max_c * last_coords[i])

        if abs(needed_last) > max_last_contrib:
            return  # Can't achieve target last coordinate

        remaining = budget_remaining - partial_norm_sq

        # Determine search range for c_k
        if gs_norms_sq[k] == 0:
            c_vals = [0]
        else:
            max_offset = int((remaining / gs_norms_sq[k]) ** 0.5) + 2
            center = round(-offset)
            c_vals = []
            for d in range(max_offset + 1):
                if d == 0:
                    c_vals.append(center)
                else:
                    c_vals.append(center + d)
                    c_vals.append(center - d)

        for c_k in c_vals:
            c[k] = c_k

            # Compute new partial vector
            new_partial = partial[:]
            for idx in range(m):
                new_partial[idx] += c_k * basis[k][idx]
            new_partial_norm = _norm_sq(new_partial)

            if new_partial_norm > budget_remaining:
                continue

            # Update last coordinate accumulator
            new_last_acc = last_coord_acc + c_k * last_coords[k]

            # Check if we can still achieve target
            remaining_needed = target_last_coord - new_last_acc
            remaining_max_contrib = 0
            for i in range(k):
                if last_coords[i] != 0 and gs_norms_sq[i] > 0:
                    max_c = int((remaining / gs_norms_sq[i]) ** 0.5) + 2
                    remaining_max_contrib += abs(max_c * last_coords[i])

            if abs(remaining_needed) > remaining_max_contrib:
                continue

            search_level(k - 1, budget_remaining, new_last_acc)

            if nodes_visited >= max_depth:
                return

    search_level(n - 1, target_norm_sq, 0)

    if best_vec is not None:
        return tuple(best_vec)
    return None