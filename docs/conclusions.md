# Conclusions — Candidate Selection and Path Decision

**Date:** 2026-08-24
**Status:** Accepted. This document records the reasoning behind the path selection.
**Supersedes:** Individual agent briefs remain as supporting evidence; this document is the synthesis.

## 1. What We Were Trying to Decide

The project is inspired by ecdsa.fail but for ML-DSA. The core question from the transcript:

> If lattice reduction is the binding constraint on attacking ML-DSA, what is the most operation-efficient way to perform it on small, fixed, reproducible instances — and can coding agents drive that cost down in a measurable, verifiable, reproducible way?

We spent a week testing whether the basis-reduction approach (Candidate B) is better or worse than alternatives on the current benchmark problem. The answer we got was not "Candidate B is worse" — it was "the current benchmark problem does not reward basis reduction at all."

## 2. What We Found

### 2.1 The current problem does not isolate lattice reduction

The challenge contract (Section 5 of PLAN.md, CHALLENGE.md) asks solvers to find `c` in `[-η, η]` such that `A*c ≡ t (mod q)`. The matrix `A` is invertible. This is a modular linear system with a unique solution mod q. Gaussian elimination solves it directly in O(n^3) operations.

Candidate A (baseline/lazy) does exactly this and wins. Candidate B (LLL on a Kannan-embedded lattice) attempts to find the solution as a short vector in a lattice, but:

- The lattice embedding is mathematically correct (after fixing the A_col_i vs A_row_i bug)
- LLL correctly reduces the lattice (determinant preserved, target vector is in the reduced lattice)
- The search strategies (Babai nearest-plane, pair/triple enumeration over reduced basis vectors) fail to find the target vector in the reduced basis because the target's representation in the reduced basis requires large coefficients
- The Gaussian elimination fallback provides correctness but is not lattice reduction — it solves the modular system directly

### 2.2 The fundamental disconnect

The transcript's hypothesis — "lattice reduction is the hardest step in attacking ML-DSA and should be the focus of this challenge" — is about the real attack. The current benchmark problem is a different thing: a modular system where the matrix is invertible, so reduction is not the bottleneck.

You cannot falsify "is basis reduction the right bottleneck for ML-DSA" by running LLL on a problem where Gaussian elimination is the optimal strategy. That's a category error.

### 2.3 Candidate B's infrastructure is valuable

Candidate B's implementation contains:
- A correct Kannan-embedded lattice construction
- A working LLL reduction implementation with incremental Gram-Schmidt updates
- Multiple search strategies (Babai, pair/triple enumeration, short-vector-focused search)
- A Gaussian elimination fallback for correctness

This is not wasted work. It becomes the foundation for a lattice-reduction problem.

## 3. The Decision: Pursue Path 1

**Path 1:** Redesign the challenge problem so that lattice reduction is the natural and necessary approach. The benchmark should actually test what the transcript hypothesized.

### 3.1 What this means concretely

The current problem: "Given (A, t, q, η), find bounded c with A*c ≡ t (mod q)."

The redesigned problem should be something like: "Given a lattice basis (constructed from public ML-DSA-like parameters), find a short vector satisfying a constraint," or "Given a module-lattice basis, perform a reduction step and extract a specific short vector."

The key change: make the problem *not* solvable by direct Gaussian elimination on a modular system. Make reduction the right tool and direct solving either impossible or suboptimal.

Candidate B's existing infrastructure (lattice construction, LLL, search) becomes the starting point, not a failed probe.

### 3.2 Why path 1 is the right call

1. **Faithfulness to the vision:** The transcript explicitly chose to isolate basis reduction as the bottleneck, drawing the ecdsa.fail analogy. Path 1 honors that choice.

2. **Candidate B already proved the point:** The failure of Candidate B on the current problem is itself the key finding. It demonstrates that the problem doesn't reward reduction. Fixing the problem to reward reduction is the natural next step.

3. **The infrastructure exists:** We have a working LLL implementation, lattice construction, and search strategies. We're not starting from scratch — we're redirecting existing work.

4. **The alternative is less interesting:** Path 2 (accept the modular system as-is) produces a benchmark that tests Gaussian elimination optimization. That's valid but less compelling as a research challenge and less aligned with the ML-DSA narrative.

### 3.3 What success looks like

- A new challenge contract where the primary solver must perform lattice reduction
- A baseline score established on the new problem
- Candidate B's reduced-basis search fixed or replaced with a strategy that actually finds the target in the reduced basis (e.g., Schnorr-Euchner enumeration, or a different embedding where the target is accessible)
- The leaderboard ranks solvers by their efficiency at lattice reduction, not at modular system solving

## 4. Why Paths 2 and 3 Are Preserved

### 4.1 Path 2: Accept the modular system as-is

The modular system benchmark is a valid synthetic challenge. It tests operation-efficient solving of bounded modular systems. If the lattice-reduction redesign turns out to be too difficult or too far from the original problem shape, the modular system remains a fallback — a simpler, already-working benchmark that still fits the "synthetic ML-DSA-motivated optimization competition" framing.

