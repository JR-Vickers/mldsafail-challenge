# Agent brief: Candidate A — bounded short-vector recovery

## Role

Build and instrument the Candidate A solver and its test suite for the reduced-scale instance comparison.

Candidate A is the bounded short-vector recovery task: given `(A, t = A s mod q)`, recover `s` with `|s_i| <= eta`. This task is already defined and verified by the repository. Your job is to produce a working Candidate A implementation that runs on the shared instance pool and emits results in the shared JSON-line format.

## What you own

- The Candidate A solver implementation.
- The Candidate A run harness that exercises the solver on the shared instance pool.
- The Candidate A diagnostic reporting that explains where the budget went.

## What you do not own

- Instance generation. Use the shared instances exactly as provided for a given profile and seed.
- The success definition. It is fixed by the shared frame: the final output must be a vector `c` of the correct dimension with all coefficients in `[-eta, eta]` and `A c == t (mod q)` within resource limits.
- The cost vocabulary or result schema. Those are fixed by the shared frame. You may add explanatory diagnostics, but you may not invent new top-level comparison fields.
- The ranking logic. The orchestrator compares all candidates using the shared cost fields. Candidate-specific diagnostics are explanatory only.

## Input you receive

- The shared instance pool, including the profile name, seed, `A`, `t`, `q`, dimension, and `eta`.
- The shared result schema.
- The shared operation vocabulary, including the current version-2 weighted abstract cost and raw per-category counts.

## What you must produce

For every instance in the assigned pool, emit one JSON line containing:

- `candidate_id`: `"A"`
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
- `extraction_method`: short string. For Candidate A this should reflect how the solver recovers the vector directly. Example: `"direct bounded recovery"`.
- `candidate_diagnostics`: an object explaining where Candidate A spent its budget. Choose statistics that are meaningful for your implementation. Examples might include search steps, backtracking events, pivots, or other control-flow structure, depending on how you implement the solver.
- `notes`: free text

## Instrumenting cost

You must report the shared operation vocabulary for every run. That is mandatory. The orchestrator will use `shared_cost` to compare Candidate A against Candidate B and Candidate C.

In addition, explain the shape of Candidate A's cost with `candidate_diagnostics`. Do not expect the orchestrator to interpret your implementation purely from the shared fields; the diagnostics exist so the synthesis can say something useful about Candidate A's behavior.

If your implementation has internal stages — for example, preprocessing, search, backtracking, reconstruction — it is useful to report where the shared cost landed across those stages. That is optional but encouraged.

## Success and failure

You are not judged on implementation elegance. You are judged on whether Candidate A:

- produces a valid `c` that passes the public-data check within the resource limits;
- reports the shared cost correctly;
- reports results in the required JSON-line format;
- documents its extraction method and diagnostics clearly enough that the orchestrator can compare it with the other candidates.

If Candidate A fails on an instance, record it honestly with a `failure_reason`. Do not claim success for an invalid vector, an out-of-bounds vector, or a vector that fails the modular relation check.

## Scope limits on implementation freedom

You may implement Candidate A however you like within the constraints of the shared frame. You may reuse existing solver scaffolding in the repository where appropriate. You may choose the algorithmic strategy, as long as the final output is a valid bounded short vector and the cost accounting follows the shared vocabulary.

If you are tempted to optimize for something other than the shared cost fields — for example, just minimizing wall time in a way that obscures operation counts — pause and check with the orchestrator, because that can make the comparison less informative.

## Deliverables

- A working Candidate A implementation.
- A run script or harness that executes Candidate A on the shared instance pool and produces the required JSON lines.
- Any local notes the orchestrator needs to understand Candidate A's diagnostics and extraction method.

## Questions

If anything in this brief is ambiguous, ask the orchestrator before deciding. In particular, ask if you are unsure about:

- which instance pool you should run against;
- how the shared operation meter or cost counting should be applied to your implementation;
- what counts as a meaningful diagnostic for Candidate A.

Do not silently change the success definition, the shared cost fields, or the result schema.
