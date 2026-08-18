"""Candidate A: bounded short-vector recovery via Gaussian elimination.

Solves A * c == t (mod q) using forward elimination with partial pivoting,
back substitution, and coefficient centering to the range [-eta, eta].

The instance generator guarantees a square, invertible matrix over a prime
field, so the modular linear system has a unique solution.  Centering the
canonical residues into [-q//2, q//2] produces the unique bounded vector
since the planted solution satisfies |s_i| <= eta < q//2 for every profile.

Cost instrumentation follows the version-2 shared meter: all arithmetic,
modular reductions, and memory operations are counted locally and flushed
to the meter in a finally block.
"""

from __future__ import annotations

from mldsafail.benchmark.cost_model import OperationMeter
from mldsafail.models import Candidate, ChallengeInstance


# ---------------------------------------------------------------------------
# Solver core
# ---------------------------------------------------------------------------

class CandidateAError(RuntimeError):
    """Raised when Candidate A cannot recover a valid bounded vector."""


def solve(instance: ChallengeInstance, cost: OperationMeter) -> Candidate:
    """Recover c with |c_i| <= eta and A*c == t (mod q).

    Four stages:
        1. augment       — build augmented matrix [A | t]
        2. forward_elim  — Gaussian elimination to upper-triangular form
        3. back_subst    — back substitution to recover canonical residues
        4. center        — map residues from [0, q-1] to [-q//2, q//2]
    """
    n = instance.dimension
    q = instance.modulus

    if n <= 0 or q <= 2:
        raise CandidateAError("invalid instance dimensions or modulus")
    if len(instance.matrix) != n or len(instance.target) != n:
        raise CandidateAError("instance shape does not match its dimension")
    if any(len(row) != n for row in instance.matrix):
        raise CandidateAError("matrix must be square")

    # Local accumulators flushed to the shared meter in the finally block.
    adds = muls = mods = bus = mreads = mwrites = 0

    # Stage-level accumulators for diagnostics (also flushed to meter).
    s_adds = s_muls = s_mods = s_bus = s_mreads = s_mwrites = 0
    stage: dict[str, dict[str, int]] = {
        "augment": {"additions": 0, "multiplications": 0, "modular_reductions": 0,
                     "basis_updates": 0, "memory_reads": 0, "memory_writes": 0},
        "forward_elim": {"additions": 0, "multiplications": 0, "modular_reductions": 0,
                         "basis_updates": 0, "memory_reads": 0, "memory_writes": 0},
        "back_subst": {"additions": 0, "multiplications": 0, "modular_reductions": 0,
                       "basis_updates": 0, "memory_reads": 0, "memory_writes": 0},
        "center": {"additions": 0, "multiplications": 0, "modular_reductions": 0,
                   "basis_updates": 0, "memory_reads": 0, "memory_writes": 0},
    }

    def bump(stage_name: str, cat: str, n_amt: int = 1) -> None:
        """Count one operation in both the global and stage accumulators."""
        nonlocal adds, muls, mods, bus, mreads, mwrites
        amt = int(n_amt)
        if amt < 0:
            raise ValueError(f"negative count: {cat}")
        if cat == "additions":
            adds += amt
        elif cat == "multiplications":
            muls += amt
        elif cat == "modular_reductions":
            mods += amt
        elif cat == "basis_updates":
            bus += amt
        elif cat == "memory_reads":
            mreads += amt
        elif cat == "memory_writes":
            mwrites += amt
        else:
            raise ValueError(f"unknown category: {cat}")
        stage[stage_name][cat] += amt

    try:
        # -- Stage 1: augment -----------------------------------------------
        # Public entries are already canonical residues; copy directly.
        augmented: list[list[int]] = []
        for row, target in zip(instance.matrix, instance.target, strict=True):
            bump("augment", "memory_reads", n)        # read matrix row
            bump("augment", "memory_reads", 1)        # read target entry
            new_row = list(row) + [target]
            bump("augment", "memory_writes", n + 1)   # write augmented row
            augmented.append(new_row)

        # -- Stage 2: forward elimination -----------------------------------
        pivot_swaps = 0
        for col in range(n):
            # Partial pivoting: find first non-zero in column.
            pivot = col
            while pivot < n and augmented[pivot][col] == 0:
                pivot += 1
                bump("forward_elim", "memory_reads", 1)
            if pivot == n:
                raise CandidateAError(f"singular matrix at column {col}")
            if pivot != col:
                # Swap rows.
                bump("forward_elim", "memory_reads", 2 * (n + 1))
                bump("forward_elim", "memory_writes", 2 * (n + 1))
                augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
                bump("forward_elim", "basis_updates", 1)
                pivot_swaps += 1

            pivot_row = augmented[col]
            pivot_val = pivot_row[col]
            bump("forward_elim", "memory_reads", 1)

            # Modular inverse via pow (counts as one mul + one mod reduction).
            try:
                inv = pow(pivot_val, -1, q)
            except ValueError as exc:
                raise CandidateAError(f"non-invertible pivot at column {col}") from exc
            bump("forward_elim", "modular_reductions", 1)
            bump("forward_elim", "multiplications", 1)

            # Eliminate entries below pivot.
            trailing = n - col  # columns col..n (inclusive of target column)
            for row_idx in range(col + 1, n):
                row_vals = augmented[row_idx]
                factor = row_vals[col]
                bump("forward_elim", "memory_reads", 1)
                if factor == 0:
                    continue
                factor = (factor * inv) % q
                bump("forward_elim", "multiplications", 1)
                bump("forward_elim", "modular_reductions", 1)
                row_vals[col] = 0
                bump("forward_elim", "memory_writes", 1)
                for j in range(col + 1, n + 1):
                    row_vals[j] = (row_vals[j] - factor * pivot_row[j]) % q
                bump("forward_elim", "memory_reads", 2 * (trailing - 1))
                bump("forward_elim", "memory_writes", trailing - 1)
                bump("forward_elim", "multiplications", trailing - 1)
                bump("forward_elim", "additions", trailing - 1)
                bump("forward_elim", "modular_reductions", trailing - 1)
                bump("forward_elim", "basis_updates", 1)

        # -- Stage 3: back substitution -------------------------------------
        residues: list[int] = [0] * n
        bump("back_subst", "memory_writes", n)
        for row_idx in range(n - 1, -1, -1):
            row_vals = augmented[row_idx]
            remainder = row_vals[n]
            bump("back_subst", "memory_reads", 1)
            width = n - row_idx - 1
            for col in range(row_idx + 1, n):
                remainder -= row_vals[col] * residues[col]
            bump("back_subst", "memory_reads", 2 * width)
            bump("back_subst", "multiplications", width)
            bump("back_subst", "additions", width)
            pivot_val = row_vals[row_idx]
            bump("back_subst", "memory_reads", 1)
            try:
                inv = pow(pivot_val, -1, q)
            except ValueError as exc:
                raise CandidateAError(f"non-invertible pivot at row {row_idx}") from exc
            bump("back_subst", "modular_reductions", 1)
            bump("back_subst", "multiplications", 1)
            residues[row_idx] = (remainder * inv) % q
            bump("back_subst", "multiplications", 1)
            bump("back_subst", "modular_reductions", 1)
            bump("back_subst", "memory_writes", 1)

        # -- Stage 4: center coefficients -----------------------------------
        # Map canonical residues [0, q-1] to centered [-q//2, q//2].
        midpoint = q // 2
        coefficients = tuple(
            v - q if v > midpoint else v for v in residues
        )
        bump("center", "memory_reads", n)
        bump("center", "memory_writes", n)

        return Candidate(coefficients=coefficients)

    finally:
        # Flush all local counts to the shared version-2 meter.
        cost.additions(adds)
        cost.multiplications(muls)
        cost.modular_reductions(mods)
        cost.basis_updates(bus)
        cost.memory_reads(mreads)
        cost.memory_writes(mwrites)


