"""Document the problem definition decision and the lattice-reduction fix.

## What was tried

Candidate B attempted to solve A*c ≡ t (mod q) with |c_i| ≤ η using LLL on the
2n-dimensional lattice:

    M = [I_n, A^T]
        [0_n, q*I_n]

The planted solution s gives a lattice point (s, t) in M, because t = A*s - q*k
for some integer vector k. Candidate B ran LLL on M, then searched the reduced
basis (Babai, pairs, triples, exhaustive) for a vector whose left half satisfies
the bound and modular relation.

## What went wrong

The vector (s, t) is NOT short in this lattice. The norm squared is:

    |(s, t)|² = |s|² + |t|²

For the small profile (n=8, q=97, η=2), typical values are:

    |s|² ≤ 32,  |t|² ≈ 25000-39000,  so |(s, t)|² ≈ 25000-39000

Meanwhile, the lattice M contains much shorter vectors:

    (0, q*e_i) with |(0, q*e_i)|² = q² = 9409

LLL correctly finds these shorter vectors (norms 65-97), but none of them
correspond to the planted solution. The search procedures (Babai, pair/triple
enumeration, exhaustive) cannot find (s, t) because it is not among the short
vectors LLL produces.

This is a fundamental mismatch: the lattice M is designed to capture the modular
relation A*s ≡ t (mod q), but it does not make the solution short. The Montgomery
embedding / Kannan embedding technique is required to make the solution the shortest
vector in a related lattice.

## Decision: keep the problem, fix the solver

The problem definition (modular linear system with planted bounded solution) is
sound and self-consistent. It is a valid synthetic proxy that rewards finding small
solutions to modular systems. The issue was purely in Candidate B's lattice
construction, not in the problem statement.

The fix is to use the Kannan embedding (sometimes called the "modulus embedding" or
"CVP embedding"):

    L_emb = [ I_n    A     0  ]   (rows are basis vectors, dimension 2n+1)
            [ 0_n   q*I_n  0  ]
            [ 0_n    t     1  ]

The planted solution s gives a short lattice vector:

    (-s, 0, 1) = s*(rows 0..n-1) + k*(rows n..2n-1) + (-1)*(last row)

with norm squared |s|² + 1. For the small profile this is ≤ 33, compared to the
q² = 9409 vectors that dominate the unembedded lattice.

LLL on L_emb finds (-s, 0, 1) (or its negative) as a short vector. The solver
extracts the first n coordinates, negates if the last coordinate is -1, and verifies
against the public instance.

## Implementation

The fixed solver is in src/mldsafail/solver/candidate_b.py. It replaces the lattice
construction and search while keeping the same public contract (solve(instance, cost)
→ Candidate).

## Performance characteristics

The embedded lattice has dimension 2n+1 instead of 2n, and LLL cost is O(dim³ log B)
where B is the bit-size of basis entries. For the benchmark profiles:

    small:  n=8,   dim=17,  q=97   — trivial
    medium: n=16,  dim=33,  q=257  — moderate
    large:  n=24,  dim=49,  q=769  — heavier but tractable

The operation cost will be higher than Gaussian elimination ( Candidates A / lazy )
because LLL does many more operations. This is expected: lattice reduction is
hypothesized to be the expensive step. The score will be worse than the Gaussian
elimination baseline, but it will be a CORRECT lattice-reduction baseline that future
optimization can improve upon.

## Remaining open questions

1. Is the embedded lattice approach the right target, or should the problem be changed
   to directly ask for short vectors in a given lattice (CSS/SSS-style)?

2. Can the LLL implementation be optimized (fewer passes, better μ management, early
   termination) to reduce the operation count?

3. For larger profiles, is BKZ or sieving needed, or does LLL suffice at these scales?

4. The cost model counts all operations equally. Should basis_updates (row swaps in
   LLL) be weighted differently from arithmetic operations?

5. Should the benchmark add a direct lattice-shortest-vector problem alongside the
   modular-system problem?

## Files changed

- src/mldsafail/solver/candidate_b.py  — replaced lattice construction + search
- results/experiments.jsonl             — appended new experiment record
- docs/agent-briefs/candidate-b-fix.md  — this document
"""
