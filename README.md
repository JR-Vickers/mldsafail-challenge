# mldsa.fail challenge

`mldsa.fail` is a local and hosted optimization benchmark on deliberately small,
repository-generated lattice instances inspired by ML-DSA. The selected 0.5.0
challenge is Module-LWE bounded secret-and-error recovery. It studies how coding
agents improve complete solvers; it does not establish practical ML-DSA attack
costs or accept real keys, signatures, or arbitrary cryptographic targets.

As of 2026-10-01, primitive selection, local 0.5.0 acceptance, the optimization
pilot, and the single-host stability study are complete. Private staging has a
native authenticated submission-to-leaderboard result. Integrated failure/recovery
and rollback gates, automated off-host backups, public measurement integrity,
production setup, and an external pilot remain open. See
[PLAN.md](docs/PLAN.md), [staging status](docs/PRIVATE_STAGING_STATUS.md), and
[failure acceptance preparation](docs/acceptance/hosted-failures/README.md).

## Choose the benchmark version

| Workflow | Version and score |
|---|---|
| `mldsafail-mlwe` | Local 0.5.0, normalized complete-worker CPU against a fixed epoch reference |
| Private staging submissions | 0.5.0, compatible epoch/environment cohorts only |
| `make bench`, `mldsafail run`, local JSONL dashboard | Historical 0.4.0, versioned operation counts |
| `make hosted-dev` | Historical 0.4.0 development stack |
| `mldsafail clone`, submissions | Default 0.5.0; explicit `--benchmark-version 0.4.0` preserves historical behavior |

The participant package is 0.5.1; the current benchmark remains 0.5.0.
Scores from different versions, epochs, or environments cannot be ranked together.
Install only an owner-supplied release wheel after independently verifying its checksum:

```sh
sh scripts/install.sh RELEASE.whl VERIFIED_SHA256 NEW_INSTALL_DIRECTORY
export STAGING_SERVER=https://OWNER_CONFIGURED_PRIVATE_STAGING
mldsafail clone contestant-workspace
mldsafail login TOKEN --server "$STAGING_SERVER"
mldsafail submit --server "$STAGING_SERVER" --repo https://github.com/OWNER/REPO \
  --commit FULL_SHA --solver-path solver --hypothesis "..."
mldsafail status ID --server "$STAGING_SERVER" --follow
mldsafail logs ID --server "$STAGING_SERVER"
mldsafail cancel ID --server "$STAGING_SERVER"
```

Publish the workspace to public GitHub before submitting. Local MLWE development
uses [MLWE_PILOT.md](docs/MLWE_PILOT.md). Public launch remains an owner gate.

## Local 0.5.0 quick start

