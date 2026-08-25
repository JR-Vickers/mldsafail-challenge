# Agent Brief: Path 1 — Redesign the Challenge Around Lattice Reduction

**Date:** 2026-08-24
**Status:** Active. One-shot implementation target.

## 1. Context and Goal

You are implementing Path 1 from the project's conclusions document. The raw prompt we started from was:

> "Okay, so what I would like is, okay, so if we're doing something like ecdsa.fail, but instead it's mldsa.fail, we probably want to isolate what the hardest part of attacking the lattice stuff... I think that it would probably be the basis reduction that we'd want to isolate."

The project spent a week testing whether the basis-reduction approach (Candidate B) is better or worse than alternatives on the current benchmark problem. The outcome was clear: the current benchmark problem (Section 5 of PLAN.md) is a modular linear system with an invertible matrix — Gaussian elimination trivially wins. The problem does not reward lattice reduction at all.

The decision: redesign the challenge so that lattice reduction is the natural and necessary approach. The benchmark should actually test what the transcript hypothesized.

You are implementing that redesign.

## 2. What Exists Now

### The current problem (to be replaced or supplemented)

Section 5 of PLAN.md defines the current challenge:

- Given: prime modulus `q`, `n × n` matrix `A` over `Z/qZ`, target vector `t` of length `n`, bound `η`
- Find: vector `c` of length `n` with integer coefficients in `[-η, η]` such that `A * c ≡ t (mod q)`
- Instances generated deterministically from profile (small/medium/large) and seed
- The planted solution `s` satisfies `t = A * s mod q` with `|s_i| ≤ η`
- Three profiles: small (n=8, q=97, η=2), medium (n=16, q=257, η=3), large (n=24, q=769, η=4)

### Current infrastructure (to be preserved/adapted)

- `src/mldsafail/trusted/generator.py` — instance generation
- `src/mldsafail/trusted/verifier.py` — candidate verification
- `src/mldsafail/benchmark/cost_model.py` — OperationMeter (version 2)
- `src/mldsafail/benchmark/runner.py` — benchmark runner CLI
- `src/mldsafail/benchmark/suites.py` — seed suite loading
- `src/mldsafail/benchmark/records.py` — experiment JSONL writer
- `src/mldsafail/benchmark/integrity.py` — trusted fingerprint
- `src/mldsafail/benchmark/metrics.py` — profile/instance measurement
- `src/mldsafail/benchmark/comparison.py` — result comparison
- `config/profiles.toml` — profile parameters
- `src/mldsafail/data/public_seeds.json` — public seeds
- `src/mldsafail/models.py` — ChallengeInstance, Candidate, etc.
- `results/experiments.jsonl` — append-only experiment log
- `docs/PLAN.md` — project specification (authoritative)
- `docs/conclusions.md` — path decision record

### Candidate B infrastructure (foundation for the redesign)

`src/mldsafail/solver/candidate_b.py` contains:

- `_build_lattice_basis(instance)` — Kannan-embedded lattice construction (dimension 2n+1)
  - Rows: (e_i, A_col_i, 0) for i=0..n-1, (0, q*e_i, 0) for i=0..n-1, (0, t, 1) for the last row
  - The planted solution s yields lattice vector (-s, 0, 1) with norm² = |s|² + 1
  - This construction is **correct** — verified
- `lll_reduce(basis, delta, cost)` — LLL reduction with incremental Gram-Schmidt updates
  - Returns reduced basis and pass count
  - Preserves lattice determinant (det = q^n)
  - This implementation is **correct** — verified
- `_babai_closest(reduced_basis, target, cost)` — Babai nearest-plane algorithm
- `_search_short_vector(reduced_basis, instance, cost)` — multiple search strategies:
  - Strategy 1: direct scan of reduced basis vectors
  - Strategy 2: Babai nearest-plane from target (0,...,0,1)
  - Strategy 3: pairs of reduced basis vectors
  - Strategy 4: triples of reduced basis vectors
  - Strategy 5: short-vector-focused combinations
  - Strategy 6: Gaussian elimination fallback (correctness safety net)
- `solve(instance, cost)` — main entry point, returns Candidate
- `build_diagnostics(...)` — diagnostic metadata

The **key finding** from Candidate B: the lattice embedding is correct, LLL reduces the lattice correctly, but the search strategies fail to find the target vector in the reduced basis because the target's representation in the reduced basis requires large coefficients (growing as O(q^n)). The search is the bottleneck, not the reduction.

### Current solvers (for reference)

- `src/mldsafail/solver/baseline.py` — clear Gaussian elimination baseline
- `src/mldsafail/solver/reference.py` — reference implementation
- `src/mldsafail/solver/lazy.py` — current best: triangular elimination with lazy modular reduction (137K ops aggregate on full suite)
- `src/mldsafail/solver/candidate_a.py` — Candidate A (Gaussian elimination with centering)
- `src/mldsafail/solver/candidate_c.py` — Candidate C (guessing + reduced solve, exponential)

