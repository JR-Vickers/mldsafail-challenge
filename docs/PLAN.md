PLAN.md

1. Project Goal

Build a finished, deployable mldsa.fail challenge product inspired by the participation model and presentation of ecdsa.fail, around a precisely defined optimization challenge over deliberately small, synthetic lattice problems motivated by ML-DSA.

The primary scientific question is:

How far can we reduce the cost of the best-known valid solution to a fixed lattice/PQC challenge?

The cryptographic optimization problem is the subject of the benchmark. Humans and coding agents are the research machinery: they should be able to modify the implementation, run a hardened verifier, measure one objective score, and contribute validated improvements to a shared frontier. How agents conduct research may later be studied from the resulting history, but it is not the benchmark's central question.

The product should preserve the ecdsa.fail-like kernel while supporting both frictionless local research and trustworthy public participation:

editable algorithm → local benchmark → authenticated submission → isolated immutable harness → rigorous verifier → one meaningful score → shared frontier

Build in deployable vertical slices designed for both human and agent contributors. Optimize for a concrete challenge contract, strong tests, reproducibility, safe evaluation of untrusted submissions, straightforward operations, and fast independent iteration.

2. Product Success Criteria

The product is complete when a contributor can:

Read a precise statement of the challenge, validity conditions, fixed evaluation suite, and score.

Generate deterministic challenge instances.

Run a baseline solver over them.

Verify candidate outputs with an independent verifier.

Measure performance and resource usage.

Save each experiment as structured data.

Compare a new run against the current best result.

Use the complete benchmark locally without an account.

Sign into the hosted website, create and revoke a named API token, authenticate the CLI, and submit a reproducible solver revision for official evaluation.

Receive queued, running, accepted, rejected, and failed submission status without trusting client-supplied scores.

Have the submitted solver evaluated in an isolated, resource-limited worker against server-controlled hidden inputs and the immutable benchmark contract.

Display the canonical leaderboard and benchmark progress in both the hosted web product and local read-only UI.

Deploy the web application, database, queue, and workers through a documented, reproducible production configuration.

Run the local benchmark stack on a MacBook Pro M4 Max without external compute.

Give a human or coding agent the repository and let them safely iterate on the solver without needing changes to the harness.

A local happy path should remain:

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

A hosted participation path should look like:

sign in on the website
    ↓
create a named API token
    ↓
authenticate the local CLI
    ↓
develop and benchmark locally
    ↓
submit a commit or bounded solver bundle
    ↓
server evaluates it in isolation
    ↓
verifier accepts or rejects the result
    ↓
accepted score enters the canonical leaderboard

3. Scope

In scope for the finished product

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

A local experiment view and canonical hosted leaderboard.

A progress-over-time chart.

Contributor documentation designed for both humans and coding agents.

A single headline score and a best-known-score frontier.

Account-free local execution.

Web authentication through a maintained OAuth provider, initially GitHub.

Named, scoped, revocable API tokens for CLI authentication.

CLI login, local run, submission, and submission-status commands.

An authenticated submission API with validation, rate limiting, and audit logging.

Persistent storage for users, token metadata, submissions, evaluation jobs, and canonical results.

Server-controlled hidden evaluation.

Isolated, resource-limited workers for untrusted solver submissions.

Reproducible deployment configuration, database migrations, secrets management, health checks, backups, and operator documentation.

Explicitly out of scope

Recovering production ML-DSA secret keys.

Forging ML-DSA signatures.

Accepting arbitrary third-party keys or signatures as attack targets.

Internet-scale target collection.

Production cryptanalytic tooling.

Payments.

Highly polished branding.

Perfect cryptographic fidelity to standardized ML-DSA parameter sets.

Agent taxonomy, model comparison, multi-agent tournaments, or orchestration research.

Arbitrary user-uploaded dependencies, unrestricted build scripts, or general-purpose remote code execution.

Enterprise identity providers, organizations, teams, billing, prizes, or financial settlement.

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

