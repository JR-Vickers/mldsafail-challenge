PLAN.md

1. Project Goal

Build an end-to-end local MVP of mldsa.fail, inspired by ecdsa.fail, around a precisely defined optimization challenge over deliberately small, synthetic lattice problems motivated by ML-DSA.

The primary scientific question is:

How far can we reduce the cost of the best-known valid solution to a fixed lattice/PQC challenge?

The cryptographic optimization problem is the subject of the benchmark. Humans and coding agents are the research machinery: they should be able to modify the implementation, run a hardened verifier, measure one objective score, and contribute validated improvements to a shared frontier. How agents conduct research may later be studied from the resulting history, but it is not the benchmark's central question.

The first version should prioritize the ecdsa.fail-like kernel over visual polish or elaborate orchestration:

editable algorithm → immutable harness → rigorous verifier → one meaningful score → baseline → autoresearch loop → frontier

This is a three-day build designed for both human and agent contributors. Optimize for a concrete challenge contract, strong tests, reproducibility, and fast independent iteration.

2. MVP Success Criteria

The MVP is complete when a local user can:

Read a precise statement of the challenge, validity conditions, fixed evaluation suite, and score.

Generate deterministic challenge instances.

Run a baseline solver over them.

Verify candidate outputs with an independent verifier.

Measure performance and resource usage.

Save each experiment as structured data.

Compare a new run against the current best result.

Display benchmark progress in a local web UI.

Run the full stack on a MacBook Pro M4 Max without external compute.

Give a human or coding agent the repository and let them safely iterate on the solver without needing changes to the harness.

A minimal happy path should look like:

generate instances
    ↓
run baseline
    ↓
verify outputs
    ↓
measure score
    ↓
record experiment
    ↓
researcher edits solver
    ↓
rerun benchmark
    ↓
keep improvement or revert
    ↓
display progress on website

3. Scope

In scope for the MVP

Synthetic, deterministic lattice challenge generation.

Small module-lattice-inspired problem instances.

A correct but intentionally unsophisticated baseline solver.

Independent verification.

Reproducible benchmarking.

Wall-clock timing.

Peak memory measurement.

One versioned abstract algorithmic cost metric for ranking valid results.

Structured experiment logs.

Hidden-seed evaluation.

Basic regression protection.

A local leaderboard / record view.

A progress-over-time chart.

Contributor documentation designed for both humans and coding agents.

A single headline score and a best-known-score frontier.

Local-first execution.

Explicitly out of scope

Recovering production ML-DSA secret keys.

Forging ML-DSA signatures.

Accepting arbitrary third-party keys or signatures as attack targets.

Internet-scale target collection.

Production cryptanalytic tooling.

Distributed compute infrastructure.

Cloud orchestration.

User accounts.

Payments.

Highly polished branding.

Perfect cryptographic fidelity to standardized ML-DSA parameter sets.

A production deployment pipeline.

Agent taxonomy, model comparison, multi-agent tournaments, or orchestration research.

4. Safety Model

The executable benchmark should be structurally limited to repository-generated instances.

The safety boundary should be enforced in code, not merely documented.

Required controls

Challenge profiles are fixed and bounded.

Arbitrary cryptographic parameter input is rejected.

The benchmark runner accepts generated instance IDs or seeds, not public keys.

The solver interface consumes the repository's internal instance schema.

Production ML-DSA parameter sets are not exposed as executable attack profiles.

External public keys and signatures are never accepted as solver targets.

If real ML-DSA mathematics is referenced, use it for:

structural inspiration;

specification study;

correctness examples;

resource estimation;

asymptotic comparison.

5. Core Benchmark Design

The first product decision is the challenge contract. Before optimization begins, freeze and document:

the mathematical problem;

the fixed, bounded instance distribution;

the candidate-output contract;

the validity conditions;

the evaluation suite;

the primary cost metric and aggregation rule.

The benchmark should capture a meaningful ML-DSA-motivated structure while remaining clearly separated from production cryptanalysis. It must be specific enough that two independent implementations receive the same validity decision and score.

Define a clean solver contract:

candidate = solve(instance)

and a separate verifier contract:

result = verify(instance, candidate)

The verifier defines correctness.

First benchmark family

Use a planted short-vector / bounded-distance synthetic lattice problem.

The generator should:

Sample a deterministic seed.

Construct a small lattice or module-lattice-like object.

Plant a known short relation or vector.

Produce the public challenge instance.

Retain diagnostic metadata separately.

Allow correctness to be checked from the challenge relation itself where possible.

The exact search problem and acceptance bound must be finalized during Day 1 rather than left as a family of loosely related experiments. Once the baseline is published, changing them creates a new benchmark version.

