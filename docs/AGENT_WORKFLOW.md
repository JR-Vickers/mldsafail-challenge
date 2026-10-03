# Agent experiment workflow

Participant package 0.5.1 defaults clone and submissions to benchmark 0.5.0.
Choose the benchmark version before an experiment. Current research and private
staging use MLWE 0.5.0; `make bench`, `mldsafail run`, and the development Compose
stack retain historical 0.4.0 behavior. `make check` runs the test suite and a
historical small-profile smoke. It does not measure a 0.5.0 improvement.

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
   `scripts/mlwe_pilot.py develop` evaluates 50 fixed public cases, each with one
   warmup and three measurements, and requires a ledger, hypothesis, mechanism,
   parent revision, and model. Consult `develop --help` for the exact arguments.
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
`mldsafail clone` defaults to MLWE 0.5.0; use `--benchmark-version 0.4.0` for historical work. See
[HOSTED_V050.md](HOSTED_V050.md) for cohort and source requirements.

## Historical 0.4.0

1. Activate `.venv`, inspect the worktree, and run `make test` and `make bench` to
   establish the public baseline. Record its parent experiment and hypothesis.
2. Edit only the smallest relevant area in `src/mldsafail/solver/` or
   `src/mldsafail/math/`. Preserve the trusted generator/verifier, profiles,
   hidden seeds, cost model, scoring, fingerprints, and resource limits.
3. Run focused tests, then `make test` and all public profiles. Invalid or over-limit
   output cannot establish an improvement. Never fabricate operation counters.
4. After a public gain, an authorized maintainer runs the full suite using
   `MLDSAFAIL_HIDDEN_SEEDS_PATH`, a clean committed tree, and that release's reviewed
   trusted fingerprint. Use `python -m mldsafail.benchmark.runner --suite full
   --baseline-fingerprint REVIEWED_FINGERPRINT` with the usual experiment metadata.
5. Keep code only if correctness/resource limits hold and the matching full-suite
   operation-count score is lower. Preserve the failed experiment record when
   reverting code. Run `make check` and commit the validated checkpoint.

## Shared safety boundary

All executable experiments use repository-generated tiny instances. Reject work
that ingests external keys/signatures, allows arbitrary attack parameters, targets
deployed systems, or uses production ML-DSA parameters. Replace it with a bounded
synthetic experiment or a non-executable theoretical/resource estimate. The adopted
profiles are structural analogues, not standardized ML-DSA parameter sets.