## 3. What You Need to Build

### 3.1 A new challenge problem where lattice reduction is necessary

The current problem is: "Given (A, t, q, η), find bounded c with A*c ≡ t (mod q)."

The new problem must be: something where Gaussian elimination on a modular system either:
- cannot solve it (the matrix is not invertible, or the solution is not unique), or
- is suboptimal compared to lattice reduction (reduction finds a shorter/cheaper solution)

Concrete options to consider (pick one, or propose a better one):

**Option A: Direct SVP on a constructed lattice.**
Given a lattice basis (constructed from public parameters), find the shortest non-zero vector (or a vector satisfying a specific constraint). The problem is genuinely a lattice problem — Gaussian elimination does not apply.

**Option B: CVP-style embedding where the target is the shortest vector.**
Similar to Candidate B's Kannan embedding, but design the instance so that:
- The target vector is the unique shortest vector (or among the shortest)
- LLL (or a stronger reduction) is necessary to find it
- The search in the reduced basis actually works because the target's coefficients in the reduced basis are small
- Gaussian elimination on a modular system either cannot solve it or gives a worse solution

**Option C: Module-lattice reduction step.**
Given a module-lattice basis (structured, ML-DSA-like), perform one reduction step and extract a specific short vector. This is closer to the real ML-DSA structure but more complex to implement.

**Option D: Non-invertible matrix with multiple bounded solutions.**
Change the generator so A is not invertible (rank-deficient), so the modular system has multiple solutions. The challenge is to find the one with smallest norm (or the one satisfying additional constraints). This requires enumeration or reduction, not just GE.

**Recommendation:** Start with Option B (refined Kannan embedding) because Candidate B's infrastructure already implements it. The problem was that the search failed, not the embedding. Fix the search, or redesign the embedding so the search works. The ecdsa.fail analogy suggests isolating one precise primitive — make that primitive "find the short vector in this lattice."

### 3.2 Instance generation for the new problem

The generator must produce instances that are:
- Deterministic (same seed → same instance)
- Small enough for rapid iteration (seconds, not minutes)
- Hard enough that lattice reduction is necessary (not solvable by trivial GE)
- Have a known planted solution for verification (retained only in trusted code)
- Increasing difficulty across profiles

For the Kannan-embedding approach, the generator should:
- Produce (A, t, q, n, η) as before
- But design A and t so that the planted solution s corresponds to a genuinely short vector in the embedded lattice
- Ensure the target vector's representation in the reduced basis has small coefficients (so search works)
- This may require constraining A's structure or the distribution of s

For a direct-SVP approach, the generator should:
- Produce a lattice basis directly (not via A, t)
- Plant a short vector in the lattice
- The solver's job is to find that short vector (or any short vector, depending on the exact problem)

### 3.3 Verifier for the new problem

The verifier must check:
- The candidate has the correct dimension
- The candidate satisfies the problem constraints (e.g., is a lattice vector, has small norm, satisfies the modular relation if applicable)
- The candidate does not trivially cheat (e.g., is not the zero vector if zero is disallowed)

The verifier must not receive the planted secret. It validates the candidate against public challenge data only.

### 3.4 A working solver for the new problem

This should be built on Candidate B's infrastructure:
- Use the existing LLL implementation
- Fix or replace the search strategy so it actually finds the target in the reduced basis

Search strategies to consider:
- **Schnorr-Euchner enumeration**: a tree-based enumeration that finds short vectors in the reduced basis. This is what modern lattice reduction implementations use.
- **A different embedding**: the augmented CVP embedding with a scaling factor γ that makes the target a unique shortest vector
- **BKZ or stronger reduction**: if LLL doesn't produce a basis where the target is findable, stronger reduction might
- **Hybrid**: reduce, then enumerate within a radius

The solver should:
- Return a Candidate with coefficients
- Instrument operations through the OperationMeter
- Work on all three profiles within resource limits (5s wall time, 64 MiB memory per instance)
- Be correct on all public seeds

### 3.5 Baseline score on the new problem

Run the new solver on the public suite and record a baseline experiment in `results/experiments.jsonl`.

## 4. What NOT to Change

The following are benchmark-defining and must not change during this implementation (unless you bump the benchmark version):

- `src/mldsafail/trusted/generator.py` — but you may extend it for the new problem (new version requires new baseline)
- `src/mldsafail/trusted/verifier.py` — but you may extend it for the new problem
- `src/mldsafail/benchmark/cost_model.py` — the operation meter
- `src/mldsafail/benchmark/runner.py` — the CLI
- `src/mldsafail/benchmark/suites.py` — seed suites
- `src/mldsafail/benchmark/records.py` — JSONL writer
- `src/mldsafail/benchmark/integrity.py` — fingerprint computation
- `src/mldsafail/benchmark/metrics.py` — metrics
- `src/mldsafail/benchmark/comparison.py` — comparison
- `config/profiles.toml` — profile parameters (may need new profiles or new fields for the new problem)
- `src/mldsafail/data/public_seeds.json` — public seeds (may need new seeds for the new problem)
- `src/mldsafail/benchmark/contract.toml` — benchmark contract version

