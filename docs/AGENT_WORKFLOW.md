# Agent experiment workflow

This procedure keeps autonomous optimization reproducible and within the toy-only safety boundary.

1. Activate the environment with `source .venv/bin/activate`, inspect `AGENTS.md`, and confirm the worktree state.
2. Run `make test` and the current public benchmark. Record the baseline experiment and its parent ID.
3. Write one falsifiable hypothesis, such as “incremental reduction state will lower the score on medium and large.”
4. Change only the smallest relevant area, normally `src/mldsafail/solver/` or `src/mldsafail/math/`. Do not alter profiles, seeds, generator, verifier, scoring, fingerprints, or safety validation to produce an apparent improvement.
5. Run focused tests, then `make test`, then all public profiles. Invalid output ends the experiment with no score.
6. If the public score improves, run `python -m mldsafail.benchmark.runner --suite full` to evaluate hidden seeds from the same distribution.
7. Keep the code only if correctness holds, resource limits are respected, and the combined public/hidden headline score is strictly lower. Revert non-improving code without deleting its appended experiment record.
8. Commit a coherent, descriptive checkpoint. Never push to the main branch automatically.

Every record should make the experiment independently interpretable: hypothesis, command, revision and dirty state, Python/dependency/OS/architecture metadata, seed suite, headline score, diagnostic metrics, cost-model version, resource limits, verification result, notes, parent experiment, and integrity fingerprint.

Stop and replace any proposal that would ingest an external key or signature, enable arbitrary attack parameters, target a deployed system, or operate beyond repository-generated toy instances. The permitted substitute is a bounded synthetic experiment or a non-executable theoretical/resource estimate.
