# Candidate comparison framing

## Purpose

This document defines the shared frame for an empirical comparison of three candidate computational approaches on reduced-scale instances derived from the ML-DSA structure. The goal is to observe which approach tends to dominate the cost profile on structurally faithful, deliberately constrained instances, and to understand how that changes when the scale varies.

This is scoping work, not a final cryptanalytic conclusion. The instances are not production-ML-DSA parameters; they are reduced-scale instances chosen so the optimization space is tractable and measurable while preserving the underlying mathematical structure.

## Status

**Locked.** Instance pool, success criteria, cost accounting, and result schema are fixed below. Any change requires explicit orchestrator decision and a new framing revision.

## Instances

All candidates are tested on the same instances for a given profile and seed. Instance generation is identical across candidates: same matrix `A`, same target `t`, same modulus `q`, same dimension, and same coefficient bound `eta`.

### Instance pool (locked)

The instance pool for this comparison is:

- **Profiles:** small, medium, large (all three)
- **Seeds:** public seeds 1 through `public_seeds` for each profile (seeds 1, 2, 3)
- **Total instances:** 9 (3 seeds × 3 profiles)

| Profile | Dimension | Modulus | Eta | Seeds |
|---------|-----------|---------|-----|-------|
| small   | 8         | 97      | 2   | 1, 2, 3 |
| medium  | 16        | 257     | 3   | 1, 2, 3 |
| large   | 24        | 769     | 4   | 1, 2, 3 |

Each candidate sees the exact same 9 instances. Instance generation uses the repository's trusted generator: `generate_instance(seed, profile)` from `src/mldsafail/trusted/generator.py`.

### Scale language

The instances are described as reduced-scale instances of the underlying structure, not as toy problems. They are deliberately constrained in dimension, modulus, and bound so that the comparison is tractable and reproducible. The framing does not claim these instances represent production ML-DSA parameters, nor does it commit to a particular scale-up path.

## Candidates

Three candidates are compared. Their detailed implementations are defined by the agents; the framing below states only what they must ultimately produce and how they will be judged.

- **Candidate A — Bounded short-vector recovery.** Given `(A, t = A s mod q)`, recover `s` with `|s_i| <= eta`. This is the task the repository already defines and verifies.
- **Candidate B — Lattice reduction on the constructed lattice, with explicit extraction.** Build the lattice associated with the short-vector problem, run a correct reduction procedure (for example LLL or a small-block BKZ variant), then extract a short vector from the result. The point is to isolate the reduction primitive and account for how much of the budget is reduction versus construction and extraction.
- **Candidate C — Structure-exploiting route (proposed by agent).** The concrete method is not prescribed. The Candidate C agent must propose and document a concrete method that exploits the bounded coefficient structure through a different algorithmic axis before running. The method must be documented well enough that Candidate C can be compared under the same success and cost rules as A and B.

## Success

All three candidates are judged by the same final public-data check. Success means:

- the candidate outputs a vector `c` of the correct dimension;
- every coefficient of `c` lies in `[-eta, eta]`;
- `A c == t (mod q)`;
- the run completed.

If a candidate's natural output is a basis or some other structure rather than a vector directly, the candidate must define an explicit extraction step that produces a vector `c` from that structure. The final judgment does not depend on the intermediate form. A candidate that reduces to a basis but does not define a documented way to extract a valid `c` has not completed the task.

A candidate that fails to produce a valid `c` is reported as a failure with a defined reason. No candidate is credited for producing a "good basis" or "good partial structure" unless it also produces a valid `c` that passes the public-data check.

**Resource limits:** None. Candidates may run as long as they need. Failures are purely about whether a valid `c` can be found.

## Cost accounting

The only formal comparison axis across candidates is the shared operation vocabulary:

- version-2 weighted abstract cost, and
- raw per-category counts: additions, multiplications, modular reductions, basis_updates, memory_reads, memory_writes.

### Shared operation meter (locked)

The shared operation meter is defined in `src/mldsafail/benchmark/cost_model.py`. Key points:

- **Version:** `"2"`
- **Categories:** `additions`, `multiplications`, `modular_reductions`, `basis_updates`, `memory_reads`, `memory_writes`
- **Weights:** all categories have weight 1 (unit weights). `weighted_total` = sum of all raw counts.
- **Interface:** solvers receive an `OperationMeter` instance and call methods like `cost.additions(n)`, `cost.multiplications(n)`, etc. At the end, `cost.snapshot()` returns a `CostSnapshot` with the counts and `weighted_total`.
- **Validation:** counts must be non-negative integers. The meter validates on write.

Each candidate must report those shared fields for every run. The shared fields are what the orchestrator uses to compare candidates.

In addition, each candidate may report candidate-specific diagnostics that explain where its budget went. These diagnostics are explanatory, not competing winners.

The orchestrator will not invent a second comparison axis out of diagnostics. If a candidate's cost story depends heavily on a diagnostic, that is noted in the final synthesis, but the formal ranking remains on the shared fields.

## Result schema

Each candidate agent emits one JSON line per run. The orchestrator collects all lines into one dataset.

Every line must include:

- `candidate_id`: `"A"`, `"B"`, or `"C"`
- `profile`: profile name
- `seed`: seed used for this instance
- `instance_id`: instance identifier
- `correct`: boolean from the public-data check
- `failure_reason`: string or `null`
- `shared_cost`:
  - `version`: `"2"`
  - `weighted_total`: version-2 weighted abstract cost
  - `raw`: object with `additions`, `multiplications`, `modular_reductions`, `basis_updates`, `memory_reads`, `memory_writes`
- `wall_seconds`: numeric if measurable, otherwise `null`
- `peak_memory_bytes`: numeric if measurable, otherwise `null`
- `extraction_method`: short string describing how the final `c` was obtained
- `candidate_diagnostics`: object specific to the candidate, used for explanation only
- `notes`: free text for anything the agent wants to flag

The schema is frozen before any agent begins work. Agents may not invent additional top-level comparison fields without orchestrator approval.

## Orchestrator responsibilities

The orchestrator:

- writes and freezes this framing before any agent begins;
- confirms the instance pools and any later scale-variation sweep before candidates are run;
- collects the JSON-line outputs from all candidates;
- synthesizes the comparison using the shared cost fields, with the candidate-specific diagnostics used only for explanation;
- reports what the results do and do not imply, scoped to the reduced-scale instances actually tested.

## What this frame does and does not imply

This frame compares three candidate approaches on 9 reduced-scale instances. Results are scoped to those instances and those profiles. They do not imply anything about production ML-DSA parameters, larger dimensions, or different parameter choices. Any claim otherwise would overstate what was measured.
