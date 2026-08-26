# mldsa.fail challenge

`mldsa.fail` is a local and hosted research benchmark for competing implementations
on small, synthetic lattice problems inspired by ML-DSA. The core research question is
which isolated cryptanalytic primitive is the most useful proxy for attacking tiny
ML-DSA-like lattice instances; the benchmark is primitive-agnostic at the top level and
measures how efficiently a submitted solver can solve a given profile on deterministic
toy instances. ML-DSA provides mathematical inspiration, but this repository is an
optimization challenge—not a key-recovery or signature-forgery tool.

Offline use remains account-free and JSONL-backed. The hosted product accepts immutable public GitHub commits, evaluates only eligible solver/math source in disposable rootless Docker workers, and publishes scores created by the trusted server.

## Quick start

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are required.

```sh
uv sync --extra dev
source .venv/bin/activate
make test
make bench
make web-smoke
make web
mldsafail run --profile small --no-record
```

The dashboard starts at `http://127.0.0.1:5000`. It reads `results/experiments.jsonl`; set `MLDSAFAIL_RESULTS_PATH=/path/to/other.jsonl` to inspect another result log. For the local hosted stack, run `make hosted-dev` and open `http://localhost:8080`.

### Hosted stack (local prototype)

```sh
make hosted-setup   # one-time: create the dev hidden-seeds file (mode 0400)
make hosted-dev     # start Postgres, web, Caddy proxy, and the coordinator
make hosted-down    # tear down the hosted stack
```

`make hosted-setup` is idempotent and safe to re-run. It copies `deploy/dev-hidden-seeds.json` into the evaluator work directory (default `/Users/jarrett/dev/mldsafail-evaluator`; override with `HOSTED_EVALUATOR_DIR`) and sets mode 0400. The coordinator requires this file at startup.

`make hosted-dev` now starts all four services — database, web, proxy, and coordinator — in one command. The coordinator polls PostgreSQL for queued submissions, acquires the participant's git commit, validates eligible solver/math source, assembles a trusted harness, and spawns an isolated Docker worker to evaluate it. Dev evaluations are tagged with `evaluator_fingerprint=development` and `hidden_suite_version=development-public-fixture`; they are a local prototype cohort and are not production results.

Docker Desktop must be running on macOS for the coordinator to spawn workers.

## Commands

```sh
make test                         # unit and integration tests
make bench                        # public deterministic benchmark
make check                        # tests plus a small-profile benchmark smoke run
make web                          # local experiment dashboard
make web-smoke                    # non-blocking dashboard route smoke test

python -m mldsafail.benchmark.runner --profile medium
python -m mldsafail.benchmark.runner --profile medium --seed 12345
MLDSAFAIL_HIDDEN_SEEDS_PATH=/secure/hidden.json mldsafail run --suite full
python -m mldsafail.benchmark.runner --profile small --no-record
```

`make bench` appends a public-suite experiment to the default JSONL log. `make check` and `make web-smoke` do not append a result or leave a server running, so they are suitable for automated validation. The diagnostic `--seed` form requires `--profile`; use `--output PATH` to append to another log and `--no-record` to print without writing.

### Record an official comparison

Official comparisons use every public and hidden profile, a clean committed tree, and the frozen trusted-input fingerprint. Confirm the current fingerprint:

```sh
uv run python -c 'from mldsafail.benchmark.integrity import compute_trusted_fingerprint; print(compute_trusted_fingerprint())'
```

For a maintainer comparison, inject the server-only suite and use the reviewed
fingerprint for that release:

```sh
MLDSAFAIL_HIDDEN_SEEDS_PATH=/secure/hidden.json \
uv run python -m mldsafail.benchmark.runner \
  --suite full \
  --baseline-fingerprint REVIEWED_FINGERPRINT \
  --agent codex \
  --model gpt-5 \
  --hypothesis "describe the tested change" \
  --tag algorithm \
  --notes "describe the measured outcome"
```