Rationale for preservation: The modular system problem is already functional, has a working lazy solver at 137K ops, has hidden seeds, has a verifier, and has a cost model. It's a complete benchmark. Dropping it entirely would lose that investment.

### 4.2 Path 3: Hybrid / multiple problem types

The modular system and a direct lattice-reduction problem could coexist as separate tracks. Different instances test different aspects of the attack pipeline. This is the most faithful to the real ML-DSA attack, where reduction, enumeration, and hybrid strategies all play roles.

Rationale for preservation: A single-problem benchmark risks being too narrow. Multiple problem types would test different algorithmic axes and better reflect the complexity of the real attack. This is explicitly flagged as an option in PLAN.md Section 23.1 and Section 22 (Track E — Challenge Design).

### 4.3 When paths 2 and 3 would be chosen

- **Path 2:** If the lattice-reduction redesign proves too expensive to implement correctly within the time available, or if the resulting problem is too hard to score meaningfully at small scales.
- **Path 3:** If we want broader coverage and have the resources to design and baseline multiple problem types.
- **Path 1:** The default path we're pursuing now.

## 5. Open Questions That Remain

These are not blockers for path 1, but they should be resolved as part of the redesign:

1. **Exact problem statement:** What precisely is the new challenge contract? Options include: given a lattice basis, find the shortest vector; given a lattice basis and a target, find the closest vector; given a module-lattice basis, perform one reduction step; or a hybrid. The ecdsa.fail analogy suggests isolating one precise primitive.

2. **Instance design:** What lattice instances should the benchmark use? They need to be small, deterministic, reproducible, and hard enough that reduction is necessary but easy enough that solvers can run in seconds. The Kannan embedding from Candidate B suggests one approach; direct SVP/CVP on randomly generated lattices suggests another.

3. **Cost metric:** The current metric (abstract operation count with unit weights) may not be the right one for lattice reduction. Should it be reduction steps, enumeration nodes, basis quality, or something else? This is flagged in PLAN.md Section 23.3.

4. **Relationship to the existing modular system:** Should the modular system remain as a separate track, or is it replaced entirely? If replaced, does the experiment history still have value?

5. **Transition plan:** How do we move from the current benchmark to the new one without losing the experiment log, the verifier, the cost model, and the infrastructure? What stays, what changes, what gets a new benchmark version?

## 6. Evidence Supporting This Decision

- **TRANSCRIPT.md:** Explicitly identifies basis reduction as the step to isolate, draws the ecdsa.fail analogy, expresses uncertainty about whether ML-DSA differs from Falcon/Hawk in a way that changes the bottleneck.
- **Candidate B analysis (docs/agent-briefs/2026-08-24-candidate-b-analysis.md, docs/agent-briefs/2026-08-24-candidate-b.md):** Demonstrates that the lattice embedding is correct, LLL works, but the search fails on the current problem. The failure is informative — it shows the problem doesn't reward reduction.
- **Candidate C method proposal (docs/candidate-c-method-proposal.md):** Presents a guessing-plus-reduced-solve approach. Shows that multiple algorithmic axes exist, but none of them win on the current problem because Gaussian elimination is optimal for an invertible matrix.
- **PLAN.md Section 23.1:** Explicitly flags the problem-design question as open and lists the three paths we're now choosing among.

## 7. Risks

1. **Redesign effort:** Building a new problem contract, instances, verifier, and baseline is more work than optimizing the existing solver. Time available is limited.
2. **Scoring the new problem:** If the new problem is too hard at small scales, solvers may not complete within resource limits. If it's too easy, there's no room for optimization.
3. **Loss of existing benchmark:** If we replace the modular system entirely, we lose a functional benchmark with a working solver and experiment history. Path 2's preservation mitigates this.
4. **Scope creep:** The "what is the right problem" question can expand indefinitely. We need to make a concrete decision and implement it, not continue exploring.

## 8. Next Steps

1. Draft a new challenge contract for the lattice-reduction problem (Section 5.1 style).
2. Design instance generation that produces lattices where reduction is necessary.
3. Adapt the verifier to check the new problem.
4. Run the existing Candidate B infrastructure on the new problem as a first baseline.
5. Fix or replace the search strategy so Candidate B actually finds the target.
6. Establish a baseline score and record it.
7. Decide whether to keep the modular system as a secondary track (path 3) or replace it entirely (path 1 only).

## 9. Related Documents

- `docs/PLAN.md` — project specification (authoritative)
- `docs/CHALLENGE.md` — current benchmark contract (version 0.3.0)
- `docs/TRANSCRIPT.md` — source conversation motivating the project
- `docs/candidate-comparison-frame.md` — candidate comparison framework
- `docs/agent-briefs/2026-08-24-candidate-b-analysis.md` — detailed Candidate B analysis
- `docs/agent-briefs/2026-08-24-candidate-b.md` — Candidate B summary
- `docs/agent-briefs/2026-08-23-candidate-b-fix.md` — earlier Candidate B fix
- `docs/candidate-c-method-proposal.md` — Candidate C method proposal
- `results/experiments.jsonl` — experiment log (preserved for history)