This gives researchers a genuine algorithmic search space without requiring interaction with real cryptographic keys.

6. Difficulty Profiles

Start with three fixed profiles:

small
medium
large

The exact parameters can be tuned during implementation.

Example configuration shape:

[small]
dimension = 16
modulus = 97

[medium]
dimension = 32
modulus = 257

[large]
dimension = 48
modulus = 769

These values are placeholders.

The important requirements are:

deterministic generation;

fast enough for repeated local iteration;

increasing difficulty;

enough headroom for optimization;

well below practical cryptographic attack sizes.

Keep all profile caps in one file:

config/profiles.toml

Changing those caps should not count as an optimization.

7. Scoring

Correctness is binary and comes first.

An invalid output receives no benchmark score.

Every valid run receives one deterministic headline score. For the MVP, the score is the total versioned abstract operation cost across the fixed evaluation suite, minimized. The exact operation weights and suite aggregation must be explicit, tested, and frozen with the benchmark version before optimization begins.

Wall-clock time, peak memory, solution quality, and individual operation counts remain visible diagnostics. They help explain improvements and expose unacceptable resource tradeoffs, but they do not create competing definitions of the winner.

Required metrics

correctness;

headline score;

total weighted abstract operation cost;

total wall-clock time;

median per-instance runtime;

peak memory;

solution quality;

abstract operation counts by category.

Optional metrics

modular multiplications;

basis updates;

reductions;

memory reads/writes;

branch count;

estimated bit complexity.

Leaderboard philosophy

Lowest valid headline score wins. Store the full diagnostic vector, but rank submissions and plot progress using the primary score only. If the score later proves scientifically inadequate, revise it through an explicit benchmark-version change and establish a new baseline; do not silently substitute a Pareto frontier or an ad hoc formula.

8. Abstract Cost Model

Implement a lightweight instrumented cost model early.

For example:

from dataclasses import dataclass

@dataclass
class Cost:
    additions: int = 0
    multiplications: int = 0
    modular_reductions: int = 0
    basis_updates: int = 0
    memory_reads: int = 0
    memory_writes: int = 0

The purpose is to provide the hardware-independent headline score and distinguish:

genuine algorithmic improvement;

implementation optimization;

hardware-dependent speedup.

The cost model, weights, aggregation rule, and instrumentation boundary must be documented and versioned. Counters must be produced by trusted instrumentation or otherwise protected against candidate fabrication.

9. Repository Architecture

Recommended layout:

.
├── AGENTS.md
├── PLAN.md
├── README.md
├── pyproject.toml
│
├── config/
│   └── profiles.toml
│
├── src/
│   ├── math/
│   │   ├── modular.py
│   │   ├── polynomial.py
│   │   └── lattice.py
│   │
│   ├── solver/
│   │   ├── baseline.py
│   │   └── optimized.py
│   │
│   ├── benchmark/
│   │   ├── runner.py
│   │   ├── metrics.py
│   │   ├── cost_model.py
│   │   └── records.py
│   │
│   └── web/
│       ├── app.py
│       ├── templates/
│       └── static/
│
├── trusted/
│   ├── generator.py
│   └── verifier.py
│
├── tests/
│   ├── test_math.py
│   ├── test_generator.py
│   ├── test_verifier.py
│   ├── test_solver.py
│   └── test_benchmark.py
│
├── experiments/
│   └── README.md
│
├── data/
│   ├── public_seeds.json
│   └── hidden_seeds.json
│
└── results/
    └── experiments.jsonl

The exact framework choices are flexible. Prefer the simplest stack that runs cleanly on macOS and is easy for coding agents to understand.

10. Trusted vs. Editable Code

Separate benchmark infrastructure from the code being optimized.

Trusted

trusted/
src/benchmark/
config/
data/hidden_seeds.json

These define the challenge.

Agent-editable by default

src/solver/
src/math/

Agents may modify other areas when necessary for legitimate engineering work, but ordinary optimization runs should focus on solver and mathematical implementation code.

The verifier should not be modified during solver optimization.

11. Experiment Storage

Use append-only JSONL for the first version.

Example:

{
  "experiment_id": "2026-08-12-0017",
  "timestamp": "2026-08-12T13:40:00+08:00",
  "parent_commit": "abc123",
  "commit": "def456",
  "agent": "codex",
  "hypothesis": "cache repeated Gram-Schmidt state",
  "benchmark_version": "0.1.0",
  "correct": true,
  "score": 934128,
  "runtime_seconds": 1.82,
  "peak_memory_mb": 214,
  "abstract_cost": 934128,
  "profiles": {
    "small": {},
    "medium": {},
    "large": {}
  },
  "notes": "Improves medium and large profiles."
}

