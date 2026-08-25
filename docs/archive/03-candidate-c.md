# Agent brief: Candidate C — structure-exploiting route (method proposed by agent)

## Role

Build and instrument the Candidate C solver and its test suite for the reduced-scale instance comparison.

Candidate C is a structure-exploiting approach that must be different from Candidate A (direct bounded recovery) and Candidate B (lattice reduction with extraction). The concrete method is not prescribed by this brief. The Candidate C agent must propose and document a concrete method before running it.

## What you own

- The Candidate C method proposal and documentation.
- The Candidate C solver implementation.
- The Candidate C run harness that exercises the solver on the shared instance pool.
- The Candidate C diagnostic reporting that explains where the budget went.

## What you do not own

- Instance generation. Use the shared instances exactly as provided for a given profile and seed.
- The success definition. It is fixed by the shared frame: the final output must be a vector `c` of the correct dimension with all coefficients in `[-eta, eta]` and `A c == t (mod q)`. No resource limits.
- The cost vocabulary or result schema. Those are fixed by the shared frame. You may add explanatory diagnostics, but you may not invent new top-level comparison fields.
- The ranking logic. The orchestrator compares all candidates using the shared cost fields. Candidate-specific diagnostics are explanatory only.

## Input you receive

- The shared instance pool: profiles small/medium/large, seeds 1/2/3 (9 instances total).
- The shared result schema (see shared frame).
- The shared operation vocabulary: version-2 cost model from `src/mldsafail/benchmark/cost_model.py`, with `OperationMeter` interface and six categories (additions, multiplications, modular_reductions, basis_updates, memory_reads, memory_writes), all weights 1.

## Method proposal requirement

Before you implement or run Candidate C, you must propose a concrete method and document it clearly enough that it can be compared under the shared rules. Your proposal must address:

1. **What the method does.** Describe the algorithmic approach at a level where someone can understand what it exploits and how. Examples of directions that would qualify as "structure-exploiting" and different from A and B:
   - Guessing some subset of coefficients and solving the reduced system for the remainder.
   - A meet-in-the-middle approach that splits the coefficient vector and matches partial results.
   - An enumeration strategy that exploits the small eta bound more directly than generic recovery.
   - A hybrid that combines a cheap preprocessing step with a targeted search.
   - Something else that uses the bounded-coefficient structure in a way A and B do not.

2. **Why it is different from A and B.** State what A and B do and why your method takes a different algorithmic axis.

3. **How it produces a valid `c`.** State the extraction method explicitly. If your method naturally produces a vector, say so. If it produces some intermediate structure, define the extraction step.

4. **How you will instrument the shared cost.** State which operations in your method map to which cost categories.

5. **What diagnostics you will report.** State what candidate-specific statistics will explain where the budget went.

6. **Plausibility check.** State why this method could plausibly work on the reduced-scale instances (small: dim=8, q=97, eta=2; medium: dim=16, q=257, eta=3; large: dim=24, q=769, eta=4).

The orchestrator will review your proposal. You may proceed to implement and run once the proposal is documented in your deliverables. If the proposal is too vague to be comparable, the orchestrator will ask you to pin it down before running.

## What you must produce

### Method proposal document

A short document (included in your deliverables, not a separate top-level comparison field) that covers the six points above. This is not optional. Candidate C cannot be run as comparable until the method is documented.

### For every instance in the assigned pool, emit one JSON line containing:

- `candidate_id`: `"C"`
- `profile`: profile name
- `seed`: seed
- `instance_id`: instance identifier
- `correct`: boolean from the public-data check
- `failure_reason`: string or `null`
- `shared_cost`:
  - `version`: `"2"`
  - `weighted_total`: version-2 weighted abstract cost
  - `raw`: object with `additions`, `multiplications`, `modular_reductions`, `basis_updates`, `memory_reads`, `memory_writes`
- `wall_seconds`: numeric or `null`
- `peak_memory_bytes`: numeric or `null`
- `extraction_method`: short string describing how the final `c` was obtained. Example: `"guessing + reduced solve"`, `"meet-in-the-middle + match"`, or whatever your method actually does.
- `candidate_diagnostics`: an object explaining where Candidate C spent its budget. Choose statistics meaningful for your method.
- `notes`: free text

## Instrumenting cost

You must report the shared operation vocabulary for every run. That is mandatory. The orchestrator will use `shared_cost` to compare Candidate C against Candidate A and Candidate B.

Report the shared cost for the entire pipeline: preprocessing, guessing/solving/matching, and extraction. Do not split off a private cost model that the orchestrator cannot compare.

## Success and failure

You are not judged on implementation elegance. You are judged on whether Candidate C:

- produces a valid `c` that passes the public-data check;
- reports the shared cost correctly;
- reports results in the required JSON-line format;
- documents its extraction method and diagnostics clearly enough that the orchestrator can compare it with the other candidates.

If Candidate C fails on an instance, record it honestly with a `failure_reason`. Do not claim success for an invalid vector, an out-of-bounds vector, or a vector that fails the modular relation check.

If your method cannot produce a valid `c` on some instances, report the failure and explain why. That is useful information for the comparison.

## Scope limits on implementation freedom

You may implement Candidate C however you like within the constraints of the shared frame, including reusing existing repository scaffolding where appropriate. You may choose the algorithmic strategy, as long as:

- the final output is a valid bounded short vector;
- the cost accounting follows the shared vocabulary;
- the method is documented before running;
- the method is arguably different from A and B.

If you are tempted to optimize for something other than the shared cost fields, pause and check with the orchestrator.

## Deliverables

- A method proposal document covering the six points in the method proposal requirement section.
- A working Candidate C implementation.
- A run script or harness that executes Candidate C on the shared instance pool and produces the required JSON lines.
- Any local notes the orchestrator needs to understand Candidate C's diagnostics and extraction method.

## Questions

If anything in this brief is ambiguous, ask the orchestrator before deciding. In particular, ask if you are unsure about:

- whether your proposed method is different enough from A and B;
- how the shared operation meter should be applied to your implementation;
- what counts as a meaningful diagnostic for your method;
- whether your extraction step is explicit enough.

Do not silently change the success definition, the shared cost fields, or the result schema.
