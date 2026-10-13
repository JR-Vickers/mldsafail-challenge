# Agent experiment workflow

Supported participants use Python-only `solver.py` with `solve(public_instance)`.
`mldsafail run` and `make bench BENCH_ARGS="..."` execute the public MLWE 0.5.0
development procedure with required ledger and hypothesis metadata. `make check`
runs the suite and deterministic MLWE contract checks. Public CPU scores remain
diagnostic; private staging uses frozen 0.5.0, and proposed 0.6.0 remains gated.

Read [AGENTS.md](../AGENTS.md), [PLAN.md](PLAN.md), and the matching contract.
Every experiment records a falsifiable hypothesis, baseline/parent identity,
benchmark version, source revision/digest, command, environment/artifacts,
comparison protocol, resource outcomes, verification, score, and disposition.
Preserve unsuccessful and partial evidence. Commit validated checkpoints without
pushing; the owner handles publication.

## MLWE 0.5.0

1. Activate `.venv` and confirm worktree state. Use [MLWE_LOCAL.md](MLWE_LOCAL.md)
   for the frozen interface and [MLWE_PILOT.md](MLWE_PILOT.md) for public development
   and predeclared private comparison procedures.
2. Copy the unchanged `examples/mlwe/primal-lll/solver.py` baseline into a separate
   contestant directory. Edit only that Python-only workspace, with `solver.py`
   exporting `solve(public_instance)`, no symlinks, and at most 2 MB of source.
3. Run tests and establish the public development baseline before editing.
   `mldsafail run` evaluates 50 fixed public cases, each with one
   warmup and three measurements, and requires a ledger, hypothesis, mechanism,
   parent revision, and model. Consult `mldsafail run --help` for the exact arguments.
   Baseline development has no `--baseline-run`; later comparisons use the saved
   baseline run. Each output directory must be new.
4. Record the hypothesis before making the smallest contestant change. Run
   relevant focused tests, then the matching public evaluation and source review.
   Do not special-case public seeds/IDs, enumerate known seeds, cache answers,
   tamper with timing, or access evaluator generators, private evidence, or results.
5. Select and commit a final candidate using public evidence. Freeze its source
   digest and the unchanged reference before authorized private evaluation. Keep
   private evidence outside the contestant workspace and inaccessible to the
   optimizer. Do not tune against private feedback or select a favorable repeat.
6. The evaluator uses an audited sealed epoch and its fixed reference table, with
   sequential execution on the same idle host. Predeclare run order/repetitions;
   the completed pilot's `final` procedure used one fresh epoch and three paired
   reference/candidate comparisons. Creating epochs is evaluator work, not part
   of the contestant optimization loop. Failed viability gates preserve evidence
   and require an explicit operator decision; no automatic seed replacement.
7. Independently audit every complete run and recompute the official ranking.
   Any invalid answer makes the run ineligible. Ordinary crashes, caps, timeouts,
   and no-answer cases receive the frozen 60-second penalty. Partial runs cannot
   rank. Preserve all failures and apply the predeclared comparison rule, anchored
   1% tie rule, and uncertainty interpretation before retaining an improvement.
8. Record the outcome, revert regressions without deleting their evidence, run
   `make check` before handoff, and commit a descriptive checkpoint.

Do not change `src/mldsafail/benchmark_v050/`, evaluator code, worker images,
dependency locks, profiles, generators, verifiers, scoring, epoch/reference costs,
or safety limits during an optimization experiment. Changes to those contracts
require separate review/versioning. The cooperative timing adapter does not
establish hostile-code score integrity; public participation must satisfy the
remaining [hosted gates](PLAN.md#21-development-plan).

For hosted 0.5.0, submit a public GitHub full commit with
`--benchmark-version 0.5.0 --solver-path PATH`, where PATH contains `solver.py`.
`mldsafail clone` defaults to MLWE 0.5.0; historical clone/submission choices are unsupported. See
[HOSTED_V050.md](HOSTED_V050.md) for cohort and source requirements.

## Historical 0.4.0

See the [unsupported archival workflow](archive/LEGACY_V040.md). Historical records
and shared dependencies remain intact. New hosted 0.4.0 submissions are rejected.

## Shared safety boundary

All executable experiments use repository-generated tiny instances. Reject work
that ingests external keys/signatures, allows arbitrary attack parameters, targets
deployed systems, or uses production ML-DSA parameters. Replace it with a bounded
synthetic experiment or a non-executable theoretical/resource estimate. The adopted
profiles are structural analogues, not standardized ML-DSA parameter sets.