Do not start with a database unless the JSONL approach becomes genuinely limiting.

12. Benchmark Commands

Create a very small command surface.

Target commands:

# run tests
pytest

# run public benchmark
python -m src.benchmark.runner

# run one profile
python -m src.benchmark.runner --profile medium

# run with an explicit seed
python -m src.benchmark.runner --profile medium --seed 12345

# run full evaluation
python -m src.benchmark.runner --suite full

# start local website
python -m src.web.app

If practical, add convenience commands:

make test
make bench
make web
make check

Agents should not need to memorize a complicated workflow.

13. Public and Hidden Evaluation

Use two seed sets.

Public seeds

Visible to the agent and used for development.

Hidden seeds

Used only by the official evaluation command.

Both must come from the same documented generator distribution.

This protects against:

seed-specific hacks;

lookup tables;

accidental overfitting;

brittle special cases.

The hidden suite does not need sophisticated secrecy in the local MVP. It only needs enough separation to make benchmark gaming obvious.

14. Testing Strategy

Tests are part of the benchmark, not optional cleanup.

Arithmetic tests

Test:

modular addition;

modular multiplication;

inverses where applicable;

polynomial arithmetic;

matrix/vector operations;

lattice relation checks.

Generator tests

Verify:

same seed → same instance;

different seed → different instance;

profile limits are enforced;

malformed profiles fail;

arbitrary oversized parameters cannot be injected.

Verifier tests

Verify:

known-valid candidates pass;

mutated candidates fail;

malformed outputs fail;

empty outputs fail;

edge cases are handled deterministically.

Solver tests

Verify:

smoke instances are solved;

solver cannot access planted secret state;

deterministic mode is reproducible.

Benchmark tests

Verify:

scores are calculated consistently;

invalid outputs receive no score;

metrics are recorded;

experiment records serialize correctly.

15. Baseline Solver

The first solver should be intentionally clear and unsurprising.

Do not try to start with the best algorithm available.

Its job is to provide:

a correctness reference;

measurable inefficiencies;

optimization headroom;

readable code for agents.

The baseline should contain obvious opportunities such as:

repeated calculations;

straightforward data structures;

conservative precision;

simple branching;

non-incremental updates.

Do not artificially sabotage it. It should be a competent reference implementation, just not highly optimized.

Tag the first validated result:

baseline-v1

16. Autoresearch Optimization Loop

The repository should make repeated scientific iteration easy for humans, coding agents, and mixed teams. Autoresearch is a core operating mechanism, not the object being scored.

Each experiment should follow:

A. Baseline

Run the current benchmark and record the current best result.

B. Hypothesis

Write one concrete hypothesis.

Example:

Repeated Gram-Schmidt recomputation dominates large runtime.
Caching and incrementally updating the orthogonal basis should reduce
both wall time and abstract operation count.

C. Patch

Implement the smallest reasonable change.

D. Test

Run unit and regression tests.

E. Benchmark

Run all public profiles.

F. Hidden evaluation

If public results improve, run the hidden suite.

G. Decision

If the change:

breaks correctness → revert;

exceeds a fixed resource limit → reject as unscored;

lowers the headline score → keep and advance the shared best implementation;

does not lower the headline score → do not advance the shared best implementation.

H. Record

Append the result to results/experiments.jsonl.

Failed experiments should still be recorded.

17. Collaborative Git Workflow

Keep the history easy to audit.

Recommended pattern:

main
 └── experiment/<researcher>/<timestamp>

For each serious experiment:

Start from current best commit.

Create an experiment branch.

Implement one hypothesis.

Run tests.

Run benchmark.

Record result.

Commit.

Merge only validated improvements.

Commit messages should describe the hypothesis, not merely the edited file.

Good:

perf: cache incremental orthogonalization state

Bad:

update solver.py

18. Frontend

The first frontend should emulate the structure of ecdsa.fail more than its exact branding.

Do not spend the first day tuning colors, fonts, or logos.

Homepage sections

Hero

Example:

mldsa.fail

How low can we drive the cost of this
post-quantum lattice challenge?

Current improvement: 37.4%

Progress bar / frontier

Show:

baseline ───────── challenge start ───────── current record

Current record

Lead with the lowest valid headline score and its improvement from baseline. Show runtime, memory, solution quality, and operation categories as supporting diagnostics.

Improvement history

A chart:

best known score
↑
│        ●
│    ●
│  ●
│ ●
└────────────────────→ experiment

Each point should link to its experiment record.

Recent experiments

Show:

timestamp;

researcher or agent;