# ---------------------------------------------------------------------------
# Stage-aware solver (for diagnostics only — same algorithm, separate meter)
# ---------------------------------------------------------------------------


def solve_with_stages(instance: ChallengeInstance) -> tuple[Candidate, dict[str, dict[str, int]], int]:
    """Run solve and return (candidate, stage_counts, pivot_swaps).

    Uses a fresh OperationMeter internally.  The returned stage_counts
    break down the shared cost vocabulary by solver stage.
    """
    meter = OperationMeter()
    # We cannot easily extract stage counts from solve() because it flushes
    # to the meter in finally.  Instead we re-implement the counting inline
    # here with stage tracking, or we run solve() and infer stages.
    #
    # Cleanest approach: re-run the same algorithm with stage-tagged counters.
    # This is deterministic and cheap.
    n = instance.dimension
    q = instance.modulus
    eta = instance.eta

    if n <= 0 or q <= 2:
        raise CandidateAError("invalid instance dimensions or modulus")
    if len(instance.matrix) != n or len(instance.target) != n:
        raise CandidateAError("instance shape does not match its dimension")
    if any(len(row) != n for row in instance.matrix):
        raise CandidateAError("matrix must be square")

    stage_counts: dict[str, dict[str, int]] = {
        "augment": {"additions": 0, "multiplications": 0, "modular_reductions": 0,
                     "basis_updates": 0, "memory_reads": 0, "memory_writes": 0},
        "forward_elim": {"additions": 0, "multiplications": 0, "modular_reductions": 0,
                         "basis_updates": 0, "memory_reads": 0, "memory_writes": 0},
        "back_subst": {"additions": 0, "multiplications": 0, "modular_reductions": 0,
                       "basis_updates": 0, "memory_reads": 0, "memory_writes": 0},
        "center": {"additions": 0, "multiplications": 0, "modular_reductions": 0,
                   "basis_updates": 0, "memory_reads": 0, "memory_writes": 0},
    }

    def bump(stage_name: str, cat: str, n_amt: int = 1) -> None:
        amt = int(n_amt)
        if amt < 0:
            raise ValueError(f"negative count: {cat}")
        stage_counts[stage_name][cat] += amt

    augmented: list[list[int]] = []
    for row, target in zip(instance.matrix, instance.target, strict=True):
        bump("augment", "memory_reads", n)
        bump("augment", "memory_reads", 1)
        new_row = list(row) + [target]
        bump("augment", "memory_writes", n + 1)
        augmented.append(new_row)

    pivot_swaps = 0
    for col in range(n):
        pivot = col
        while pivot < n and augmented[pivot][col] == 0:
            pivot += 1
            bump("forward_elim", "memory_reads", 1)
        if pivot == n:
            raise CandidateAError(f"singular matrix at column {col}")
        if pivot != col:
            bump("forward_elim", "memory_reads", 2 * (n + 1))
            bump("forward_elim", "memory_writes", 2 * (n + 1))
            augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
            bump("forward_elim", "basis_updates", 1)
            pivot_swaps += 1

        pivot_row = augmented[col]
        pivot_val = pivot_row[col]
        bump("forward_elim", "memory_reads", 1)
        inv = pow(pivot_val, -1, q)
        bump("forward_elim", "modular_reductions", 1)
        bump("forward_elim", "multiplications", 1)

        trailing = n - col
        for row_idx in range(col + 1, n):
            row_vals = augmented[row_idx]
            factor = row_vals[col]
            bump("forward_elim", "memory_reads", 1)
            if factor == 0:
                continue
            factor = (factor * inv) % q
            bump("forward_elim", "multiplications", 1)
            bump("forward_elim", "modular_reductions", 1)
            row_vals[col] = 0
            bump("forward_elim", "memory_writes", 1)
            for j in range(col + 1, n + 1):
                row_vals[j] = (row_vals[j] - factor * pivot_row[j]) % q
            bump("forward_elim", "memory_reads", 2 * (trailing - 1))
            bump("forward_elim", "memory_writes", trailing - 1)
            bump("forward_elim", "multiplications", trailing - 1)
            bump("forward_elim", "additions", trailing - 1)
            bump("forward_elim", "modular_reductions", trailing - 1)
            bump("forward_elim", "basis_updates", 1)

    residues: list[int] = [0] * n
    bump("back_subst", "memory_writes", n)
    for row_idx in range(n - 1, -1, -1):
        row_vals = augmented[row_idx]
        remainder = row_vals[n]
        bump("back_subst", "memory_reads", 1)
        width = n - row_idx - 1
        for col in range(row_idx + 1, n):
            remainder -= row_vals[col] * residues[col]
        bump("back_subst", "memory_reads", 2 * width)
        bump("back_subst", "multiplications", width)
        bump("back_subst", "additions", width)
        pivot_val = row_vals[row_idx]
        bump("back_subst", "memory_reads", 1)
        inv = pow(pivot_val, -1, q)
        bump("back_subst", "modular_reductions", 1)
        bump("back_subst", "multiplications", 1)
        residues[row_idx] = (remainder * inv) % q
        bump("back_subst", "multiplications", 1)
        bump("back_subst", "modular_reductions", 1)
        bump("back_subst", "memory_writes", 1)

    midpoint = q // 2
    coefficients = tuple(v - q if v > midpoint else v for v in residues)
    bump("center", "memory_reads", n)
    bump("center", "memory_writes", n)

    if meter is not None:
        # Flush to meter for consistency (though we don't use the meter result here).
        meter.additions(sum(stage_counts[s]["additions"] for s in stage_counts))
        meter.multiplications(sum(stage_counts[s]["multiplications"] for s in stage_counts))
        meter.modular_reductions(sum(stage_counts[s]["modular_reductions"] for s in stage_counts))
        meter.basis_updates(sum(stage_counts[s]["basis_updates"] for s in stage_counts))
        meter.memory_reads(sum(stage_counts[s]["memory_reads"] for s in stage_counts))
        meter.memory_writes(sum(stage_counts[s]["memory_writes"] for s in stage_counts))

    return Candidate(coefficients=coefficients), stage_counts, pivot_swaps


