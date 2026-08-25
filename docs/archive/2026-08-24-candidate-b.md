# Candidate B: Analysis and Baseline

**Date:** 2026-08-24
**Agent:** codex
**Model:** Solar Pro 4 (free)

## Summary

Candidate B was analyzed and partially fixed. The solver now works on the small profile (n=8) but times out on medium (n=16) and large (n=24) profiles due to search inefficiency.

## What Was Tried

### Original Candidate B Approach

Solve `A*c ≡ t (mod q)` with `|c_i| ≤ η` using LLL lattice reduction on a `(2n+1)`-dimensional Kannan-embedded lattice `L = [I_n, A^T, 0; 0, q*I_n, 0; 0, t, 1]`.

The goal: the planted solution `s` corresponds to a short lattice vector `(-s, k, 1)` with norm `|s|^2 + |k|^2 + 1`. LLL finds short vectors in the lattice; the solver then searches the reduced basis for the vector corresponding to `s`.

### Bug 1: Lattice Construction (FIXED)

The original code used `A[j][i]` (column i of A) to construct the lattice rows, but the problem is `A*c ≡ t (mod q)` — with `A` acting on the left. The lattice embedding must place `A` (not `A^T`) in the middle coordinates.

**Fix:** Changed `basis[i][n+j] = A[j][i]` (column i) to `basis[i][n+j] = A[i][j]` (row i).

This makes the lattice contain `(s, 0, -1)` as a lattice vector, where `|s|^2 + 1` is small (≤ 19 for small profile).

### Bug 2: Search Strategy Returns Wrong Type (FIXED)

The Strategy 6 (Gaussian elimination fallback) in `_search_short_vector` was returning `Candidate(coefficients=coefficients)` instead of a `tuple`. The caller `solve()` expects a `Tuple[int, ...]` and wraps it in `Candidate(coefficients=...)`. This caused `cand.coefficients` to be a `Candidate` object instead of a tuple, breaking verification.

**Fix:** Changed to `return coefficients` (the tuple).

## Current State

### Small Profile (n=8, q=97, η=2)
- **Status:** WORKS — 3/3 public seeds verified
- **Operations:** ~960K total (vs. lazy baseline ~4,120)
- **Time:** ~9s total (within 5s/instance limit for all 3 seeds)
- **Lattice embedding:** Confirmed correct — `(s, 0, -1)` is a valid lattice vector with norm² ≈ 12-19
- **LLL reduction:** Works correctly (133 passes, preserves lattice)
- **Search:** Finds solutions via pair/triple enumeration over reduced basis

### Medium Profile (n=16, q=257, η=3)
- **Status:** TIMES OUT — 0/3 public seeds verified
- **Time:** >5s per instance (resource limit exceeded)
- **Root cause:** Search strategies (pair/triple enumeration, Babai) too slow for n=16

### Large Profile (n=24, q=769, η=4)
- **Status:** TIMES OUT — 0/3 public seeds verified  
- **Time:** >5s per instance (resource limit exceeded)
- **Root cause:** Same as medium — search inefficiency

## Key Findings

### 1. Lattice Embedding is Mathematically Sound

After fixing Bug 1, the lattice correctly contains `(s, 0, -1)` as a short vector. LLL reduces the lattice correctly. The target vector is in the reduced lattice (verified by rational solving of the transposed system).

### 2. Reduced Basis Coefficients are Large

The target vector `(s, 0, -1)` requires LARGE coefficients to express in the REDUCED basis:
- Original basis: 6 non-zero coefficients, max |coeff| = 2, norm² = 12
- Reduced basis: 11 non-zero coefficients, max |coeff| = 3, norm² = 28 (still tractable)
- For medium profile: up to 32 non-zero coefficients, max |coeff| = 16
- For large profile: up to 46 non-zero coefficients, max |coeff| = 10

This is why pair/triple enumeration over the reduced basis fails for larger profiles — the coefficients needed to form `(s, 0, -1)` are large, requiring enumeration over many more combinations.

### 3. Gaussian Elimination Fallback Works

For all 9 public seeds, Gaussian elimination on the modular system `A*c ≡ t (mod q)` recovers the planted solution `s` exactly. The centered solution `c ∈ [-q/2, q/2]^n` coincides with `s` for all tested seeds.

This means:
- The planted solution IS the modular solution (not just congruent modulo q)
- Gaussian elimination is a valid fallback for correctness
- The operation count is high (~500K+ for small profile) but within limits

## Benchmark Results (Public Suite)

| Profile | Seeds | Correct | Score | Notes |
|---------|-------|---------|-------|-------|
| small | 1101, 1102, 1103 | 3/3 | ~960K ops | Works |
| medium | 2201, 2202, 2203 | 0/3 | N/A | Times out |
| large | 3301, 3302, 3303 | 0/3 | N/A | Times out |

**Public suite: INCORRECT** (only small profile works)

## Root Cause

The fundamental issue is that LLL produces a basis where the target short vector `(s, 0, -1)` requires large integer coefficients to express. While the ORIGINAL basis has small coefficients for `(s, 0, -1)` (because the basis was constructed with `(s, 0, -1)` in mind), LLL transforms the basis to make each basis vector "locally short" — which means the transformation matrix has large entries.

The search strategies (Babai, pair/triple enumeration over reduced vectors) work by finding integer combinations of REDUCED basis vectors that equal the target. But the target requires large coefficients in the reduced basis, making enumeration expensive.

## What Would Fix It

1. **Schnorr-Euchner enumeration:** A more sophisticated lattice enumeration algorithm that can efficiently find short vectors without enumerating all combinations. This is what modern lattice reduction libraries use.

2. **Block-Korkine-Zolotarev (BKZ) reduction:** Stronger than LLL, produces better bases where short vectors are more accessible. Would increase reduction time but might make search feasible.

3. **Augmented CVP embedding:** Add `-t` as an additional row with a large scaling factor γ. The lattice `L' = [I_n, A^T, 0; 0, q*I_n, 0; 0, -t, γ]` with γ chosen appropriately. The vector `(s, k, 1)` would be a unique shortest vector, making LLL + Babai more likely to find it.

4. **Use original basis for search:** Since the original basis has small coefficients for the target, enumerate over the original basis (or a subset) rather than the reduced basis. This is essentially what the Gaussian elimination fallback does.

## Decision: Keep the Problem, Document the Limitation

The problem definition is sound. The lattice embedding is correct. The search strategies are incomplete for the current problem parameters.

**Recommendation:** Use Gaussian elimination as the primary solver for now, with LLL as an optimization target for future work. The Euclidean algorithm already achieves correctness; the challenge is to reduce operations while maintaining correctness.

## Files Changed

- `src/mldsafail/solver/candidate_b.py`: Fixed lattice construction and search return type
- `src/mldsafail/benchmark/runner.py`: Added candidate_b solver option
- `docs/agent-briefs/2026-08-24-candidate-b-analysis.md`: This document
- `results/experiments.jsonl`: Appended failed experiment records

## Experiment Record

See `results/experiments.jsonl` for detailed records. Summary:
- Experiment 1: Candidate B with fixed lattice — small profile passed, medium/large failed (timeout)
- Experiment 2: Same as above — confirmed results

The experiment records are preserved even though the solver failed (correctness gate).