hypothesis;

result;

delta;

commit.

Methodology

Short explanation of:

instances;

verifier;

scoring;

hidden evaluation;

safety boundary.

19. Local Web Stack

Choose simplicity over architectural sophistication.

Good MVP options include:

Python + FastAPI/Flask + server-rendered templates;

a tiny static frontend that reads generated JSON;

another minimal framework if it materially reduces implementation time.

Avoid creating:

a separate frontend deployment pipeline;

a complex API layer;

authentication;

stateful backend services;

unless a concrete requirement appears.

For a local MVP, the experiment log itself can be the datastore.

20. Website Data Flow

Prefer:

results/experiments.jsonl
          ↓
      parser
          ↓
   derived records
          ↓
      web view

Derived values should include:

current best;

baseline delta;

headline-score frontier;

recent experiments;

diagnostic metrics for the current record;

cumulative improvement.

Keep these calculations deterministic and testable.

21. Three-Day Build Plan

Day 1 — Make the benchmark real

Primary goal: freeze the scientific challenge and produce its first verified score.

Build:

project skeleton;

precise challenge statement and solver contract;

profiles;

deterministic generator;

mathematical primitives;

verifier;

baseline solver;

benchmark runner;

metrics;

one versioned headline-score formula;

basic tests;

experiment JSONL writer.

End-of-day target:

python -m src.benchmark.runner

produces a verified, reproducible baseline result.

Do not prioritize the frontend until this works.

Day 2 — Make autoresearch productive

Primary goal: humans and coding agents can make and validate meaningful improvements without modifying the benchmark contract.

Build:

stronger test coverage;

hidden-seed suite;

cost instrumentation;

regression comparison;

simple experiment workflow;

automatic result recording;

best-result detection;

benchmark-integrity checks;

clear editable/trusted boundaries.

Then begin human- and agent-driven optimization runs.

End-of-day target:

multiple recorded experiments;

at least one validated improvement over baseline;

failed experiments preserved;

hidden evaluation working.

Day 3 — Make it legible and compelling

Primary goal: turn the research loop into a convincing local demonstration.

Build:

homepage;

headline improvement metric;

historical progress chart;

records view;

experiment detail view;

headline-score frontier;

methodology section;

basic ecdsa.fail-inspired layout;

README;

one-command local startup.

Spend remaining time on:

additional human- or agent-driven optimization runs;

bug fixing;

documentation;

presentation polish.

End-of-day target:

make web

opens a complete local demo showing the baseline, the best-known valid solution, and the history of improvements to the challenge.

22. Parallel Workstreams

Once the benchmark contract stabilizes, human and agent contributors can work in parallel.

Suggested tracks:

Track A — Mathematics

Improve:

lattice data structures;

basis operations;

reduction algorithms;

numerical stability.

Track B — Solver optimization

Explore:

caching;

incremental updates;

pruning;

heuristics;

ordering;

precision reduction;

memory reuse.

Track C — Benchmark infrastructure

Improve:

instrumentation;

profiling;

deterministic execution;

regression detection;

result comparison.

Track D — Web UI

Implement:

homepage;

history chart;

record cards;

experiment pages.

Do not parallelize work that changes the benchmark contract until that contract is stable.

23. Benchmark Integrity Checks

The benchmark should explicitly fail if an optimization attempts to:

alter expected answers;

weaken the verifier;

delete hard seeds;

special-case official seeds;

inspect hidden solution metadata;

fabricate resource counters;

alter the scoring formula;

skip verification;

silently change profile difficulty.

Where practical, hash or otherwise fingerprint trusted benchmark files before an optimization run and report changes.

This does not need to be adversarially secure. It needs to make accidental or unauthorized benchmark changes obvious.

24. Quantum Resource Estimation

Quantum work is a secondary track, not a requirement for the first functioning benchmark.

Once the classical loop works, add a resource-estimation module capable of representing quantities such as:

logical qubits;

Toffoli count;

T-count;

circuit depth;

reversible memory;

spacetime volume.

Keep four categories distinct:

classical experiment
quantum simulation
quantum resource estimate
extrapolation

Do not present one as another.

A useful eventual feature is to let researchers optimize an abstract reversible algorithm against a resource model without requiring a real quantum computer.

25. Secondary Research Opportunities

The experiment history may later support meta-research about how humans and agents search the design space: which improvements generalize, which approaches fail hidden evaluation, whether independent researchers rediscover the same techniques, and what helps progress resume after a plateau.

These are useful studies derived from the benchmark. They must not drive the MVP architecture, complicate the scoring objective, or displace work on the lattice challenge itself.

26. Experiment Classification

