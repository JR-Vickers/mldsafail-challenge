# Agent brief: Candidate B — lattice reduction with explicit extraction

## Role

Build and instrument the Candidate B solver and its test suite for the reduced-scale instance comparison.

Candidate B is a lattice reduction approach: construct the lattice associated with the bounded short-vector problem, run a correct reduction procedure, and then extract a short vector from the result. The point of this candidate is to isolate the reduction primitive and to account for how much of the total budget is reduction versus the surrounding construction and extraction work.

## What you own

- The Candidate B solver implementation.
- The Candidate B run harness that exercises the solver on the shared instance pool.
- The Candidate B diagnostic reporting that explains where the budget went, including reduction-specific statistics.

## What you do not own

- Instance generation. Use the shared instances exactly as provided for a given profile and seed.
- The success definition. It is fixed by the shared frame. The final output must be a vector `c` of the correct dimension with all coefficients in `[-eta, eta]` and `A c == t (mod q)` within resource limits.
- The cost vocabulary or result schema. Those are fixed by the shared frame. You may add explanatory diagnostics, but you may not invent new top-level comparison fields.
- The ranking logic. The orchestrator compares all candidates using the shared cost fields. Candidate-specific diagnostics are explanatory only.

## Input you receive

- The shared instance pool, including the profile name, seed, `A`, `t`, `q`, dimension, and `eta`.
- The shared result schema.
- The shared operation vocabulary, including the current version-2 weighted abstract cost and raw per-category counts.

## What you must produce

For every instance in the assigned pool, emit one JSON line containing:

- `candidate_id`: `"B"`
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
- `extraction_method`: short string describing how the final `c` was obtained from the reduced structure. This must be explicit. Examples might be `"LLL basis + shortest vector extraction"`, `"reduced basis + Babai-style extraction"`, or similar, depending on what you actually implement.
- `candidate_diagnostics`: an object explaining where Candidate B spent its budget, with reduciton-relevant statistics. Examples might include:
  - number of passes or tours
  - number of size-reduction events or column swaps
  - basis quality metrics such as maximum basis vector norm or Gram-Schmidt coefficient magnitudes
  - any useful measure of how much reduction was performed before extraction

You may include other diagnostic fields that are meaningful for your method, provided they are explainable and clearly belong to `candidate_diagnostics`, not to the shared comparison fields.

## Instrumenting cost

You must report the shared operation vocabulary for every run. That is mandatory. The shared fields cover all arithmetic and memory operations involved in lattice construction, reduction, and extraction. Do not split off a private cost model that the orchestrator cannot compare.

The important part for Candidate B is that you account for the whole pipeline, not just the reduction loop. If the cost is dominated by construction, or by extraction, or by the reduction itself, the shared fields should reflect that. The candidate diagnostics then explain why.

## Success and failure

Candidate B does not succeed merely by producing a reduced basis. It succeeds only if it produces a valid `c` that passes the public-data check within the resource limits.

If your reduction outputs a basis rather than a short vector directly, you must define an explicit, documented extraction step that turns that basis into a candidate vector `c`. The orchestrator needs to know exactly how the final vector was obtained, because that affects how we interpret the cost and the failure modes.

If Candidate B fails on an instance, record it honestly with a `failure_reason`. A failure might mean:

- the reduction did not produce a usable basis within the resource limits;
- the extraction step did not yield a valid `c`;
- the final `c` failed the modular relation check or the coefficient bound check.

Do not claim success for a nice basis that does not lead to a valid short vector.

## Implementation freedom

You may choose the reduction style, the lattice construction, and the extraction method, within the constraints of the shared frame. For reduced-scale instances, common approaches such as LLL or small-block BKZ variants are reasonable starting points, but the brief does not require any specific algorithm.

If you pick a specific variant, document it clearly in `extraction_method` and `notes`, because the comparison depends on knowing what Candidate B actually does.

If your implementation uses external libraries for reduction, the same rule applies: the shared cost fields must still cover the comparable operations, and the extraction step must be explicit. If using an external library makes the shared cost accounting unclear, flag that for the orchestrator rather than hiding the gap.

## Scope limits on implementation freedom

You are not free to redefine success. You are not free to report only reduction cost and omit construction or extraction cost. You are not free to invent new top-level comparison fields. You are not free to claim the task is complete if the final vector does not pass the public-data check.

You are free to implement the pipeline as you see fit, instrument it honestly, and report the shared cost plus explanatory diagnostics.

## Deliverables

- A working Candidate B implementation.
- A run script or harness that executes Candidate B on the shared instance pool and produces the required JSON lines.
- Clear documentation of the extraction method and the reduction-specific diagnostics.
- Any local notes the orchestrator needs to understand Candidate B's behavior and failure modes.

## Questions

If anything in this brief is ambiguous, ask the orchestrator before deciding. In particular, ask if you are unsure about:

- how the lattice should be constructed for the given public data;
- how to define a reasonable extraction step from the reduced basis;
- how to map your reduction-specific operations onto the shared cost vocabulary;
- whether your chosen reduction method is plausible for a reduced-scale instance comparison.

Do not silently change the success definition, the shared cost fields, or the result schema.
