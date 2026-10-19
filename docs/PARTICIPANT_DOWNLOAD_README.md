# MLWE participant package 0.5.1 — benchmark 0.5.0

This unpublished release candidate supports only tiny repository-generated MLWE
instances. It does not attack external keys/signatures or establish production
ML-DSA hardness. Hosted public participation remains subject to owner launch
approval; use only an explicitly authorized server/epoch.

The archive/documentation source commit/tree, separately verified wheel-build
source commit, and wheel/starter/contract hashes are recorded in `SOURCE.json`.
The included specification is a presentation copy: repository-context links to
omitted historical/operator documents are removed, with original and included
file hashes recorded separately. The scientific contract source is unchanged.
`SHA256SUMS` binds every included file; the separately retained release manifest
binds the whole archive. Verify checksums before installation. Included fixture
JSON contains six public seed-zero fixed-profile cases, never private epoch data.
The approved starter is `examples/mlwe/primal-lll/solver.py`.

## Install and identify the version

Use Python **3.12.10** on the supported POSIX environment. Set `python3` to that
interpreter before invoking the installer. It creates a new virtual environment
and refuses an existing destination; it installs the verified wheel with its
dependency metadata; dependency resolution may require access to the package index.
No login is necessary for offline historical checks or source scaffolding.

Scaffolding creates its initial commit with the synthetic identity
`MLDSAFAIL Workspace <workspace@mldsafail.invalid>` and disables signing and hooks
for that generated commit only. It works without Git identity configuration and
does not change local or global Git settings. Configure your own Git identity
before committing subsequent solver changes.

```sh
shasum -a 256 -c SHA256SUMS
sh scripts/install.sh mldsafail_challenge-0.5.1-py3-none-any.whl VERIFIED_WHEEL_SHA256 NEW_INSTALL_DIRECTORY
NEW_INSTALL_DIRECTORY/bin/mldsafail --help
NEW_INSTALL_DIRECTORY/bin/mldsafail clone NEW_SOLVER_DIRECTORY
```

Replace `VERIFIED_WHEEL_SHA256` with the value in `SOURCE.json`, after independent
checksum verification. Default clone creates a benchmark **0.5.0** MLWE scaffold.
The package version **0.5.1** differs from its benchmark version. `mldsafail run`
and `make bench` now execute public MLWE development with a required ledger,
hypothesis, mechanism, parent revision and model. Run `mldsafail run --help`.
Historical 0.4.0 execution is unsupported archival tooling; new submissions
and clone choices exclude it. Previously retained archives still describe their
original artifact and must not be relabeled with successor behavior.

## Contestant contract and scoring

Edit only a separate approved Python-source contestant directory, at most 2 MB,
containing `solver.py` exporting `solve(public_instance)`. Public input supplies
fixed tiny-profile ring/dimension/eta, `A`, `t` and instance ID. Return complete
bounded vectors as `{"tag":"recovered_secret","s1":s1,"s2":s2}`, or `None`.
Do not import generator/evidence state, inspect hidden seeds or cache answers.
Keep evaluator evidence outside and unavailable to the contestant workspace.

Frozen 0.5.0 performs one unscored warmup and exactly three measured executions
per case. All successful repetitions use median cooperative clock-scoped worker
CPU (`process_time`), with a one-microsecond floor, divided by the same-instance
frozen reference cost. The clock includes parsing, contestant loading, lazy
mathematical imports, solving and verification; it excludes container startup,
trusted adapter imports before the clock and final serialization.
An ordinary failure in any measured invocation assigns the whole case 60 seconds;
invalid answers make the run ineligible. Five equal-weight cell geometric means,
anchored 1% ties and the frozen profile/seed-cluster uncertainty rule apply.
Comparisons require the same compatible epoch/reference table/environment.
Cooperative timing is unsuitable as a hostile-code security boundary; proposed
0.6.0 host accounting is a separate unadopted contract, not this package's score.
Full frozen details are in [the included contract](docs/PRIMITIVE_SELECTION_SPEC.md).

## Local MLWE validation and reproduction

A compatible reviewed Linux worker image and Docker are required for MLWE CPU
evaluation. The initial lock targets Linux ARM64; the independently reviewed
Linux amd64 image uses a distinct environment/epoch. Interpreter/library/image/
host identities must match the epoch. Obtain the reviewed image/source artifact
from the approved release channel; this participant archive does not contain
worker image layers and does not silently select another architecture.

Installation checks stop at CLI help, cloning and public fixture verification.
Use `mldsafail run --help` to inspect the required public-development metadata
without executing a solver. Public development requires a ledger, hypothesis,
mechanism, parent revision and model, plus the compatible reviewed worker.

Evaluation, epoch creation, auditing, ranking and hosted submission are later,
separately authorized operations. Do not create an epoch as an installation test.
Keep evaluator nonces, seeds, witnesses and raw evidence outside the contestant
workspace. Public fixtures support input/correctness checks; installation on a
local machine establishes no native amd64 or timing acceptance.

## Authorized hosted submission

After obtaining a short-lived scoped token from the approved server, configure
CLI login without placing credentials in a public transcript. Freeze an immutable
public GitHub commit containing the Python solver directory, record a falsifiable
hypothesis, and select the approved epoch/version explicitly:

```sh
NEW_INSTALL_DIRECTORY/bin/mldsafail submit --server APPROVED_SERVER \
  --repo PUBLIC_GITHUB_REPOSITORY --commit FULL_COMMIT_SHA \
  --benchmark-version 0.5.0 --epoch-id APPROVED_EPOCH_ID \
  --solver-path REPOSITORY_RELATIVE_SOLVER_DIRECTORY \
  --hypothesis FALSIFIABLE_HYPOTHESIS --idempotency-key RECORDED_UNIQUE_KEY
NEW_INSTALL_DIRECTORY/bin/mldsafail status SUBMISSION_ID --server APPROVED_SERVER
NEW_INSTALL_DIRECTORY/bin/mldsafail logs SUBMISSION_ID --server APPROVED_SERVER
NEW_INSTALL_DIRECTORY/bin/mldsafail cancel SUBMISSION_ID --server APPROVED_SERVER
```

Preserve the idempotency key. Reconcile a lost submission response by replaying
the same request/key or querying its known submission; never blindly generate a
new key. Follow retry status and retained logs; infrastructure failure is distinct
from scored ordinary failure. Leaderboards compare matching benchmark/epoch/
environment cohorts, not historical 0.4.0 and not future 0.6.0 results.