Use lightweight tags when they help contributors understand the technical history; do not build an elaborate taxonomy during the MVP.

Suggested tags:

algorithm
data-structure
caching
pruning
numerics
memory
vectorization
parallelism
compiler
heuristic
cost-model
verification
failed

Multiple tags may apply.

This keeps the optimization record searchable and can support later analysis without making agent behavior part of the score.

27. Performance Profiling

Before making low-level changes, gather evidence.

Useful profiling stages:

Whole benchmark timing.

Per-profile timing.

Per-instance timing.

Function-level profiling.

Allocation / memory profiling.

Abstract operation counts.

Contributors should optimize measured bottlenecks instead of guessing.

28. Reproducibility Metadata

Every official run should record:

git commit
benchmark version
Python version
dependency lock/hash
machine architecture
OS
profile
seed set
researcher and, when applicable, agent/model
run timestamp
command

Since development is local on Apple Silicon, record the machine architecture explicitly so wall-clock results are interpretable.

29. Failure Handling

A failed experiment is not a failed project event.

Store failures such as:

verifier failure;

timeout;

regression;

numerical instability;

memory explosion;

hidden-seed failure;

non-generalizing speedup.

The UI may eventually display them as part of the research history.

Failed results prevent duplicated work and document the evidence behind changes to the best-known implementation.

30. README Requirements

The README should eventually contain:

One-paragraph description.

Screenshot of the local site.

Quickstart.

Benchmark explanation.

Safety boundary.

Repository map.

How to run tests.

How to run benchmarks.

How experiments are recorded.

How to launch the site.

How agents should interact with the repo.

Link/reference to AGENTS.md.

Link/reference to PLAN.md.

Keep the README user-facing.

Keep operational agent rules in AGENTS.md.

Keep implementation sequencing here in PLAN.md.

31. Domain and Deployment

Use the project name:

mldsa.fail

for local branding from the beginning.

Do not make public deployment a prerequisite for the MVP.

The local project should avoid assumptions that prevent later deployment to mldsa.fail, but the first three-day sprint ends successfully even if everything runs only on localhost.

32. Decision Rules During the Sprint

When an implementation choice is ambiguous:

Prefer the option a new human or coding-agent contributor can understand.

Prefer deterministic behavior.

Prefer fewer dependencies.

Prefer explicit data structures.

Prefer testable interfaces.

Prefer local execution.

Prefer a working vertical slice over architectural completeness.

Defer visual refinement until the benchmark loop is stable.

Contributors are authorized to make routine solver implementation decisions without changing the trusted benchmark contract.

Escalate only when a decision changes:

benchmark semantics;

safety boundaries;

scoring meaning;

major project scope.

33. Definition of Done

The three-day MVP is done when all of the following are true:

Repository installs cleanly on the target Mac.

pytest passes.

Instances are deterministic.

Profiles are hard-bounded.

Baseline solver works.

Independent verifier works.

Public benchmark works.

Hidden evaluation works.

Metrics are recorded.

One versioned headline score determines the best-known valid result.

Experiment JSONL is append-only.

At least one optimization can be compared objectively against baseline.

Invalid solutions receive no score.

Benchmark corruption is detectable.

Local website starts with one command.

Website shows baseline, current best, and headline-score improvement.

Website shows progress over time.

Website shows recent experiments.

AGENTS.md gives coding agents clear operating rules.

PLAN.md describes architecture and build order.

README explains how to reproduce the demonstration.

34. Stretch Goals

Only pursue these after the vertical slice is solid.

Research

Optimization transfer across profiles.

Scaling-law analysis.

Analysis of independently rediscovered techniques.

Benchmarking

Multiple lattice challenge families.

Machine-independent normalized cost.

Statistical confidence intervals.

Automatic benchmark bisecting.

Quantum

Reversible arithmetic primitives.

Circuit-cost DSL.

Toffoli/T-count instrumentation.

Quantum resource frontier.

Web

Interactive experiment graph.

Patch diffs.

Public read-only leaderboard.

Live experiment feed.

Infrastructure

Parallel experiment workers.

Reproducible Nix/Docker environment.

CI benchmark checks.

None of these should delay the first end-to-end MVP.

35. Final Build Principle

The project should remain centered on one objectively scored scientific challenge and one observable loop:

editable algorithm
    ↓
candidate solution
    ↓
immutable verification
    ↓
headline score
    ↓
shared best-known frontier

Humans and agents advance that loop by forming hypotheses, changing code, and contributing evidence. Everything else exists to make the scientific optimization faster, more reliable, easier to audit, or easier to understand.

If a feature does not strengthen that loop during the MVP sprint, defer it.