# ---------------------------------------------------------------------------
# Diagnostics builder
# ---------------------------------------------------------------------------


def build_diagnostics(
    stage_counts: dict[str, dict[str, int]],
    pivot_swaps: int,
    dimension: int,
    modulus: int,
    eta: int,
) -> dict:
    """Build the candidate_diagnostics object for one run."""
    total_by_stage = {}
    for name, counts in stage_counts.items():
        total_by_stage[name] = sum(counts.values())

    return {
        "stages": {
            name: {
                "additions": counts["additions"],
                "multiplications": counts["multiplications"],
                "modular_reductions": counts["modular_reductions"],
                "basis_updates": counts["basis_updates"],
                "memory_reads": counts["memory_reads"],
                "memory_writes": counts["memory_writes"],
                "total": sum(counts.values()),
            }
            for name, counts in stage_counts.items()
        },
        "stage_totals": total_by_stage,
        "pivot_swaps": pivot_swaps,
        "dimension": dimension,
        "modulus": modulus,
        "eta": eta,
        "coefficient_range": f"[-{eta}, {eta}]",
        "approach": (
            "Gaussian elimination with partial pivoting. "
            "Forward elimination to upper-triangular form (O(n^3/3) field ops), "
            "back substitution (O(n^2/2) field ops), "
            "coefficient centering from [0, q-1] to [-q//2, q//2]. "
            "Since eta < q//2 for all profiles, the centered residues "
            "recover the unique bounded vector within [-eta, eta]."
        ),
    }