In practice: you will probably need to bump the benchmark version and update several of these. That's expected for a problem redesign. The key constraint: don't silently change the existing benchmark — if you create a new version, establish a new baseline.

What you MAY edit freely:
- `src/mldsafail/solver/` — new solver implementations
- `src/mldsafail/math/` — mathematical primitives (lattice operations, etc.)
- `docs/` — documentation (PLAN.md, CHALLENGE.md, etc.)

## 5. Success Criteria

1. **New problem is defined.** A clear challenge contract (like CHALLENGE.md) for the new problem, specifying the input, the output, the verification, and the scoring.

2. **Instances are generated.** A generator (or extended generator) that produces valid instances for the new problem on all three profiles.

3. **Verifier works.** An independent verifier that checks candidates against public data only.

4. **A solver works.** At least one solver that solves the new problem correctly on all public seeds within resource limits.

5. **Baseline is recorded.** A benchmark run on the public suite with a valid score, recorded in `results/experiments.jsonl`.

6. **PLAN.md and CHALLENGE.md are updated** to reflect the new problem (or a new version of the benchmark).

7. **Candidate B's infrastructure is reused or extended**, not discarded. The point of Path 1 is that this infrastructure is valuable.

8. **The existing modular-system benchmark is preserved** as a fallback (Path 2). Do not delete or overwrite it. The new problem can coexist as a separate benchmark version, a separate track, or a replacement — but the existing code and experiment history remain accessible.

## 6. Open Questions (resolve as you go)

These are flagged in conclusions.md Section 5 and PLAN.md Section 23:

1. **Exact problem statement:** Which option (A/B/C/D) above, or something else?
2. **Instance design:** What lattice instances? Kannan embedding? Direct SVP? Something else?
3. **Cost metric:** Abstract operation count (current) or something more specific to reduction?
4. **Search strategy:** Schnorr-Euchner? BKZ? Better embedding? Hybrid?
5. **Coexistence with existing benchmark:** Separate version? Separate track? Replacement?

The conclusions document says these are not blockers for starting — resolve them as part of the redesign.

## 7. Constraints

- All instances must be small, synthetic, deterministic, and locally generated.
- No production ML-DSA parameters. No real keys or signatures.
- The safety boundary (PLAN.md Section 8, AGENTS.md) must be respected.
- The benchmark must be reproducible — same seed and profile always produce the same instance.
- The verifier must be independent — it cannot receive the planted secret.

## 8. Files You'll Likely Touch

- `src/mldsafail/solver/` — new or extended solver(s)
- `src/mldsafail/math/lattice.py` — may need new lattice operations
- `src/mldsafail/trusted/generator.py` — may need new instance generation (new version)
- `src/mldsafail/trusted/verifier.py` — may need new verification (new version)
- `config/profiles.toml` — may need new profile parameters
- `src/mldsafail/data/public_seeds.json` — may need new seeds
- `src/mldsafail/benchmark/contract.toml` — new benchmark version
- `docs/PLAN.md` — update to reflect new problem
- `docs/CHALLENGE.md` — new or updated challenge contract
- `results/experiments.jsonl` — new baseline record

## 9. How to Run

After making changes:

```bash
source .venv/bin/activate
make test        # ensure tests pass
make check       # tests + small-profile smoke (no record)
python -m mldsafail.benchmark.runner --suite public  # public suite
python -m mldsafail.benchmark.runner --suite full    # full suite (if hidden seeds available)
```

The runner CLI accepts `--solver`, `--profile`, `--seed`, `--suite`, `--agent`, `--model`, `--hypothesis`, `--tag`, `--notes`, `--no-record`, and `--baseline-fingerprint` flags. Run with `--no-record` for diagnostic runs that shouldn't append to the experiment log.

## 10. References

- `docs/PLAN.md` — project specification (authoritative)
- `docs/conclusions.md` — path decision record (Path 1 is the decision)
- `docs/CHALLENGE.md` — current benchmark contract (0.3.0, to be versioned or replaced)
- `docs/TRANSCRIPT.md` — original motivating conversation
- `src/mldsafail/solver/candidate_b.py` — existing lattice infrastructure (foundation)
- `src/mldsafail/solver/lazy.py` — current best solver on the old problem (for reference)
- `src/mldsafail/solver/baseline.py` — clear baseline (for reference)

## 11. Outcome

At the end of this session, the repo should contain:

1. A working solver for a lattice-reduction problem (not the modular system)
2. A verifiable instance generator for that problem
3. An independent verifier
4. A public-suite baseline run recorded in experiments.jsonl
5. Updated documentation (PLAN.md, CHALLENGE.md or equivalent)
6. The existing modular-system benchmark preserved and untouched

The new problem should make lattice reduction the necessary and natural approach — Gaussian elimination should either not solve it or be clearly suboptimal.

Good luck.