If the computed fingerprint differs, do not reuse the example value: review the trusted-file changes and establish a new benchmark baseline. The dashboard ranks full public-plus-hidden records together and never uses a custom, smoke, or public-only run to calculate their headline improvement.

The 0.3.0 contract removed hidden seeds from the repository and package. Public runs remain fully offline; hidden/full runs are maintainer-only and require `MLDSAFAIL_HIDDEN_SEEDS_PATH`. Hosted results are separated into cohorts by benchmark version, evaluator fingerprint, hidden-suite version, and worker class.

## Hosted CLI

Create a token in the signed-in web UI, then use the unified command:

```sh
mldsafail login TOKEN --server https://mldsa.fail
mldsafail submit --repo https://github.com/OWNER/REPO --commit FULL_40_CHAR_SHA --hypothesis "reduce basis updates"
mldsafail status SUBMISSION_ID --follow
mldsafail logout
```

The secret is stored in the operating-system credential store. A mode-0600 file fallback requires explicit `--allow-plaintext-storage` opt-in. See [docs/OPERATIONS.md](docs/OPERATIONS.md) for TLS, OAuth, deployment, migration, backup/restore, hidden-suite rotation, rollback, and incident response.

## Benchmark model

Only fixed, bounded profiles in `config/profiles.toml` can generate instances. The solver receives public `ChallengeInstance` data and a trusted operation meter. Diagnostic planted data stays within trusted generation code. A separate verifier decides whether a candidate is valid; invalid or over-limit candidates receive no score. See [docs/CHALLENGE.md](docs/CHALLENGE.md) for the frozen contract.

The lowest valid headline score wins. It is the versioned weighted operation cost across the selected suite. Successful results also retain diagnostics:

- total and median wall-clock runtime;
- peak memory;
- solution quality;
- versioned abstract counts for arithmetic, reduction, basis updates, and memory access.

Public and hidden suites use fixed seeds from the same generator distribution. Environment, command, revision, hypothesis, verification outcome, and per-profile results are recorded in append-only JSONL. See [experiments/README.md](experiments/README.md) for the record format and [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) for the keep-or-revert workflow.

## Safety boundary

All executable experiments operate on deliberately small instances produced by this repository. The program does not accept public keys, signatures, arbitrary matrices, custom modulus/dimension combinations, or production ML-DSA parameters as solver targets.

Do not use this project to recover real secret keys, forge signatures, search for vulnerable keys, target deployed systems, or remove the restrictions to attack practical parameters. Work involving real ML-DSA should remain specification study, official correctness vectors, asymptotic analysis, or theoretical resource estimation.

## Repository map

```text
config/                    fixed, bounded profiles
data/                      public benchmark seeds only
src/mldsafail/trusted/     generator and independent verifier
src/mldsafail/solver/      reference, balanced, and lazy-frontier solvers
src/mldsafail/math/        arithmetic and linear algebra
src/mldsafail/benchmark/   runner, metrics, records, integrity checks
src/mldsafail/web/         local dashboard and hosted web/API
src/mldsafail/evaluator/   source validation, queue, coordinator, worker
tests/                     correctness, safety, benchmark, and web tests
results/experiments.jsonl  append-only research history (generated)
experiments/               experiment schema documentation
```

## Agent workflow

Optimization agents should edit `solver/` and `math/` by default. Generator, verifier, profile caps, seeds, scoring, and integrity code define the challenge and must not change during an optimization experiment.

For each hypothesis: record the current baseline, make one focused change, run tests and the public suite, run the hidden suite only after a public score improvement, then retain only a correctness-preserving full-suite score improvement within the fixed resource limits. Revert regressing code but keep its failed experiment record. Make descriptive checkpoint commits; do not push automatically.

The full product intent and acceptance criteria are in [docs/PLAN.md](docs/PLAN.md).