Use Python **3.12.10**, [uv](https://docs.astral.sh/uv/), and Docker. The commands
below use the original Linux ARM64 worker lock. Private staging uses the separately
reviewed Linux amd64 lock described in [HOSTED_V050.md](docs/HOSTED_V050.md).

```sh
uv sync --extra dev
source .venv/bin/activate
make check
python -m mldsafail.benchmark_v050.build
mldsafail-mlwe smoke --output /tmp/mlwe-smoke-new

mkdir contestant
cp examples/mlwe/primal-lll/solver.py contestant/solver.py
```

Every evaluation output directory must be new. Smoke is diagnostic. For private
epoch creation, complete contestant evaluation, independent audit, and ranking,
follow [MLWE_LOCAL.md](docs/MLWE_LOCAL.md). Keep private evidence outside the
contestant workspace and unavailable to optimization agents. Full epoch creation
and evaluation take longer than the historical small-profile check.

## 0.5.0 solver and score

A contestant directory contains only approved Python source, at most 2 MB, with
`solver.py` exporting `solve(public_instance)`. Return complete bounded vectors
`{"tag": "recovered_secret", "s1": s1, "s2": s2}`, or `None` if no answer was
found. The evaluator independently checks every coefficient bound and the full
ring equation. Instances use only the fixed tiny profiles; they are structural
analogues, not standardized ML-DSA parameter sets.

Each of the 100 ranked cases has one warmup and three measured fresh-container
executions. Successful case cost is median complete-worker CPU with a one-microsecond
floor. Ordinary timeouts, crashes, caps, and no-answer cases cost 60 seconds;
invalid answers make a submission ineligible. The score is the equally-cell-weighted
geometric mean of candidate/reference cost ratios, minimized. Anchored 1% ties and
the frozen bootstrap intervals apply. Partial evidence cannot rank.

Workers receive only public input and a read-only solver snapshot, with no network,
epoch, credentials, or Docker socket. The current timing adapter assumes cooperative
contestants. An enforceable measurement boundary remains required before untrusted
public submissions. The authoritative contract is
[PRIMITIVE_SELECTION_SPEC.md](docs/PRIMITIVE_SELECTION_SPEC.md).

## Private staging participation

Staging is reachable through the authorized maintainer SSH tunnel, with real GitHub
OAuth and participant-created tokens. It is not a publicly launched endpoint:

```sh
ssh -i ~/.ssh/mldsafail_vps -L 8080:127.0.0.1:8080 mldsafail@178.128.17.58
```

While the tunnel is open, sign in at `http://localhost:8080` and create a token.
The OAuth callback is `http://localhost:8080/auth/callback`. Submit an owner-published
public GitHub repository at a full immutable commit SHA:

```sh
mldsafail login TOKEN --server http://localhost:8080
mldsafail submit --repo https://github.com/OWNER/REPO --commit FULL_40_CHAR_SHA \
  --benchmark-version 0.5.0 --solver-path contestant \
  --hypothesis "describe the solver change"
mldsafail status SUBMISSION_ID --follow
mldsafail logout
```

`--solver-path` selects a repository-relative directory containing `solver.py`.
For the project reference example, use `examples/mlwe/primal-lll`. Optional
`--epoch-id` requires a particular cohort; `--idempotency-key` lets a retried
request reuse the same submission. The API supports logs and cancellation as
shown in [OPERATIONS.md](docs/OPERATIONS.md).

Tokens are stored in the operating-system credential store. A mode-0600 plaintext
fallback requires explicit `--allow-plaintext-storage` opt-in. Agents do not push
commits or publish fixtures; the owner handles publication.

## Historical 0.4.0 workflows

Historical offline use is account-free and JSONL-backed:

```sh
make test
make bench                         # public suite; appends an experiment
make web-smoke
make web                           # local JSONL dashboard at 127.0.0.1:5000
mldsafail run --profile small --no-record
```

Historical official comparisons require all public/hidden profiles, a reviewed
trusted fingerprint, and maintainer-only hidden seeds. See
[CHALLENGE.md](docs/CHALLENGE.md) and [AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md).
`make check` runs tests and a historical small-profile smoke without recording;
it does not replace MLWE epoch acceptance or native staging checks.

The historical local hosted prototype uses `make hosted-setup`, `make hosted-dev`,
and `make hosted-down`. Setup replaces the development hidden-seed fixture under
`HOSTED_EVALUATOR_DIR`; never point it at staging/production evidence. The stack
uses development credentials and differs from private staging's standalone Compose
configuration. See [OPERATIONS.md](docs/OPERATIONS.md).

## Safety and agent work

All executable experiments stay within repository-generated tiny instances. Do not
recover real keys, forge signatures, ingest third-party targets, target deployed
systems, or remove profile restrictions. Real ML-DSA work is limited to specification
study, official correctness vectors, asymptotic analysis, and resource estimates.

For 0.5.0, optimize a separate Python-only contestant workspace. For historical
0.4.0, edit `src/mldsafail/solver/` and `src/mldsafail/math/`. Preserve generators,
verifiers, profiles, private evidence, scoring, worker artifacts, and dependency
locks. Record hypotheses and failures, select candidates on public evidence, freeze
before authorized private validation, and retain only validated improvements under
the declared comparison rule. Follow [AGENTS.md](AGENTS.md) and
[AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md).

Key directories: `src/mldsafail/benchmark_v050/` (frozen MLWE contract),
`examples/mlwe/` (starters), `src/mldsafail/evaluator/` (hosted queue/evaluation),
`src/mldsafail/web/` (dashboard/API), `experiments/` (public/sanitized research
records), and `docs/acceptance/` (acceptance evidence).
