# Agent experiment workflow

This procedure keeps autonomous optimization reproducible and within the toy-only safety boundary.

1. Activate the environment with `source .venv/bin/activate`, inspect `AGENTS.md`, and confirm the worktree state.
2. Run `make test` and the current public benchmark. Record the baseline experiment and its parent ID.
3. Write one falsifiable hypothesis, such as “incremental reduction state will lower abstract cost on toy-medium and toy-large.”
4. Change only the smallest relevant area, normally `src/mldsafail/solver/` or `src/mldsafail/math/`. Do not alter profiles, seeds, generator, verifier, scoring, fingerprints, or safety validation to produce an apparent improvement.
5. Run focused tests, then `make test`, then all public profiles. Invalid output ends the experiment with no score.
6. If the public result is Pareto-improving, run `python -m mldsafail.benchmark.runner --suite full` to evaluate hidden seeds from the same distribution.
7. Keep the code only if correctness holds and the combined public/hidden result improves at least one measured dimension without being dominated. Revert regressing code without deleting its appended failure record.
8. Commit a coherent, descriptive checkpoint. Never push to the main branch automatically.

Every record should make the experiment independently interpretable: hypothesis, command, revision and dirty state, Python/dependency/OS/architecture metadata, seed suite, per-profile and aggregate metric vectors, cost-model version, verification result, notes, parent experiment, and integrity fingerprint.

Stop and replace any proposal that would ingest an external key or signature, enable arbitrary attack parameters, target a deployed system, or operate beyond repository-generated toy instances. The permitted substitute is a bounded synthetic experiment or a non-executable theoretical/resource estimate.
