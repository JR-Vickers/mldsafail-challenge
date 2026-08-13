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

Parameters need to correspond to a valid standardized ML-DSA
parameter set.

# 4. Instance Generator

All optimization experiments should begin with instances produced by a
repository-controlled generator.

Suggested interface:

```python
instance = generate_instance(
    seed=12345,
    profile="medium",
)

```

## Optimization Workflow

Ordinary optimization work is limited to `src/mldsafail/solver/` and
`src/mldsafail/math/`. Treat the following as benchmark-defining and do not
change them during a solver experiment:

- `config/`
- the evaluator deployment's hidden-seed secret
- `src/mldsafail/trusted/`
- `src/mldsafail/benchmark/`

For each experiment:

1. Activate the environment with `source .venv/bin/activate`.
2. Start from the current best commit and record a concrete hypothesis.
3. Run `make test` and `make bench` before editing to establish the baseline.
4. Make the smallest solver or math change that tests the hypothesis.
5. Run tests and the public suite. Run the full suite only after a public gain.
6. Keep a change only if it remains correct, stays within resource limits, and lowers the full-suite headline score.
7. Record successful and failed experiments; revert regressing code, not the
   evidence that the experiment occurred.
8. Commit validated checkpoints with a message describing the hypothesis.

Never special-case known seeds, inspect hidden diagnostic state, fabricate
cost counters, skip verification, or weaken difficulty and scoring. Escalate
before changing benchmark semantics, the safety boundary, or score meaning.

## Completion Checks

Before handing off a change, run the most relevant focused tests plus:

```sh
make check
```

Do not push commits. The repository owner handles publication.