The exact search problem and acceptance bound must be finalized during the benchmark-kernel phase rather than left as a family of loosely related experiments. Once the baseline is published, changing them creates a new benchmark version.

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

Every valid run receives one deterministic headline score. The score is the total versioned abstract operation cost across the fixed evaluation suite, minimized. The exact operation weights and suite aggregation must be explicit, tested, and frozen with the benchmark version before optimization begins.

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

Use append-only JSONL for local research runs. Local use must not require an account, network connection, or database.

Example:

{
  "experiment_id": "2026-08-12-0017",
  "timestamp": "2026-08-12T13:40:00+08:00",
  "parent_commit": "abc123",
  "commit": "def456",
  "agent": "codex",
  "hypothesis": "cache repeated Gram-Schmidt state",
  "benchmark_version": "0.2.0",
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

The hosted product requires a transactional database as the source of truth for:

users and OAuth identities;

API-token names, prefixes, hashes, scopes, creation time, last-used time, expiry, and revocation;

submissions and their immutable source reference or uploaded bundle digest;

evaluation jobs, state transitions, worker attempts, and sanitized logs;

verified results and canonical leaderboard eligibility;

benchmark versions and trusted evaluator fingerprints.

Do not import a client JSONL record directly into the canonical leaderboard. The server creates its own experiment record from the worker's verified output. Provide an export format compatible with the local record schema so hosted results remain reproducible and portable.

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

# authenticate the CLI for hosted participation
mldsafail login <api-token>

# submit the current eligible solver revision
mldsafail submit

# inspect an evaluation job
mldsafail status <submission-id>

# start local website
python -m src.web.app

If practical, add convenience commands:

make test
make bench
make web
make check

`run` remains account-free and local. `submit` and `status` require a token because they act on the hosted service. The CLI must store tokens in the operating-system credential store when available, fall back to a permission-restricted configuration file only with an explicit warning, and never print a token after login.

13. Public and Hidden Evaluation

Use two seed sets.

Public seeds

Visible to the agent and used for development.

Hidden seeds

Kept outside the public repository and used only by official hosted evaluation workers. Maintainers may use a separate administrative path to reproduce an official evaluation; ordinary participant CLIs never receive hidden seeds.

Both must come from the same documented generator distribution.

This protects against:

seed-specific hacks;

lookup tables;

accidental overfitting;

brittle special cases.

The public and hidden suites must use the same documented distribution. The hosted evaluator records a hidden-suite version or digest without exposing the seeds. Rotation requires an explicit evaluation-suite version change and must not silently mix incomparable leaderboard results.

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

Identity and token tests

Verify:

OAuth identities bind to stable provider subjects;

session cookies and CSRF checks protect browser mutations;

token plaintext is returned only at creation and is never persisted or logged;

valid scopes authorize only their intended API operations;

expired, revoked, malformed, and wrong-user tokens fail safely;

rate limits and audit events are applied deterministically.

Submission and worker tests

Verify:

payload bounds, idempotency, and allowed-source manifests are enforced;

path traversal, symlinks, changed trusted files, dependencies, and setup hooks are rejected;

client-supplied scores and result records are ignored;

workers have no outbound network, service credentials, or writable trusted harness;

timeouts, memory excess, worker loss, retry, and cancellation produce the correct states;

hidden data does not appear in participant-visible logs or artifacts;

only a verified worker envelope can create an accepted canonical result.

Deployment tests

Verify migrations on an empty and representative existing database, exercise backup restoration, smoke-test health/readiness behavior, and run the complete OAuth-token-CLI-submission-worker-leaderboard path in staging.

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

baseline-v2

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

The frontend should emulate the structure and participation flow of ecdsa.fail more than its exact branding.

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

Authenticated participant area

Provide:

GitHub sign-in and sign-out;

API-token creation, listing, and revocation;

one-time display of newly created token secrets;

submission history and status;

sanitized evaluator logs and rejection reasons;

links from accepted submissions to leaderboard records.

Never render token secrets after their creation response. Token-list pages show only the name, non-secret prefix, scopes, dates, last use, and revocation state.

19. Product Stack, Identity, and API Tokens

Use one deployable web application for server-rendered pages and the versioned CLI API unless scale proves that separation is necessary. Retain the existing lightweight Python web stack where practical, but add a supported relational database, background-job queue, and isolated worker service.

Authentication policy

Use GitHub OAuth for browser identity in the first production version. Store the stable provider subject identifier rather than treating a mutable username or email address as identity. Use secure, HTTP-only, same-site cookies, CSRF protection on browser mutations, short session lifetimes, and explicit sign-out.

API-token policy

Generate tokens with a recognizable non-secret prefix and at least 256 bits of cryptographically secure entropy. Show the secret exactly once. Store only a slow, salted token hash plus the prefix and metadata. Compare credentials in constant time. Tokens must be individually named, revocable, optionally expiring, and scoped; the initial scopes are `submission:write` and `submission:read`. Do not use API tokens for browser sessions.

The CLI sends tokens only over TLS using the Authorization bearer scheme. Never place tokens in URLs, command telemetry, job payloads, evaluator environments, or logs. Apply per-user and per-token rate limits and retain security audit events for creation, use, failed authentication, and revocation.

Submission API

Expose a small versioned API for creating a submission, inspecting status, listing the authenticated user's submissions, and retrieving sanitized logs. Mutating requests require authentication, bounded payload sizes, idempotency keys, and rate limiting. The public leaderboard remains readable without authentication.

20. Local and Hosted Data Flow

Local research remains:

results/experiments.jsonl
          ↓
      parser
          ↓
   derived records
          ↓
      web view

Hosted participation is:

GitHub OAuth → participant account → named API token
                                   ↓
CLI submit → authenticated API → immutable submission record
                                   ↓
                              evaluation queue
                                   ↓
                        isolated disposable worker
                                   ↓
              trusted generator + verifier + cost model
                                   ↓
                     server-created verified result
                                   ↓
                 canonical database → public leaderboard

Derived values should include:

current best;

baseline delta;

headline-score frontier;

recent experiments;

diagnostic metrics for the current record;

cumulative improvement.

Keep derived calculations deterministic and testable. The leaderboard must derive only from accepted server-created results matching the same benchmark version, evaluator fingerprint, suite version, and required full scope.

Submission source contract

Accept only the bounded editable solver/math surface defined by the challenge. The initial submission format should be an immutable public Git commit plus repository URL, or a size-limited archive containing only eligible paths and a manifest. Resolve the exact commit, copy only allowed files into a clean evaluator checkout, reject symlinks and path traversal, verify the dependency lock and trusted fingerprint, and record the resulting content digest. Never execute participant-provided setup hooks or accept arbitrary dependencies.

Evaluation isolation

Treat every submission as untrusted code. Run it in a fresh, non-privileged worker with no outbound network, read-only trusted harness, bounded writable scratch space, CPU/time/memory/process/file-size limits, and no platform secrets or API token. Destroy the worker and scratch data after collecting the signed result envelope and sanitized logs. Workers must not have database credentials capable of directly accepting a result; a coordinator validates the worker envelope and performs the state transition.

21. Delivery Plan

Phase 1 — Freeze the benchmark kernel

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

Exit criterion:

python -m src.benchmark.runner

produces a verified, reproducible baseline result.

Do not prioritize hosted participation until this works.

Phase 2 — Make local autoresearch productive

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

Exit criterion:

multiple recorded experiments;

at least one validated improvement over baseline;

failed experiments preserved;

hidden evaluation working.

Phase 3 — Build the public read-only product

Primary goal: turn the research loop into a convincing local and deployable read-only product.

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

one-command local startup;

containerized web deployment and health checks.

Spend remaining time on:

additional human- or agent-driven optimization runs;

bug fixing;

documentation;

presentation polish.

Exit criterion:

make web

opens a complete local demo, while a documented deployment shows the same baseline, best-known valid solution, and history publicly.

Phase 4 — Add authenticated participation

Primary goal: contributors can authenticate and submit without weakening local usability.

Build:

GitHub OAuth and secure browser sessions;

named API-token lifecycle;

CLI login and credential storage;

versioned submission/status API;

relational schema and migrations;

rate limits and audit events;

participant submission pages.

Exit criterion:

a user can sign in, create and revoke a token, authenticate the CLI, create an immutable queued submission, and inspect its status; no submitted code runs in the web process.

Phase 5 — Add trusted hosted evaluation

Primary goal: accepted submissions can safely enter the canonical leaderboard.

Build:

isolated disposable workers;

server-only hidden suites;

source allowlisting and trusted-checkout assembly;

resource and network isolation;

signed result envelopes and coordinator validation;

retry, timeout, cancellation, and sanitized-log behavior;

canonical leaderboard promotion.

Exit criterion:

an untrusted eligible submission is evaluated end to end, cannot access hidden inputs or service credentials, and appears on the leaderboard only after independent server verification.

Phase 6 — Production hardening and launch

Primary goal: the complete product is operable, recoverable, and safe to expose publicly.

Build:

production configuration and secret injection;

TLS and secure headers;

backup and restore procedures;

monitoring, alerting, structured logs, and queue dashboards;

abuse controls and administrative token/submission revocation;

deployment, rollback, migration, and incident runbooks;

end-to-end staging and load tests.

Exit criterion:

a fresh environment can be deployed from documentation, survives a restore exercise, exposes health signals, and supports the complete browser-to-CLI-to-leaderboard flow.

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

Local integrity checks need to make accidental or unauthorized benchmark changes obvious. Hosted evaluation must additionally enforce the trusted checkout, allowed submission surface, evaluator fingerprint, and isolation boundary rather than trusting participant compliance.

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

These are useful studies derived from the benchmark. They must not drive the core product architecture, complicate the scoring objective, or displace work on the lattice challenge itself.

26. Experiment Classification

Use lightweight tags when they help contributors understand the technical history; do not build an elaborate taxonomy into the core product.

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
submission ID and user ID
source repository, immutable commit, and eligible-source digest
evaluation job and worker attempt IDs
evaluator fingerprint and hidden-suite version
resource-limit outcome

Record the machine architecture explicitly so diagnostic wall-clock results are interpretable. Hosted leaderboard workers for a benchmark version should use a documented, homogeneous execution class; a worker-class change must not silently mix timing diagnostics.

29. Failure Handling

A failed experiment is not a failed project event.

Store failures such as:

verifier failure;

timeout;

regression;

numerical instability;

memory explosion;

hidden-seed failure;

non-generalizing speedup;

submission validation failure;

authentication or authorization failure;

queue timeout or worker loss;

evaluator infrastructure failure.

The UI must display them as part of the research and submission history.

Distinguish participant-result failures from infrastructure failures. Invalid output, resource excess, or an ineligible source bundle produces a rejected, unscored submission. Worker loss, platform outage, or evaluator malfunction produces an infrastructure-failed attempt that may be retried and must not count against the participant's result history as a scientific failure.

Failed results prevent duplicated work and document the evidence behind changes to the best-known implementation. Hosted error messages and logs must be sanitized so they do not disclose hidden inputs, filesystem layout, credentials, or internal service details.

30. README Requirements

The README should contain:

One-paragraph description.

Screenshots of the public challenge, leaderboard, API-token, and submission-status views.

Quickstart.

Benchmark explanation.

Safety boundary.

Repository map.

How to run tests.

How to run benchmarks.

How experiments are recorded.

How to launch the site.

How to sign in, create/revoke an API token, authenticate the CLI, submit, and inspect status.

How official evaluation differs from local benchmarking.

How to deploy, migrate, monitor, back up, restore, and roll back the hosted product.

How agents should interact with the repo.

Link/reference to AGENTS.md.

Link/reference to PLAN.md.

Keep the README user-facing.

Keep operational agent rules in AGENTS.md.

Keep implementation sequencing here in PLAN.md.

31. Domain and Deployment

Use the project name:

mldsa.fail

for local and hosted branding.

Treat deployability as a product requirement, not a future possibility. Keep local development simple, but maintain production-equivalent service boundaries for the web application, relational database, queue, evaluator coordinator, and isolated workers.

Provide:

container images pinned by digest;

declarative service configuration with separate development, staging, and production environments;

database migrations that are forward-safe and have documented rollback or recovery behavior;

platform secret injection with no committed secrets;

TLS termination, secure headers, health/readiness checks, and graceful shutdown;

durable database backups plus a tested restore procedure;

structured logs, metrics, alerts, and retention policies;

a deployment runbook and a one-command local composition for the complete hosted stack.

The production evaluator must be independently scalable from the web process and must never share its untrusted execution environment with the API, database, queue broker, or platform credentials.

32. Decision Rules During Product Development

When an implementation choice is ambiguous:

Prefer the option a new human or coding-agent contributor can understand.

Prefer deterministic behavior.

Prefer fewer dependencies.

Prefer explicit data structures.

Prefer testable interfaces.

Preserve account-free local execution while designing hosted paths for safe deployment.

Prefer a working vertical slice over architectural completeness.

Defer visual refinement until the benchmark loop is stable.

Contributors are authorized to make routine solver implementation decisions without changing the trusted benchmark contract.

Escalate only when a decision changes:

benchmark semantics;

safety boundaries;

scoring meaning;

major project scope;

identity, token, submission, or evaluator trust boundaries;

production data retention or operational security.

33. Definition of Done

The finished product is done when all of the following are true:

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

Local benchmark and website start without an account.

Website shows baseline, current best, and headline-score improvement.

Website shows progress over time.

Website shows recent experiments.

AGENTS.md gives coding agents clear operating rules.

PLAN.md describes architecture and build order.

README explains how to reproduce the demonstration.

GitHub OAuth creates a stable participant identity with secure browser sessions.

Users can create, view metadata for, and revoke named scoped API tokens; plaintext secrets are shown only once and never stored.

The CLI can authenticate securely, submit eligible immutable source, and inspect submission status.

The API enforces authorization, idempotency, payload bounds, rate limits, and audit logging.

Submitted code runs only in disposable isolated workers with no outbound network, hidden-seed access beyond the running evaluator, or platform credentials.

The server independently generates every canonical score and never trusts client-submitted metrics.

Only accepted full-scope results for one benchmark/evaluator/suite contract enter a leaderboard cohort.

Users can distinguish rejected scientific results from retryable infrastructure failures and view sanitized logs.

Database migrations, backups, restore, deployment, rollback, health checks, monitoring, and operator runbooks are tested in staging.

The hosted product can be deployed reproducibly to mldsa.fail while the complete local workflow remains usable offline.

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

Live experiment feed.

Public participant profiles.

Infrastructure

Autoscaling across multiple homogeneous worker pools.

Multi-region read replicas and disaster recovery.

Additional OAuth providers and hardware-backed administrator authentication.

CI benchmark checks for non-submission branches.

None of these should delay the finished single-region product.

35. Final Build Principle

The project should remain centered on one objectively scored scientific challenge and one observable loop:

editable algorithm
    ↓
local candidate solution
    ↓
authenticated reproducible submission
    ↓
isolated immutable verification
    ↓
headline score
    ↓
shared best-known frontier

Humans and agents advance that loop by forming hypotheses, changing code, and contributing evidence. Everything else exists to make the scientific optimization faster, more reliable, easier to audit, or easier to understand.

Local research must remain fast and account-free. Hosted infrastructure exists to make public participation attributable, reproducible, safe, and trustworthy. If a feature does not strengthen that loop or make the finished product operable, defer it.
