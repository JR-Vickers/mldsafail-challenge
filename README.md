# mldsa.fail challenge

`mldsa.fail` is a local research benchmark for measuring how effectively coding agents improve algorithms over small, synthetic lattice problems. ML-DSA provides mathematical inspiration, but this repository is an optimization challenge—not a key-recovery or signature-forgery tool.

The MVP closes a reproducible loop: generate a deterministic toy instance, solve it, verify the candidate independently, measure resources, append the experiment record, and display progress locally.

## Quick start

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are required.

```sh
uv sync --extra dev
source .venv/bin/activate
make test
make bench
make web-smoke
make web
```

The dashboard starts at `http://127.0.0.1:5000`. It reads `results/experiments.jsonl`; set `MLDSAFAIL_RESULTS_PATH=/path/to/other.jsonl` to inspect another result log.

## Commands

```sh
make test                         # unit and integration tests
make bench                        # public deterministic benchmark
make check                        # tests plus a toy-small benchmark smoke run
make web                          # local experiment dashboard
make web-smoke                    # non-blocking dashboard route smoke test

python -m mldsafail.benchmark.runner --profile toy-medium
python -m mldsafail.benchmark.runner --profile toy-medium --seed 12345
python -m mldsafail.benchmark.runner --suite full
python -m mldsafail.benchmark.runner --profile toy-small --no-record
```

`make bench` appends a public-suite experiment to the default JSONL log. `make check` and `make web-smoke` do not append a result or leave a server running, so they are suitable for automated validation. The diagnostic `--seed` form requires `--profile`; use `--output PATH` to append to another log and `--no-record` to print without writing.

### Record an official comparison

Official comparisons use every public and hidden profile, a clean committed tree, and the frozen trusted-input fingerprint. Confirm the current fingerprint:

```sh
uv run python -c 'from mldsafail.benchmark.integrity import compute_trusted_fingerprint; print(compute_trusted_fingerprint())'
```

For the current benchmark contract, record a run with:

```sh
uv run python -m mldsafail.benchmark.runner \
  --suite full \
  --baseline-fingerprint 2cc9c58633fe20dbeea06f243b638b61b72c19293210a5ad91e4142e4fc69b00 \
  --agent codex \
  --model gpt-5 \
  --hypothesis "describe the tested change" \
  --tag algorithm \
  --notes "describe the measured outcome"
```

If the computed fingerprint differs, do not reuse the example value: review the trusted-file changes and establish a new benchmark baseline. The dashboard ranks full public-plus-hidden records together and never uses a custom, smoke, or public-only run to calculate their headline improvement.

The full suite includes the repository's separated hidden seeds. They discourage seed-specific optimization; they are not intended to be secret from a local repository owner.

## Benchmark model

Only fixed, bounded profiles in `config/toy_profiles.toml` can generate instances. The solver receives public `ToyInstance` data and an instrumented cost counter. Diagnostic planted data stays within trusted generation code. A separate verifier decides whether a candidate is valid; invalid candidates receive no scored result.

Successful results retain a full vector rather than a single opaque score:

- total and median wall-clock runtime;
- peak memory;
- solution quality;
- versioned abstract counts for arithmetic, reduction, basis updates, and memory access.

Public and hidden suites use fixed seeds from the same generator distribution. Environment, command, revision, hypothesis, verification outcome, and per-profile results are recorded in append-only JSONL. See [experiments/README.md](experiments/README.md) for the record format and [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) for the keep-or-revert workflow.

## Safety boundary

All executable experiments operate on deliberately small instances produced by this repository. The program does not accept public keys, signatures, arbitrary matrices, custom modulus/dimension combinations, or production ML-DSA parameters as solver targets.

Do not use this project to recover real secret keys, forge signatures, search for vulnerable keys, target deployed systems, or remove the toy restrictions to attack practical parameters. Work involving real ML-DSA should remain specification study, official correctness vectors, asymptotic analysis, or theoretical resource estimation.

## Repository map

```text
config/                    fixed, bounded toy profiles
data/                      public and hidden benchmark seeds
src/mldsafail/trusted/     generator and independent verifier
src/mldsafail/solver/      baseline and future optimized solvers
src/mldsafail/math/        toy arithmetic and linear algebra
src/mldsafail/benchmark/   runner, metrics, records, integrity checks
src/mldsafail/web/         read-only local results dashboard
tests/                     correctness, safety, benchmark, and web tests
results/experiments.jsonl  append-only research history (generated)
experiments/               experiment schema documentation
```

## Agent workflow

Optimization agents should edit `solver/` and `math/` by default. Generator, verifier, profile caps, seeds, scoring, and integrity code define the challenge and must not change during an optimization experiment.

For each hypothesis: record the current baseline, make one focused change, run tests and the public suite, run the hidden suite only after a public improvement, then retain only a correctness-preserving Pareto improvement. Revert regressing code but keep its failed experiment record. Make descriptive checkpoint commits; do not push automatically.

The full product intent and acceptance criteria are in [docs/PLAN.md](docs/PLAN.md).
