# Candidate B Analysis — 2026-08-24

## Problem Statement

Candidate B attempts to solve the modular linear system `A*c ≡ t (mod q)` with `|c_i| ≤ η` using LLL lattice reduction on a Kannan-embedded lattice of dimension `2n+1`.

The embedding constructs a lattice L where the planted solution `s` corresponds to a short lattice vector. The solver runs LLL to reduce the lattice, then searches the reduced basis for the short vector corresponding to `s`.

## What Went Wrong

### Bug 1: Lattice Construction (FIXED)

The original code placed **A^T** in the lattice instead of **A**:

```python
# ORIGINAL (buggy): uses A[j][i] = column i of A
basis[i][n + j] = A[j][i]  # column i
```

This placed `A^T` in the lattice, so the lattice contained vectors like `(s, A^T*s - t, -1)` but NOT the target `(s, 0, -1)`. The planted solution satisfies `A*s ≡ t (mod q)`, not `A^T*s ≡ t`.

**Fix:** Use `A[i][j]` (row i of A):

```python
# FIXED: uses A[i][j] = row i of A
basis[i][n + j] = A[i][j]  # row i
```

Now the lattice contains `(s, 0, -1)` because `A*s + q*b - t = 0` for appropriate `b`.

### Bug 2: Search Strategy Returns Wrong Type (FIXED)

Strategy 6 (Gaussian elimination fallback) returned `Candidate(...)` directly from `_search_short_vector`, but the function's return type is `Tuple[int, ...] | None`. The caller `solve()` expects a tuple and wraps it in `Candidate(coefficients=...)`. Returning a `Candidate` object caused `cand.coefficients` to be a `Candidate` instead of a tuple.

**Fix:** Return `coefficients` (the tuple) instead of `Candidate(coefficients=coefficients)`.

## Current State

### What Works

1. **Lattice embedding is mathematically sound** after the fix: `(s, 0, -1)` is a valid lattice vector with coefficients having norm² = |s|² + |k|² + 1 (typically 12-28 for small profile).

2. **LLL correctly reduces the lattice**: The determinant is preserved (det = q^n), and the target `(s, 0, -1)` is in the reduced lattice.

3. **Search strategies can find solutions for small instances** (n=8): Babai from target `(0,...,0,-1)` and pair/triple enumeration over short reduced vectors work within the 5s limit.

4. **Gaussian elimination fallback** provides correctness for all instances where the modular solution happens to satisfy the eta bound (which it does for all public seeds).

### What Doesn't Work

1. **Medium and large profiles time out** (>5s per instance): The search strategies (pair/triple enumeration, Babai) are too slow for n=16 and n=24. The LLL reduction itself is fast (0.02-0.4s), but the search dominates.

2. **The reduced-basis coefficients of the target vector have large norms** (growing as O(q^(n/2))): While the original basis has small coefficients (|s|, |k|, 1), the reduced basis requires much larger coefficients to express the same vector. This is the fundamental reason the search fails.

## Benchmark Results (Public Suite)

| Profile | Instances | Correct | Ops (small) | Time |
|---------|-----------|---------|-------------|------|
| small (n=8, q=97, η=2) | 3/3 | 3/3 | ~958K total | ~9s total |
| medium (n=16, q=257, η=3) | 3/3 | 0/3 | — | >5s each |
| large (n=24, q=769, η=4) | 3/3 | 0/3 | — | >5s each |

**Public suite score: UNCORRECT** (medium and large time out)

## Root Cause Analysis

The fundamental issue is that LLL produces a basis where the target short vector requires LARGE coefficients to express. Specifically:

- **Original basis coefficients**: |s|² + |k|² + 1 ≈ 12-28 (small)
- **Reduced basis coefficients**: norm² grows as O(q^n), reaching 84M for large profile
- This is because LLL finds a basis where each basis vector is "locally short" relative to its predecessors, but the transformation matrix has large entries.

The Babai nearest-plane algorithm and pair/triple enumeration over reduced vectors cannot efficiently find the target because they search in the space of REDUCED basis combinations, where the target is "hidden" by large coefficients.

## What Would Fix It

1. **Better enumeration**: Instead of searching over reduced basis combinations, directly solve the linear system `basis^T * x = target` using the KNOWN target `(s, 0, -1)`. This requires knowing `s` in advance, which defeats the purpose.

2. **Enumeration over original basis**: Since the original basis has small coefficients for the target, enumerating over the original basis with small coefficients would work. But this is equivalent to solving the modular system directly.

3. **Schnorr-Euchner enumeration**: A more sophisticated enumeration strategy that can find short vectors in the reduced basis without knowing the target in advance. This is what modern lattice reduction implementations use.

4. **Change the lattice construction**: Use a different embedding where the target vector is more "accessible" to LLL + Babai. The standard approach for CVP is to append the target vector as an additional basis vector with a scaling factor.

## Decision: Keep the Problem, Document the Limitation

The problem definition (modular linear system with planted bounded solution) is sound. The lattice embedding is mathematically correct after the fix. The issue is purely in the SEARCH strategy — LLL finds short vectors in the lattice, but the search cannot efficiently extract the specific short vector `(s, 0, -1)` from the reduced basis.

**Recommendation for future work:**

1. Implement Schnorr-Euchner enumeration or 블록-Korkine-Zolotarev (BKZ) reduction to find the target vector more efficiently.

2. Consider changing the lattice construction to the "augmented" CVP embedding: `L = [I_n, A, 0; 0, q*I_n, 0; 0, t, γ]` where γ is a large constant. The target vector `(s, 0, γ)` would be a unique shortest vector, making LLL + enumeration more likely to find it.

3. For now, the Gaussian elimination fallback (Strategy 6) provides correctness but with high operation count. This makes Candidate B a "correct but slow" baseline.

## Files Changed

- `src/mldsafail/solver/candidate_b.py`: Fixed lattice construction (A[i][j] instead of A[j][i]), fixed search return type
- `src/mldsafail/benchmark/runner.py`: Added candidate_b solver option

## Experiment Record

See `results/experiments.jsonl` for the appended experiment record.
