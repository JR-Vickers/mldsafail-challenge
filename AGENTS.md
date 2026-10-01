# AGENTS.md

## Behaviors
Make regular, descriptive git commits upon reaching sensible checkpoints.  Don't push them to main, let me do that manually.

## Project Overview

This repository is an experimental benchmarking platform inspired by
ECDSA.fail.

The project explores a question:

> How efficiently can automated research agents improve algorithms and
> implementations related to lattice-based cryptography when evaluated on
> small, synthetic, reproducible problem instances?

The long-term research interest is post-quantum cryptography, especially
ML-DSA/Dilithium-like lattice structures.

All executable cryptanalytic experiments must operate on deliberately small,
locally generated instances.

Think of this repository as:

- an optimization benchmark;
- an automated-research environment;
- a reproducibility harness;
- a leaderboard for algorithmic improvements;
- a way to study how coding/research agents search an algorithmic design space.

# 1. Primary Objective

Build a challenge environment in which an agent can repeatedly:

1. inspect the current implementation;
2. propose an algorithmic or implementation improvement;
3. modify the code;
4. run the benchmark;
5. verify correctness;
6. measure resource usage;
7. record the experiment;
8. keep improvements and revert regressions.

The benchmark should reward genuine algorithmic progress rather than
benchmark-specific hacks.

A successful system should eventually support runs resembling:

    baseline
       ↓
    agent proposes modification
       ↓
    implementation
       ↓
    deterministic benchmark
       ↓
    verification
       ↓
    score
       ↓
    experiment log
       ↓
    next iteration


# 2. Safety Boundary

This boundary is part of the project specification.

## Allowed

Agents may:

- generate synthetic lattice problem instances;
- implement mathematical operations on those instances;
- experiment with small-dimensional lattice reduction;
- implement generic linear algebra and polynomial arithmetic;
- compare reduction algorithms on instances;
- optimize memory usage;
- optimize runtime;
- optimize abstract operation counts;
- construct resource estimators;
- simulate algorithms;
- inspect NIST specifications;
- reproduce publicly documented examples;
- analyze asymptotic complexity;
- implement correctness verifiers;
- implement benchmark infrastructure;
- visualize optimization progress;
- compare theoretical attack-cost estimates;
- use official cryptographic test vectors for correctness testing.

## Not allowed

Agents must not:

- forge ML-DSA signatures;
- attack externally supplied cryptographic keys;
- attack externally supplied signatures;
- target deployed systems;
- search the Internet for vulnerable keys;
- ingest arbitrary third-party cryptographic targets;
- remove instance restrictions in order to attack practical parameters;
- turn the benchmark into a general-purpose ML-DSA cracking utility;
- provide automated exploitation against production cryptographic parameters.

If a proposed experiment crosses this boundary, replace it with either:

1. an instance experiment; or
2. a theoretical/resource-estimation experiment.


# 3. Relationship to ML-DSA

ML-DSA should be treated as the motivating cryptographic structure rather than
as a production target.

Use the NIST ML-DSA specification to understand concepts such as:

- module lattices;
- polynomial rings;
- matrix/vector structure;
- coefficient distributions;
- modular arithmetic;
- signature verification;
- parameter relationships.

Where useful, reproduce the *shape* of these mathematical objects at greatly
reduced dimensions.

For example, a configuration might use variables analogous to:

    q
    n
    k
    l
    eta

but with deliberately tiny values.

Parameters must remain within the adopted tiny-instance profiles in
[the frozen MLWE specification](docs/PRIMITIVE_SELECTION_SPEC.md). They are
structural analogues, not standardized ML-DSA parameter sets. Do not introduce
production ML-DSA parameters or claim production hardness from these experiments.

# 4. Instance Generator

All optimization experiments should begin with instances produced by a
repository-controlled generator.

Historical 0.4.0 generator interface:

```python
instance = generate_instance(
    seed=12345,
    profile="medium",
)

```

## Benchmark Versions and Optimization Workflow

The current research challenge and private staging use MLWE benchmark 0.5.0.
`make bench`, `mldsafail run`, and the development Compose stack retain historical
0.4.0 behavior. Read [PLAN.md](docs/PLAN.md),
[MLWE_LOCAL.md](docs/MLWE_LOCAL.md), and
[AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) before choosing a workflow.

For 0.5.0, edit only a separate contestant directory of approved Python source,
with `solver.py` exporting `solve(public_instance)`. Start from
`examples/mlwe/primal-lll/solver.py`. Keep private evidence outside the contestant
workspace and unavailable to the optimizer. The evaluator supplies only public
fixed-profile data; contestants must not import or access generator/evidence state.

For historical 0.4.0, ordinary optimization edits remain limited to
`src/mldsafail/solver/` and `src/mldsafail/math/`. Its `generate_instance` interface
above and operation-count scoring do not define the 0.5.0 contestant contract.

Benchmark-defining material must not change during any solver experiment:

- `config/` and all private seeds, nonces, epochs, and reference costs;
- `src/mldsafail/trusted/` and `src/mldsafail/benchmark/`;
- `src/mldsafail/benchmark_v050/`, evaluator code, worker images, and dependency locks.

For each experiment:

1. Activate the environment with `source .venv/bin/activate`.
2. Start from the selected baseline commit and record a falsifiable hypothesis,
   source identity, benchmark version, environment, and evaluation protocol.
3. Run tests and establish a public baseline before editing. For 0.5.0 use the
   development procedure in `docs/MLWE_PILOT.md`; `make bench` measures 0.4.0.
4. Make the smallest permitted contestant or historical solver/math change.
5. Run focused tests and the matching public suite. Public development scores
   are diagnostic; do not tune against private feedback.
6. Freeze a candidate selected from public evidence before an authorized private
   evaluation. For 0.5.0 use a fixed audited epoch and reference, sequential runs
   on the same idle host, and a predeclared comparison protocol. For 0.4.0 run
   the full suite only after a public gain.
7. Keep only changes that remain correct and within limits and improve the
   matching official score under the declared decision rule. In 0.5.0, crashes,
   timeouts, caps, and no-answer cases receive the frozen 60-second penalty;
   invalid answers make a run ineligible. Preserve failed/partial evidence.
8. Record successful and failed experiments; revert regressing code, not the
   evidence. Commit validated checkpoints without pushing.

Never special-case known seeds or identifiers, inspect hidden diagnostic state,
cache answers, fabricate cost counters or timings, skip verification, or weaken
difficulty/scoring. Escalate before changing benchmark semantics, safety, or score
meaning. Cooperative CPU timing is not a hostile-code measurement boundary;
public acceptance remains subject to the gates in `docs/PLAN.md`.

## Completion Checks

Before handing off a change, run the most relevant focused tests plus:

```sh
make check
```

Do not push commits. The repository owner handles publication.
