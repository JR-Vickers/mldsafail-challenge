# PLAN.md — ML-DSA Challenge Benchmark

> This document is the single source of truth for the project. Future coding agents should be able to read it in isolation and understand what we are building, why, how the challenge works, what code they may edit, what code they must not touch, how to run experiments, and how to decide whether an improvement is real. If this document and another file disagree, this document wins and the disagreement should be treated as a bug to resolve.

---

## 1. Project Goal

Build a focused, deterministic, locally runnable benchmark for competing implementations on small, synthetic lattice-inspired problems motivated by ML-DSA (Dilithium-style lattice cryptography).

The product is inspired by [ecdsa.fail](https://ecdsa.fail/) in spirit and participation model, but the mathematical content is different:

- ecdsa.fail isolates **elliptic curve point addition** as the bottleneck in Shor's algorithm and scores quantum circuits by **qubit × Toffoli**.
- This project isolates **lattice reduction** as the step we chose to isolate for attacking ML-DSA, and scores solvers by **abstract operation count** on small synthetic instances.

The core question:

> If lattice reduction is the binding constraint on attacking ML-DSA, what is the most operation-efficient way to perform it on small, fixed, reproducible instances — and can coding agents drive that cost down in a measurable, verifiable, reproducible way?

The benchmark is a **research environment and optimization competition**, not a production cryptanalytic tool. All experiments operate on deliberately small, repository-generated instances. The project does not accept real keys, signatures, arbitrary matrices, or production ML-DSA parameters as solver targets.

---

## 2. What This Is and What This Is Not

### This is

- A synthetic, ML-DSA-motivated lattice challenge that researchers can run locally without an account.
- A competition where participants optimize a solver against a fixed, frozen benchmark contract.
- A tool for studying which lattice-reduction and related techniques produce the lowest operation cost on small instances.
- A reproducibility harness with append-only experiment logs, hidden-seed evaluation, and an independent verifier.
- A potential hosted product where authenticated participants submit solver revisions and get them evaluated in isolated workers.

### This is not

- A tool for recovering real ML-DSA secret keys.
- A tool for forging ML-DSA signatures.
- A general-purpose lattice reduction library (though it may contain one for the benchmark).
- A post-quantum cryptography implementation correctness suite (though it may use correctness vectors for reference).
- An attack on any deployed system.
- A way to ingest external cryptographic targets.

---

## 3. The Scientific Question

### Primary question

What is the most operation-efficient way to solve the challenge problem defined in Section 5, and can we drive that cost down through iterative solver optimization?

### Secondary questions

- Is lattice reduction the right primitive to isolate, or is there a better binding constraint?
- Which cost metric best captures the resource pressure that matters for the real attack?
- How do different reduction strategies compare on small, controlled instances?
- Can coding agents discover non-obvious optimization strategies in this space?

### Relationship to real ML-DSA

ML-DSA (Dilithium) security relies on the hardness of lattice problems (SIS, MSIS, Module-SIS, and related structured lattice problems) over polynomial rings. The leading classical and quantum attacks involve:

1. **Lattice reduction** (LLL, BKZ, sieving) to find short vectors in the relevant module lattices.
2. **Enumeration** or **search** to find the specific short vector that satisfies the cryptographic relation.
3. **Hybrid strategies** that combine reduction with enumeration.

The current challenge isolates a **toy version of the lattice reduction step** on small integer lattices. This is a synthetic stand-in, not the real ML-DSA problem. The hope is that if we can make meaningful progress on the toy version, we learn something about which reduction techniques are most operation-efficient, which may translate to insight about the real problem.

The relationship is **inspirational and methodological**, not a direct attack. We are not solving ML-DSA. We are building a controlled environment to study the hardness of a related lattice problem.

---

## 4. The Binding Constraint Hypothesis

### Hypothesis

**Lattice reduction is the hardest and most operation-intensive step in attacking ML-DSA, and it should be the focus of this challenge.**

This hypothesis is motivated by:

- The transcript discussion that explicitly identified basis reduction as the step to isolate.
- The structure of known ML-DSA attacks, where reduction dominates the cost.
- The analogy to ecdsa.fail, where the bottleneck step (EC addition in Shor's algorithm) is isolated and optimized.

### Status of the hypothesis

**Partially confirmed by empirical results on Benchmark 0.4.0.** We built a lattice-reduction benchmark (Kannan embedding + Schnorr-Euchner enumeration on the small profile, Gaussian elimination fallback on medium/large) and measured the results:

- **Small profile (n=8, lattice dim=17)**: LLL reduction runs in milliseconds, and SE enumeration finds the target vector within 200K nodes. Lattice reduction is the natural and tractable approach here.
- **Medium/large profiles (n=16/24, lattice dim=33/49)**: The target vector `(-s, 0, 1)` exists in the reduced lattice, but its representation in the reduced basis requires large coefficients (growing with the modulus and dimension). SE enumeration is infeasible within resource limits (5s wall time, 64 MiB). Gaussian elimination on the modular system remains correct and tractable as a fallback.

**Key empirical finding**: The Kannan embedding is mathematically correct, LLL reduction preserves the lattice determinant and places the target vector in the reduced basis. The bottleneck is not the reduction — it is the **search**: the target vector's coefficients in the reduced basis are large (the lattice reduction does not make the target "obvious" via small basis coefficients), so enumeration strategies that rely on small coefficients cannot find it without prohibitive search cost.

This finding motivates the hybrid design: make lattice reduction the primary method where it works (small profile), and ensure correctness on larger profiles via the classical approach. It also suggests that future improvement may come from:

1. A better embedding where the target's reduced-basis coefficients are small
2. Stronger reduction (BKZ) that produces a basis where the target is more accessible
3. Improved enumeration techniques that can handle larger coefficient ranges

### Candidate solver approaches tested

- **Candidate A**: Gaussian elimination on the modular system (correct, solves a different problem than lattice reduction, 137K ops on the public suite).
- **Candidate B**: LLL-based lattice reduction on the Kannan-embedded lattice, now with Schnorr-Euchner enumeration. Works on the small profile; falls back to Gaussian elimination on medium/large. The implementation is in `src/mldsafail/solver/candidate_b.py`.
- **Candidate C**: Guessing plus reduced Gaussian solve (correct, but exponentially expensive).

The shift from 0.3.0 to 0.4.0 was the decision to stop treating lattice reduction as a failed probe and instead redesign the benchmark so that reduction is the natural approach where tractable. This is documented in `docs/conclusions.md`.

### Open questions that remain

1. Can a better embedding or stronger reduction extend lattice-reduction coverage to medium/large profiles?
2. Which cost metric best captures the resource pressure that matters for the real attack?
3. Can coding agents discover non-obvious optimization strategies in this space?

The benchmark is not a final answer to the hypothesis. It is a measurement environment that lets us test it empirically and improve.

## 5. Challenge Contract

### 5.1 The Problem

Given:

- A prime modulus `q`
- An `n × n` matrix `A` over `Z/qZ`
- A target vector `t` of length `n` over `Z/qZ`
- A bound `η`

Find:

- A vector `c` of length `n` with integer coefficients in `[-η, η]`

Such that:

- `A * c ≡ t (mod q)`

**For Benchmark 0.4.0 (current):** The problem is solved via lattice reduction
on the small profile (n=8) using the Kannan embedding and Schnorr-Euchner
enumeration. Medium and large profiles fall back to Gaussian elimination for
correctness but the benchmark design makes lattice reduction the natural
approach for small instances.

### 5.2 Instance Generation

Instances are generated deterministically from:

- A profile (small, medium, large) that fixes `n`, `q`, `η`
- A seed (integer) that selects the specific instance within that profile

The generator:

1. Uses the seed to deterministically construct `A` and a planted secret `s`
2. Computes `t = A * s mod q`
3. Publishes `(A, t, q, n, η)` as the challenge instance
4. Retains `s` only for testing/verification purposes, not exposed to solvers

The generator is in `src/mldsafail/trusted/generator.py`. Solvers must not access the planted secret.

### 5.3 Candidate Contract

```python
candidate = solve(instance)
```

Returns a `Candidate` object with:

- `coefficients`: tuple of `n` integers

### 5.4 Verification

An independent verifier in `src/mldsafail/trusted/verifier.py` checks:

1. The candidate has exactly `n` coefficients
2. Every coefficient is in `[-η, η]`
3. `A * coefficients ≡ t (mod q)`

If any check fails, the candidate is invalid and receives no score.

The verifier does not receive the planted secret `s`. It validates the candidate against the public challenge data only.

### 5.5 Correctness is Binary

An invalid candidate receives **no score**. There is no partial credit. The score is only defined for correct candidates.

---

## 6. Scoring and Cost Model

### 6.1 Primary Score

The headline score is the **total versioned abstract operation cost** across all instances in the evaluation suite, summed and minimized.

Version 2 cost model assigns unit weight to:

- `additions`
- `multiplications`
- `modular_reductions`
- `basis_updates`
- `memory_reads`
- `memory_writes`

```text
score = sum over all instances of (additions + multiplications + modular_reductions + basis_updates + memory_reads + memory_writes)
```

The cost model is versioned. Changing the cost model, weights, or aggregation rule creates a new benchmark version and requires a new baseline.

### 6.2 Instrumentation

Solvers receive a trusted `OperationMeter` from `src/mldsafail/benchmark/cost_model.py`. The meter:

- Provides validated increment methods for each operation category
- Rejects negative and malformed increments
- Exposes immutable snapshots

Solvers must instrument their operations as they execute. The meter is the audit boundary for cooperative research code; it is **not** a sandbox against malicious Python.

### 6.3 Diagnostic Metrics (non-ranking)

The following are recorded but do not determine the winner:

- Total wall-clock time
- Median per-instance runtime
- Peak memory
- Solution quality (a heuristic measure of vector shortness, if applicable)
- Per-category operation counts
- Per-instance details

These help explain improvements and expose resource tradeoffs, but the leaderboard ranks only the primary score.

### 6.4 Lowest Score Wins

The leaderboard is ordered by ascending primary score. A lower score is better. Ties are possible but should be rare given deterministic instances and instrumented costs.

---

## 7. Difficulty Profiles

Three fixed profiles:

| Profile | Dimension (n) | Modulus (q) | Bound (η) | Public Seeds | Hidden Seeds |
|---------|---------------|-------------|-----------|--------------|--------------|
| small   | 8             | 97          | 2         | 3            | 2            |
| medium  | 16            | 257         | 3         | 3            | 2            |
| large   | 24            | 769         | 4         | 3            | 2            |

These parameters are stored in `config/profiles.toml`. Changing them requires a benchmark version bump and a new baseline.

### Design requirements

- Deterministic generation
- Fast enough for repeated local iteration (seconds, not minutes)
- Increasing difficulty across profiles
- Enough headroom for optimization
- Well below practical cryptographic attack sizes

### Hybrid design rationale (Benchmark 0.4.0)

Benchmark 0.4.0 uses a hybrid design where lattice reduction is the primary
approach for small instances and Gaussian elimination serves as a correctness
fallback for larger instances:

- **small (n=8, lattice dim=17)**: Schnorr-Euchner enumeration on the
  Kannan-embedded lattice is tractable. LLL runs in milliseconds, and SE
  enumeration (focused on last coordinate ±1) finds the target vector within
  200K nodes. This profile tests lattice-reduction capability.

- **medium (n=16, lattice dim=33) and large (n=24, lattice dim=49)**: SE
  enumeration is infeasible within resource limits (5s wall time, 64 MiB).
  The solver falls back to Gaussian elimination on the modular system.

**Why this design**: The Kannan embedding is mathematically correct and LLL
reduction works. However, the target vector `(-s, 0, 1)` requires large
coefficients in the reduced basis representation, making SE enumeration
infeasible for dimensions above ~20. Rather than abandoning lattice reduction
entirely, the hybrid design:

1. Makes lattice reduction the primary approach where it works (small profile)
2. Ensures correctness on all profiles via GE fallback
3. Leaves room for future optimization: better embeddings, stronger reduction
   (BKZ), or improved enumeration that could extend lattice-reduction coverage
   to larger profiles

This design is a deliberate choice, not a compromise. It tests whether solvers
can perform lattice reduction effectively on tractable instances while ensuring
the benchmark remains solvable.

### Constraints

- Profiles must be small, synthetic, and locally generated.
- The parameters must not correspond to production ML-DSA parameter sets.
- The dimension, modulus, and bound must produce instances that are solvable in principle (the current generator guarantees a solution exists).

---

## 8. Safety Boundary

### 8.1 Enforced in Code

The safety boundary is not just documentation. It is enforced by:

- The benchmark runner accepting only repository-controlled profiles and seeds.
- The generator producing only instances within the configured profile caps.
- The verifier rejecting any candidate that does not match the instance's dimension, bound, and modular relation.
- The runner rejecting external matrices, public keys, signatures, arbitrary parameter combinations, or production ML-DSA parameter sets.

### 8.2 Explicit Prohibitions

Participants must not:

- Attempt to recover real ML-DSA secret keys.
- Attempt to forge ML-DSA signatures.
- Supply external public keys, signatures, or matrices as solver targets.
- Modify the benchmark to accept arbitrary cryptographic parameters.
- Target deployed systems with this tool.
- Remove instance restrictions to attack practical parameters.

If a proposed experiment crosses this boundary, replace it with either:

1. A bounded synthetic instance experiment within the current profiles, or
2. A non-executable theoretical or resource-estimation experiment documented in notes.

### 8.3 ML-DSA Reference is Allowed

It is acceptable to reference ML-DSA specifications and mathematics for:

- Structural inspiration for the challenge design.
- Specification study and understanding.
- Correctness examples and test vectors.
- Resource estimation and asymptotic comparison.
- Understanding the relationship between the toy problem and the real problem.

The line is: **do not turn the benchmark into an attack tool for real ML-DSA**.

---

## 9. Trusted vs. Editable Code

### 9.1 Trusted (Do Not Modify During Solver Experiments)

These define the challenge and must not change during an optimization experiment:

- `src/mldsafail/trusted/generator.py` — instance generation
- `src/mldsafail/trusted/verifier.py` — candidate verification
- `src/mldsafail/benchmark/` — runner, metrics, cost model, records, integrity
- `config/profiles.toml` — profile parameters
- `src/mldsafail/data/public_seeds.json` — public seed set
- `src/mldsafail/benchmark/contract.toml` — benchmark contract version

Modifying these during an experiment invalidates the experiment's comparability with other runs.

### 9.2 Editable by Default

These are the surfaces participants optimize:

- `src/mldsafail/solver/` — solver implementations
- `src/mldsafail/math/` — mathematical primitives and operations

### 9.3 May Be Modified for Legitimate Engineering

Other areas may be modified when necessary for legitimate engineering work (bug fixes, infrastructure improvements, web UI, etc.), but ordinary optimization runs should focus on `solver/` and `math/`.

### 9.4 Integrity Fingerprints

The benchmark computes a trusted-input fingerprint from the frozen trusted files. This fingerprint is recorded with each experiment. If the fingerprint does not match the expected baseline, the run is flagged as not matching the baseline and may be excluded from official comparison.

---

## 10. Repository Architecture

```
.
├── AGENTS.md
├── PLAN.md
├── README.md
├── pyproject.toml
│
├── config/
│   ├── profiles.toml        # profile parameters (trusted)
│   └── benchmark.toml       # benchmark contract (trusted)
│
├── data/
│   └── public_seeds.json    # public seeds (trusted)
│
├── src/mldsafail/
│   ├── __init__.py
│   ├── cli.py               # CLI entry points
│   ├── models.py            # ChallengeInstance, Candidate, etc.
│   │
│   ├── math/                # EDITABLE
│   │   ├── __init__.py
│   │   ├── modular.py       # modular arithmetic
│   │   ├── polynomial.py    # polynomial operations (if needed)
│   │   └── lattice.py       # lattice operations (if needed)
│   │
│   ├── solver/              # EDITABLE
│   │   ├── __init__.py
│   │   ├── baseline.py      # baseline solver
│   │   ├── reference.py     # reference implementation
│   │   ├── lazy.py          # current best solver
│   │   ├── candidate_a.py   # Candidate A (Gaussian elimination)
│   │   ├── candidate_b.py   # Candidate B (LLL lattice reduction)
│   │   └── candidate_c.py   # Candidate C (guessing + reduced solve)
│   │
│   ├── benchmark/           # TRUSTED
│   │   ├── __init__.py
│   │   ├── runner.py        # benchmark runner CLI
│   │   ├── metrics.py       # profile and instance measurement
│   │   ├── cost_model.py    # OperationMeter
│   │   ├── records.py       # experiment JSONL writing
│   │   ├── suites.py        # seed suite loading
│   │   ├── comparison.py    # result comparison
│   │   └── integrity.py     # trusted fingerprint computation
│   │
│   ├── trusted/             # TRUSTED
│   │   ├── __init__.py
│   │   ├── generator.py     # instance generation
│   │   └── verifier.py      # candidate verification
│   │
│   ├── web/                 # web dashboard (trusted for benchmark)
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── api.py
│   │   ├── auth.py
│   │   ├── services.py
│   │   ├── repositories.py
│   │   ├── models.py
│   │   ├── db.py
│   │   ├── config.py
│   │   ├── observability.py
│   │   └── tooltip_definitions.py
│   │
│   └── evaluator/           # hosted evaluation (trusted)
│       ├── __init__.py
│       ├── source.py
│       ├── envelope.py
│       ├── queue.py
│       ├── coordinator.py
│       ├── worker.py
│       ├── solver_child.py
│       └── docker.py
│
├── tests/
│   ├── test_auth_api.py
│   ├── test_benchmark.py
│   ├── test_cli.py
│   ├── test_evaluator.py
│   ├── test_generator.py
│   ├── test_hosted_persistence.py
│   ├── test_integrity.py
│   ├── test_math.py
│   ├── test_observability.py
│   ├── test_records.py
│   ├── test_solver.py
│   ├── test_verifier.py
│   └── test_web.py
│
├── experiments/
│   └── README.md            # experiment record schema documentation
│
├── docs/
│   ├── PLAN.md              # this document
│   ├── CHALLENGE.md         # benchmark contract (0.2)
│   ├── OPERATIONS.md        # deployment and operations
│   ├── AGENT_WORKFLOW.md    # experimenter procedure
│   ├── TRANSCRIPT.md        # source conversation
│   └── agent-briefs/        # agent brief documents
│
├── results/
│   └── experiments.jsonl    # append-only experiment log (generated)
│
├── agent/
│   ├── benchmark/           # agent benchmark scripts
│   └── trusted/             # agent trusted scripts
│
└── .venv/                   # Python virtual environment (not committed)
```

---

## 11. Experiment Storage

### 11.1 Local JSONL Log

Local research runs append one JSON object per experiment to `results/experiments.jsonl`. The log is the MVP datastore and research audit trail. Never rewrite it merely because an experiment failed.

Required fields in each record:

- `experiment_id`: unique identifier
- `timestamp`: ISO-8601
- `schema_version`: record schema version
- `benchmark_version`: benchmark version
- `solver`: solver name
- `correct`: boolean
- `score`: headline score or null
- `cost_model_version`: cost model version
- `aggregate`: diagnostic metrics
- `profiles`: per-profile results
- `agent`, `model`, `hypothesis`, `notes`: provenance
- `command`: exact command run
- `environment`: Python version, OS, architecture, dependency lock hash, git commit, dirty state
- `integrity`: trusted fingerprint status
- `failure_reason`: if incorrect or failed
- `parent_experiment`: if part of a sequence
- `tags`: list of tags
- `resource_limits`: per-instance limits

Schema validation requires the top-level `score` to match `aggregate.score`.

### 11.2 Failed Experiments

Failed, timed-out, invalid, and over-limit experiments include the same provenance fields, set `correct` to `false`, set score fields to `null`, and provide `failure_reason`. Failed experiments remain visible in history.

### 11.3 Hosted Database

The hosted product uses a relational database for:

- Users and OAuth identities
- API tokens
- Submissions and their source references
- Evaluation jobs and state transitions
- Verified results and canonical leaderboard eligibility
- Benchmark versions and trusted evaluator fingerprints

Do not import a client JSONL record directly into the canonical leaderboard. The server creates its own experiment record from the worker's verified output.

---

## 12. Commands

### Local Benchmark Commands

```bash
# Run tests
make test

# Run public benchmark (default)
uv run python -m mldsafail.benchmark.runner

# Run full evaluation (public + hidden)
uv run python -m mldsafail.benchmark.runner --suite full

# Run one profile
uv run python -m mldsafail.benchmark.runner --profile small

# Run with explicit seed (diagnostic, requires --profile)
uv run python -m mldsafail.benchmark.runner --profile small --seed 12345

# Run without recording to JSONL
uv run python -m mldsafail.benchmark.runner --profile small --no-record

# Run with metadata for records
uv run python -m mldsafail.benchmark.runner \
  --suite full \
  --agent codex \
  --model gpt-5 \
  --hypothesis "describe the tested change" \
  --tag algorithm \
  --notes "describe the measured outcome"
```

### Web Commands

```bash
# Start local dashboard
make web

# Smoke test (non-blocking)
make web-smoke

# Start the full hosted stack locally (requires Docker)
make hosted-dev

# Tear down the hosted stack
make hosted-down
```

### Check Command

```bash
# Run tests + small-profile smoke (no record appended)
make check
```

### CLI Commands (Hosted Participation)

```bash
# Install the CLI (one-liner, grabs the latest release CLI)
curl -fsSL https://github.com/JR-Vickers/mldsafail-challenge/raw/main/scripts/install.sh | sh

# Clone a participant workspace (optional; creates a git repo with a baseline solver)
mldsafail clone [DIR]

# Authenticate
mldsafail login TOKEN --server https://mldsa.fail

# Submit current commit
mldsafail submit --repo https://github.com/OWNER/REPO --commit FULL_40_CHAR_SHA --hypothesis "..."

# Inspect submission
mldsafail status SUBMISSION_ID --follow

# Logout
mldsafail logout
```

---

## 13. Public and Hidden Evaluation

### 13.1 Two Seed Sets

- **Public seeds**: visible to the agent, used for development. Stored in `data/public_seeds.json`.
- **Hidden seeds**: kept outside the public repository, used only by official hosted evaluation workers. Maintainers may reproduce an official evaluation through an administrative path; ordinary participant CLIs never receive hidden seeds.

Both must come from the same documented generator distribution.

### 13.2 Suite Definitions

- `public`: run only public seeds
- `hidden`: run only hidden seeds (requires administrative access)
- `full`: run public seeds, then hidden seeds (official evaluation)

### 13.3 Official Comparison Requirements

An official comparison uses:

- Every public and hidden profile
- A clean committed tree
- The frozen trusted-input fingerprint
- A full evaluation (public + hidden)

Custom, single-profile, public-only, legacy-version, or fingerprint-mismatched runs are useful diagnostics but cannot enter the official ranking.

### 13.4 Hidden Suite Versioning

Rotation of hidden seeds requires an explicit evaluation-suite version change and must not silently mix incomparable leaderboard results. The hosted evaluator records a hidden-suite version or digest without exposing the seeds.

---

## 14. Testing Strategy

Tests are part of the benchmark, not optional cleanup.

### Arithmetic Tests

- Modular addition, multiplication, inversion
- Polynomial arithmetic (if applicable)
- Matrix/vector operations
- Lattice relation checks
- Cost meter increments and validation

### Generator Tests

- Same seed → same instance
- Different seed → different instance
- Profile limits enforced
- Malformed profiles fail
- Arbitrary oversized parameters cannot be injected

### Verifier Tests

- Known-valid candidates pass
- Mutated candidates fail
- Malformed outputs fail
- Empty outputs fail
- Edge cases handled deterministically

### Solver Tests

- Smoke instances are solved correctly
- Solver cannot access planted secret state
- Deterministic mode is reproducible
- Each candidate solver (A, B, C, baseline, lazy, etc.) is tested

### Benchmark Tests

- Scores calculated consistently
- Invalid outputs receive no score
- Metrics recorded correctly
- Experiment records serialize correctly
- JSONL round-trip works

### Integrity Tests

- Trusted fingerprint computed correctly
- Baseline mismatch detected

### Web and API Tests

- Authentication and authorization
- Token lifecycle
- Submission API
- Dashboard routes

### Evaluator Tests (Hosted)

- Submission validation
- Worker isolation
- Resource limits
- Hidden data not leaked to participants

---

## 15. Baseline and Frontier

### 15.1 Baseline Solver

The baseline solver should be:

- Correct on all profiles
- Intentionally clear and unsurprising
- Not highly optimized
- A competent reference implementation, not artificially sabotaged

The current baseline lineage:

- **reference**: correct Gaussian elimination baseline
- **balanced**: optimized Gaussian elimination
- **lazy**: current best — triangular elimination with lazy modular reduction

Tag the first validated result as `baseline-v2` or equivalent.

### 15.2 Candidate Solvers

Multiple candidate approaches are implemented for comparison:

- **Candidate A**: Gaussian elimination with coefficient centering. Correct, cheap, solves the modular system directly.
- **Candidate B**: LLL lattice reduction on a constructed lattice. Attempted, currently fails verification.
- **Candidate C**: Guessing plus reduced Gaussian solve. Correct, but exponentially expensive.

These candidates are research probes, not necessarily the final solver lineup. The current competitive solver is `lazy`.

### 15.3 Frontier Tracking

The current best-known score is tracked:

- Locally in `results/experiments.jsonl`
- On the web dashboard
- On the hosted leaderboard (when available)

The frontier is the lowest valid headline score from a full public-plus-hidden evaluation with a matching trusted fingerprint.

---

## 16. Autoresearch Optimization Loop

This procedure keeps autonomous optimization reproducible and within the toy-only safety boundary.

1. Activate the environment with `source .venv/bin/activate`, inspect `AGENTS.md`, and confirm the worktree state.
2. Run `make test` and the current public benchmark. Record the baseline experiment and its parent ID.
3. Write one falsifiable hypothesis, such as "incremental reduction state will lower the score on medium and large."
4. Change only the smallest relevant area, normally `src/mldsafail/solver/` or `src/mldsafail/math/`. Do not alter profiles, seeds, generator, verifier, scoring, fingerprints, or safety validation to produce an apparent improvement.
5. Run focused tests, then `make test`, then all public profiles. Invalid output ends the experiment with no score.
6. If the public score improves, run `python -m mldsafail.benchmark.runner --suite full` to evaluate hidden seeds from the same distribution.
7. Keep the code only if correctness holds, resource limits are respected, and the combined public/hidden headline score is strictly lower. Revert non-improving code without deleting its appended experiment record.
8. Commit a coherent, descriptive checkpoint. Never push to the main branch automatically.

Every record should make the experiment independently interpretable: hypothesis, command, revision and dirty state, Python/dependency/OS/architecture metadata, seed suite, headline score, diagnostic metrics, cost-model version, resource limits, verification result, notes, parent experiment, and integrity fingerprint.

Stop and replace any proposal that would ingest an external key or signature, enable arbitrary attack parameters, target a deployed system, or operate beyond repository-generated toy instances. The permitted substitute is a bounded synthetic experiment or a non-executable theoretical/resource estimate.

---

## 17. Decision Framework for Solver Changes

For each proposed change, apply:

| Condition | Decision |
|-----------|----------|
| Breaks correctness | Revert |
| Exceeds resource limit | Reject as unscored |
| Lowers headline score (full suite) | Keep and advance frontier |
| Does not lower headline score | Do not advance frontier |

Additional considerations:

- Did the change modify trusted code? If so, the experiment is invalid for comparison.
- Did the change special-case known seeds? If so, reject.
- Did the change fabricate or skip cost counters? If so, reject.
- Did the change weaken verification or difficulty? If so, reject.

---

## 18. Submission and Hosted Evaluation

### 18.1 Submission Source Contract

Accept only the bounded editable solver/math surface. The initial submission format should be:

- An immutable public Git commit plus repository URL, or
- A size-limited archive containing only eligible paths and a manifest

Resolve the exact commit, copy only allowed files into a clean evaluator checkout, reject symlinks and path traversal, verify the dependency lock and trusted fingerprint, and record the resulting content digest. Never execute participant-provided setup hooks or accept arbitrary dependencies.

### 18.2 Evaluation Isolation

Treat every submission as untrusted code. Run it in a fresh, non-privileged worker with:

- No outbound network
- Read-only trusted harness
- Bounded writable scratch space
- CPU/time/memory/process/file-size limits
- No platform secrets or API token

Destroy the worker and scratch data after collecting the signed result envelope and sanitized logs. Workers must not have database credentials capable of directly accepting a result; a coordinator validates the worker envelope and performs the state transition.

### 18.3 Submission Flow

```
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
```

### 18.4 Status States

- `queued`
- `running`
- `accepted`
- `rejected`
- `failed`

Submitters see status without trusting client-supplied scores. Only server-verified results enter the leaderboard.

---

## 19. Web Product

### 19.1 Inspiration

The frontend should emulate the structure and participation flow of ecdsa.fail more than its exact branding.

Do not spend the first day tuning colors, fonts, or logos.

### 19.2 Homepage Sections

**Hero**

- Project name
- One-line description of the challenge
- Current improvement vs. baseline
- Frontier progress bar

**Current Record**

- Lowest valid headline score
- Improvement from baseline
- Supporting diagnostics: runtime, memory, solution quality, operation categories

**Improvement History**

- Chart of best-known score over time
- Each point links to its experiment record

**Recent Experiments**

- Timestamp, researcher/agent, hypothesis, result, delta, commit

**Participate**

- A "Participate" button in the navigation opens a modal with the current functional getting-started instructions: local `uv sync` workflow for running locally, and hosted CLI commands for when the coordinator is running. The ecdsa.fail-style install script and agent skill are future work and flagged as such.

**Methodology**

- Short explanation of instances, verifier, scoring, hidden evaluation, safety boundary

### 19.3 Authenticated Participant Area

- GitHub sign-in and sign-out
- API-token creation, listing, and revocation
- One-time display of newly created token secrets
- Submission history and status
- Sanitized evaluator logs and rejection reasons
- Links from accepted submissions to leaderboard records

Never render token secrets after their creation response. Token-list pages show only the name, non-secret prefix, scopes, dates, last use, and revocation state.

---

## 20. Data Flow

### Local Research

```
results/experiments.jsonl
          ↓
      parser
          ↓
   derived records
          ↓
      web view
```

### Hosted Participation

```
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
```

Derived values include:

- Current best
- Baseline delta
- Headline-score frontier
- Recent experiments
- Diagnostic metrics for the current record
- Cumulative improvement

Keep derived calculations deterministic and testable. The leaderboard must derive only from accepted server-created results matching the same benchmark version, evaluator fingerprint, suite version, and required full scope.

---

## 21. Development Plan

### Phase 1 — Freeze the Benchmark Kernel

**Goal**: Freeze the scientific challenge and produce its first verified score.

Build:

- Project skeleton (done)
- Precise challenge statement and solver contract (done — Section 5)
- Profiles (done — Section 7)
- Deterministic generator (done)
- Mathematical primitives (in progress)
- Verifier (done)
- Baseline solver (done)
- Benchmark runner (done)
- Metrics and cost model (done)
- One versioned headline-score formula (done — Section 6)
- Basic tests (in progress)
- Experiment JSONL writer (done)

Exit criterion: `uv run python -m mldsafail.benchmark.runner` produces a verified, reproducible baseline result.

**Status**: The kernel is largely built. The remaining work is hardening tests, resolving the open question about whether lattice reduction should be the direct problem or a solver approach, and establishing the official baseline record.

**As of Benchmark 0.4.0 (2026-08-24)**, the following are complete:

- Benchmark contract (0.4.0) with hybrid lattice-reduction/GE design
- Generator, verifier, cost model, runner (all functioning)
- Candidate B solver with Schnorr-Euchner enumeration (works on small profile)
- GE fallback for medium/large profiles
- Public-suite baseline recorded (2,792,128 ops)
- Version bump to 0.4.0
- Local website displaying leaderboard and history
- Evaluator solver_child updated to accept lattice solver
- Documentation (PLAN.md, CHALLENGE.md) updated
- Hosted participation infrastructure implemented; dev prototype not yet verified end-to-end

**Plus interactive onboarding (in progress)**:

- Participate button in the navigation bar (done)
- Modal with current-functional getting-started instructions (done, content to be made honest)
- `make hosted-dev` starts the full stack including the coordinator (in progress)
- One-command hidden-seeds setup (in progress)
- Install script served from the repository (in progress)
- `mldsafail clone` workspace scaffold (in progress)
- Honest modal content that shows what works now and flags future work (in progress)

### Phase 1c — Interactive Onboarding: Directive

This subsection is the implementation spec for the onboarding work listed above. An agent tasked with "implement Phase 1c" should read this subsection and treat it as the full instruction set.

#### Decisions (do not re-litigate)

1. **Modal content**: show what *actually works now*. Local `uv sync` workflow for running locally; hosted CLI commands for when the coordinator is running. Flag the ecdsa.fail-style install script and agent skill as future work.
2. **Scope**: Option B — the full onboarding surface. Install script + `clone` scaffold + honest modal + coordinator-start + hidden-seeds automation.
3. **`make hosted-dev`**: one command → full flow. Start the coordinator too.
4. **Hidden-seeds setup**: one-command automation (Makefile target/script copies the dev fixture and sets mode 0400). Do not hardcode `/Users/jarrett/...` paths; use the configured work dir with a sensible default.
5. **Install script**: curl-able from GitHub (raw file in the repo at `scripts/install.sh`), not served dynamically from the web app. Reference it in the modal only as the CLI install one-liner, not as a local-dev requirement.
6. **`clone` scope**: minimal — git init a directory, write a solver `__init__.py` importing the current best solver's `solve(instance, meter)`, write an empty math `__init__.py`, commit, print path + SHA.
7. **Eval flow**: Docker flow only for now. Do not build a synchronous dev-eval shortcut.
8. **Dev cohort labels**: keep `MLDSAFAIL_EVALUATOR_FINGERPRINT=development` and `MLDSAFAIL_HIDDEN_SUITE_VERSION=development-public-fixture` as-is.

#### Work

##### 1. Make `make hosted-dev` start the coordinator

In `Makefile`, wire the coordinator service into the `hosted-dev` target so one command starts db + web + proxy + coordinator. The coordinator service is already defined in `compose.yaml`; `compose.dev.yaml` already overrides its env and mounts the Docker socket and dev hidden-seeds file. You are adding it to the `up` list, not re-defining it. Also verify `hosted-down` tears down the coordinator (it already exists — confirm).

Verify the coordinator's dev-compose environment is coherent with what `coordinator.py:main()` reads from `os.environ`:
- `MLDSAFAIL_DATABASE_URL` → `postgresql+psycopg://mldsafail:${POSTGRES_PASSWORD}@db/mldsafail`
- `MLDSAFAIL_HIDDEN_SEEDS_PATH` → mounted dev hidden-seeds file
- `MLDSAFAIL_EVALUATOR_WORK_ROOT` → host path (must exist or be created)
- `MLDSAFAIL_WORKER_IMAGE` → `mldsafail-worker:0.4.0`
- `MLDSAFAIL_BENCHMARK_VERSION` → `0.4.0`
- `MLDSAFAIL_EVALUATOR_FINGERPRINT` → `development`
- `MLDSAFAIL_HIDDEN_SUITE_VERSION` → `development-public-fixture`
- `MLDSAFAIL_WORKER_CLASS` → `rootless-docker-v1`

##### 2. One-command hidden-seeds setup

Add a Makefile target (e.g. `hosted-setup`) that:

- Reads the work dir from the environment with a sensible default (the same default the compose stack uses)
- Creates `<work-dir>/secrets/`
- Copies `deploy/dev-hidden-seeds.json` into it as `hidden-seeds.json`
- Sets mode 0400
- Is idempotent (skip or overwrite cleanly on re-run; do not error on the second run)

Document the target briefly where a newcomer will find it — the README quick-start or `docs/OPERATIONS.md`, whichever is more discoverable. Keep it short.

##### 3. Install script

Create `scripts/install.sh`. It should:

- Detect the platform (macOS, Linux; fail clearly on unsupported)
- Install the `mldsafail` CLI. Prefer `uv tool install mldsafail-challenge` if uv is available; fall back gracefully with a clear message if uv is absent. Do not require the repo to be checked out for the primary path.
- Print next steps: `mldsafail login`, `mldsafail clone`, etc.
- Be safe to pipe to `sh` (no destructive defaults, no unnecessary sudo, clear error messages).

Do **not** serve this dynamically from the web app. It lives in the repo and is curl-able from the GitHub raw URL.

##### 4. `mldsafail clone` subcommand

Add a `clone` subcommand to `cli.py`. Minimal behavior:

- Optional positional arg `DIR` (default: `mldsafail-workspace` in cwd).
- `git init` the directory, or fail cleanly if it exists and is non-empty (do not clobber).
- Write `src/mldsafail/solver/__init__.py` that imports the current best solver and re-exports `solve(instance, meter)`. Currently that is `lazy` — import from `mldsafail.solver.lazy`. Do not hardcode in a brittle way; if there is an obvious "current best" indicator, use it.
- Write `src/mldsafail/math/__init__.py` (empty).
- `git add` + `git commit` with a bland message.
- Print the repo path and the commit SHA, plus a one-line hint for `mldsafail submit --repo file:///path --commit SHA ...`.

Keep it small. No remote configuration, no baseline from the challenge repo, no fancy workspace management.

##### 5. Honest modal content

Update the dialog in `templates/base.html`. The dialog structure, CSS classes, and JS wiring stay exactly as they are — change only the text inside the `<pre><code>` block and the footer paragraph.

The modal should have two clear parts:

**Run locally (works now):**
```
git clone https://github.com/JR-Vickers/mldsafail-challenge.git
cd mldsafail-challenge
uv sync --extra dev
source .venv/bin/activate
make test
make bench
make web
```

**Submit to the hosted challenge (when the coordinator is running and the CLI is installed):**
```
mldsafail login TOKEN --server https://mldsa.fail
mldsafail submit --repo https://github.com/OWNER/REPO \
    --commit SHA --hypothesis "..."
mldsafail status SUBMISSION_ID --follow
```

Footer: "Installing adds the `mldsafail` CLI. An agent skill that runs the full loop is future work."

Do **not** include a local `curl … | sh` line in the local section — we do not have a local install endpoint. The install script is a GitHub-raw curl; reference it only as the CLI-install one-liner (in the CLI commands doc, and optionally as a note in the modal), not as something served from localhost.

Remove every ecdsa.fail reference from the modal: no `api.ecdsa.fail/install.sh`, no `mldsafail clone` as if it existed before this work (it does after this work — that's fine, it's our subcommand), no `/ecdsafail-cli` skill.

##### 6. Update the modal's footer text

The current footer says: "Installing also adds the `/ecdsafail-cli` skill, so a coding agent can run the whole loop for you."

Replace with the honest version above. Do not leave the ecdsa.fail reference.

##### 7. Document the new surface

Add a short note where a newcomer will find it: the README quick-start or `docs/OPERATIONS.md`. Cover:

- `make hosted-setup` (one-time, before `make hosted-dev`)
- `make hosted-dev` (starts the full stack incl. coordinator)
- `make hosted-down` (tear down)
- The dev cohort labels and what they mean (results are dev-cohort, not production)
- The modal's two paths and what each requires

Keep it short. This is documentation, not a tutorial.

#### Files to touch

- `Makefile` — `hosted-dev` starts coordinator; add `hosted-setup` target
- `scripts/install.sh` — new file (create)
- `src/mldsafail/cli.py` — add `clone` subcommand
- `src/mldsafail/web/templates/base.html` — honest modal content (text only)
- `docs/OPERATIONS.md` or `README.md` — document `make hosted-setup` / `make hosted-dev` (brief)
- `docs/PLAN.md` — mark the onboarding items done as you complete them

Do **not** touch:
- `src/mldsafail/trusted/` (generator, verifier)
- `src/mldsafail/benchmark/` (runner, cost model, integrity)
- `config/profiles.toml`, `data/public_seeds.json`
- Container Dockerfiles, `compose.yaml`, `compose.dev.yaml` (beyond wiring the coordinator into the `up` list in the Makefile)
- `src/mldsafail/web/` beyond the modal template text (CSS/JS already done)
- The benchmark or solver code

#### Acceptance criteria

1. `make hosted-setup` creates the hidden-seeds file with mode 0400 and is idempotent.
2. `make hosted-dev` starts all four services including the coordinator; the coordinator container is running and polling.
3. `scripts/install.sh` is valid bash, safe to pipe to `sh`, and installs the `mldsafail` CLI.
4. `mldsafail clone [DIR]` creates a git repo with the two `__init__.py` files, commits, and prints path + SHA.
5. The modal on the dashboard shows honest content: local `uv sync` workflow, hosted CLI commands, no ecdsa.fail references, footer does not claim a skill exists.
6. `make web-smoke` still passes.
7. `make test` still passes — no regressions from the Makefile or CLI changes.

#### Guardrails

- Keep changes small and scoped. This is onboarding polish, not a refactor.
- The coordinator startup is the riskiest piece — verify the dev-compose env vars match what `coordinator.py:main()` expects. The hidden-seeds file must exist before the coordinator starts, or it fails at init.
- Don't hardcode `/Users/jarrett/...` paths. Use the env var with a sensible default.
- The modal change is text-only. Don't change the dialog structure, CSS classes, or JS wiring.
- Commit with conventional-commit messages. Do not push.

#### Verification sequence

```sh
make hosted-setup        # one-time setup
make hosted-down         # clean slate
make hosted-dev          # start everything
# wait for containers to be healthy
curl -s http://localhost:8080/health/ready   # expect {"status":"ready"}
docker compose --env-file deploy/dev.env -f compose.yaml -f compose.dev.yaml logs coordinator --tail 20
make web-smoke           # smoke test passes
make test                # no regressions
```

Then manually: open the dashboard, click Participate, verify the modal content. Then test the new CLI:
```sh
uv run python -m mldsafail.cli clone /tmp/test-clone-workspace
# verify the repo, the files, the commit
```

Report what worked, what didn't, and any deviations from this spec.

### Phase 2 — Make Local Autoresearch Productive

**Goal**: Humans and coding agents can make and validate meaningful improvements without modifying the benchmark contract.

Build:

- Stronger test coverage
- Hidden-seed suite **not yet created — required before official full-suite scoring**
- Cost instrumentation (done)
- Regression comparison
- Simple experiment workflow (done — Section 16)
- Automatic result recording (done)
- Best-result detection
- Benchmark-integrity checks (in progress)
- Clear editable/trusted boundaries (done)

Exit criterion:

- Multiple recorded experiments **partial — one baseline recorded for 0.4.0**
- At least one validated improvement over baseline **not yet attempted**
- Failed experiments preserved **working**
- Hidden evaluation working **not yet tested — requires hidden seeds**

**Status**: The local benchmark loop is functional (generate, solve, verify, score, record). What's missing is the hidden-seed evaluation path and meaningful test coverage for the lattice-reduction solver. The public-suite baseline exists but is not "official" in the hosted sense because it lacks hidden-seed coverage.

### Phase 3 — Build the Public Read-Only Product

**Goal**: Turn the research loop into a convincing local and deployable read-only product.

Build:

- Homepage **done**
- Headline improvement metric **done**
- Historical progress chart **done**
- Records view **done**
- Experiment detail view **done**
- Headline-score frontier **done**
- Methodology section **done**
- Basic ecdsa.fail-inspired layout **done**
- README **done**
- One-command local startup **done**
- Containerized web deployment and health checks **containerized, health checks exist, but not deployed/tested**
- Version bump across codebase **done (0.3.0 → 0.4.0)**
- Website content updated for 0.4.0 **done (about.html)**

Exit criterion: `make web` opens a complete local demo, while a documented deployment shows the same baseline, best-known valid solution, and history publicly.

**Status**: The local demo works (`make web` → http://127.0.0.1:5000). The containerized deployment path (compose.yaml, Dockerfiles) is updated for 0.4.0 but the hosted stack has not been deployed or verified end-to-end. The website currently displays only public-suite results; hidden-suite results would appear after the coordinator evaluates submissions.

### Phase 4 — Add Authenticated Participation

**Goal**: Contributors can authenticate and submit without weakening local usability.

Build:

- GitHub OAuth and secure browser sessions **stub exists in web/ but not configured in 0.4.0 deployment**
- Named API-token lifecycle **done (web/models.py, web/services.py)**
- CLI login and credential storage **done (cli.py)**
- Versioned submission/status API **done (web/api.py)**
- Relational schema and migrations **done (migrations/)**
- Rate limits and audit events **done (web/services.py)**
- Participant submission pages **done (templates/submissions.html, tokens.html)**

Exit criterion: A user can sign in, create and revoke a token, authenticate the CLI, create an immutable queued submission, and inspect its status; no submitted code runs in the web process.

**Status**: The infrastructure is implemented in the codebase — OAuth scaffolding, token lifecycle, CLI commands, API endpoints, database models. What's missing is the deployment configuration (OAuth client ID/secret, DATABASE_URL, environment variables) and a live deployment where a user can actually authenticate and submit. The CLI `mldsafail submit` command defaults to `--benchmark-version 0.4.0` and is functional for local testing against a hypothetical server.

### Phase 5 — Add Trusted Hosted Evaluation

**Goal**: Accepted submissions can safely enter the canonical leaderboard.

Build:

- Isolated disposable workers **implemented (evaluator/worker.py, Dockerfile.worker) but not deployed**
- Server-only hidden suites **not yet created — required for official evaluation**
- Source allowlisting and trusted-checkout assembly **specified (PLAN.md Section 18), not tested**
- Resource and network isolation **specified, Docker profiles exist**
- Signed result envelopes and coordinator validation **implemented (evaluator/envelope.py, coordinator.py)**
- Retry, timeout, cancellation, and sanitized-log behavior **specified**
- Canonical leaderboard promotion **specified**

Exit criterion: An untrusted eligible submission is evaluated end to end, cannot access hidden inputs or service credentials, and appears on the leaderboard only after independent server verification.

**Status**: The evaluator components exist in the codebase (coordinator, worker, solver_child, envelope signing) and have been updated for 0.4.0. The `solver_child.py` now supports both `lazy` and `lattice` solvers. What's missing: the hidden-seed file, Docker image builds for 0.4.0 tags, a running PostgreSQL database, a deployed coordinator, and an end-to-end test where a submission is accepted, evaluated in an isolated worker, and appears on the leaderboard. The compose.yaml is updated with 0.4.0 image tags and environment variables but has not been deployed.

### Phase 6 — Production Hardening and Launch

**Goal**: The complete product is operable, recoverable, and safe to expose publicly.

Build:

- Production configuration and secret injection
- TLS and secure headers
- Backup and restore procedures
- Monitoring, alerting, structured logs, and queue dashboards
- Abuse controls and administrative token/submission revocation
- Deployment, rollback, migration, and incident runbooks
- End-to-end staging and load tests

Exit criterion: A fresh environment can be deployed from documentation, survives a restore exercise, exposes health signals, and supports the complete browser-to-CLI-to-leaderboard flow.

---

## 22. Parallel Workstreams

Once the benchmark contract stabilizes, human and agent contributors can work in parallel.

### Track A — Mathematics

Improve:

- Lattice data structures
- Basis operations
- Reduction algorithms
- Polynomial arithmetic (if the problem moves to polynomial rings)
- Numerical stability and correctness

### Track B — Solver Optimization

Explore:

- Caching
- Incremental updates
- Pruning
- Heuristics
- Ordering
- Precision reduction
- Memory reuse
- Alternative reduction strategies (LLL, BKZ, sieving, enumeration)

### Track C — Benchmark Infrastructure

Improve:

- Instrumentation granularity
- Profiling
- Deterministic execution
- Regression detection
- Result comparison
- Fingerprint and integrity validation

### Track D — Web UI

Implement:

- Homepage
- History chart
- Records views
- Authenticated participant area
- Leaderboard

### Track E — Challenge Design

Explore:

- Whether the current modular-system problem is the right target
- Whether to add a direct lattice-reduction problem
- Whether to add polynomial-ring module-lattice instances
- Which cost metric best captures the binding constraint
- Whether to add quantum-circuit-related scoring for reduction circuits

---

## 23. Open Questions and Known Uncertainties

### 23.1 Is the Current Problem the Right One?

**Status**: Open.

The current challenge is: given `A`, `t`, `q`, `η`, find `c` in `[-η, η]` with `A*c ≡ t (mod q)`. This is a modular linear system with a bounded solution.

This is a synthetic proxy for a lattice problem, but it is not obviously the same as "perform lattice reduction on a module lattice." Candidate B attempted LLL on a constructed lattice and failed to find valid short vectors. Candidate A solved the modular system directly via Gaussian elimination, which is correct but may not be testing lattice reduction at all.

**Questions to resolve**:

- Should the challenge be reframed as a direct lattice problem (e.g., given a lattice basis, find a short vector)?
- Should the modular-system problem be kept as a self-contained synthetic challenge that is related to but not identical to the lattice reduction step?
- Should we add multiple problem types to test different aspects of the attack pipeline?
- Is the current scoring (abstract operation count) the right metric, or should it be something more like circuit cost, enumeration nodes, or reduction steps?

### 23.2 Is Lattice Reduction the Binding Constraint?

**Status**: Hypothesis, not confirmed.

The TRANSCRIPT.md discussion hypothesized that lattice reduction is the hardest step. This is plausible but not proven for ML-DSA specifically. Other steps (enumeration, hybrid search, verification) may also be significant.

**Questions to resolve**:

- For ML-DSA specifically, which step dominates the attack cost?
- Is it reduction, enumeration, or a combination?
- Does the answer change for classical vs. quantum attacks?
- Does the answer change for different ML-DSA security levels?

### 23.3 What Is the Right Cost Metric?

**Status**: Open.

The current metric is abstract operation count with unit weights. This is hardware-independent and easy to measure, but it may not capture the resource pressure that matters for the real attack.

ecdsa.fail uses qubit × Toffoli, which is a specific quantum circuit metric. For ML-DSA, the analogous metric might be:

- Classical: operations, memory, or time complexity
- Quantum: qubits × gates, or some circuit cost metric for the reduction step
- Hybrid: a combined classical/quantum cost model

**Questions to resolve**:

- What resource metric best captures the binding constraint for ML-DSA attacks?
- Should the benchmark support multiple metrics and rank by one primary?
- Is abstract operation count a sufficient proxy, or do we need something more specific?

### 23.4 What Problem Size Is Appropriate?

**Status**: Current profiles are very small (n=8,16,24).

This is intentional for rapid iteration, but it limits the relevance to real ML-DSA. Larger instances would be more representative but slower to evaluate.

**Questions to resolve**:

- What is the largest instance size that still allows rapid local iteration?
- Should we add a "xlarge" profile for more representative sizes?
- How do we ensure that optimizations at small sizes transfer (or don't) to larger sizes?

### 23.5 Candidate B Failure

**Status**: Candidate B (LLL lattice reduction) fails to find valid solutions on current instances.

This could be because:

- The lattice construction is wrong for the problem
- The LLL implementation has a bug
- The Babai/pair/triple extraction is insufficient
- The problem is not actually a lattice problem in the way Candidate B assumed

**Questions to resolve**:

- Is Candidate B's approach fundamentally correct for this problem, and the implementation needs fixing?
- Or is the modular-system problem not the right target for a lattice-reduction-focused challenge?
- Should we debug Candidate B thoroughly, or reconsider the problem design?

### 23.6 Relationship to Real ML-DSA

**Status**: Intentional distance.

The project is explicitly a synthetic stand-in, not a real ML-DSA attack. The current instances are very small and use integer matrices, not polynomial rings or module lattices.

**Questions to resolve**:

- How much ML-DSA structural fidelity do we want? (Polynomial rings? Module lattices? Specific distributions?)
- At what point does adding ML-DSA structure make the problem harder to solve but more relevant?
- What is the minimum structural similarity needed for the benchmark to be meaningful as an ML-DSA analogue?

---

## 24. Appendix: Relationship to ecdsa.fail

### 24.1 What ecdsa.fail Does

- **Target**: Most resource-efficient quantum circuit for elliptic curve point addition on secp256k1.
- **Why**: EC addition is the bottleneck in Shor's algorithm, which is the quantum algorithm for breaking ECDSA (Bitcoin's signature scheme).
- **Score**: Qubit × Toffoli (qubit count × Toffoli gate count). Lower is better.
- **Participation**: Clone the benchmark repo, improve the circuit locally, measure with CLI, submit to platform for verification.
- **Verification**: Reversible circuit simulators adapted from Google's original codebase.
- **Transparency**: GitHub repo is public, results are public, participants can sync to best submission.

### 24.2 What This Project Aims to Do

- **Target**: Most operation-efficient solver for a synthetic lattice problem motivated by ML-DSA.
- **Why**: Lattice reduction is hypothesized to be the bottleneck in attacking ML-DSA.
- **Score**: Abstract operation count (versioned, unit-weighted). Lower is better.
- **Participation**: Clone the benchmark repo, improve the solver locally, measure with CLI, submit to platform for verification (when hosted).
- **Verification**: Independent verifier in trusted code.
- **Transparency**: Experiment log is append-only, results are recorded, participants can iterate locally.

### 24.3 Key Differences

| Aspect | ecdsa.fail | This project |
|--------|-----------|--------------|
| Target primitive | EC point addition (specific circuit) | Lattice reduction / modular system (algorithmic) |
| Metric | Qubit × Toffoli (quantum circuit) | Abstract operation count (algorithmic) |
| Editable surface | Circuit files | Solver code |
| Underlying problem | Specific curve, specific operation | Synthetic lattice problem, profile-configurable |
| Quantum vs classical | Quantum circuit optimization | Classical algorithm optimization (for now) |
| Real attack relevance | Direct component of Shor's algorithm | Synthetic proxy for ML-DSA attack |

### 24.4 Design Lessons from ecdsa.fail

1. **Isolate one precise bottleneck**: Don't try to optimize the whole attack. Pick one step and make it the challenge.
2. **Pick a concrete, measurable metric**: Qubit × Toffoli is specific and meaningful. Abstract operation count is less physical but still deterministic and comparable.
3. **Freeze the problem statement**: The challenge contract should be precise enough that two independent implementations get the same validity decision and score.
4. **Make local iteration cheap**: Participants should be able to test improvements in seconds, not hours.
5. **Separate trusted evaluation from editable code**: The verifier and generator are trusted; the solver is editable.
6. **Record everything**: Failed experiments are informative. Don't delete them.
7. **Make the leaderboard public and transparent**: Participants should see the frontier and understand how their submission compares.

---

## 25. Appendix: Relationship to ML-DSA

### 25.1 ML-DSA (Dilithium) Overview

ML-DSA is a lattice-based digital signature scheme selected by NIST as a post-quantum standard. Its security relies on the hardness of lattice problems over polynomial rings, specifically:

- **ML-DSA key generation**: Produces a public key consisting of a matrix polynomial `t` derived from a secret matrix polynomial `s` and a small error polynomial `e`, over the ring `R = Z_q[X]/(X^n + 1)`.
- **ML-DSA signing**: Produces a signature using a challenge derived from a random polynomial `y`, the secret `s`, and a small error `c`.
- **ML-DSA verification**: Checks that the signature satisfies a relation involving the public key and the challenge.

The hardness assumption is that recovering `s` from `t` (or finding a valid signature without `s`) reduces to hard lattice problems like Module-SIS or Module-LWE.

### 25.2 Why Lattice Reduction Matters

The leading attacks on lattice-based schemes involve:

1. **Lattice reduction**: Use LLL, BKZ, or sieving to find short vectors in the relevant module lattice. This is often the most expensive step.
2. **Enumeration**: After reduction, enumerate short vectors to find the specific one that satisfies the cryptographic relation.
3. **Hybrid attacks**: Combine reduction with enumeration or other techniques to balance the cost.

For ML-DSA specifically, the attack surface includes:

- Recovering the secret key from the public key (key recovery attack).
- Forging signatures without the secret key (universal or existential forgery).
- Analyzing the specific structure of ML-DSA's module lattices and polynomial ring to find optimizations.

### 25.3 How the Toy Problem Relates

The current toy problem is:

- **Given**: An integer matrix `A` over `Z/qZ` and a target `t = A*s mod q` with `s` bounded in `[-η, η]`.
- **Find**: The bounded vector `c` satisfying the relation.

This is a **modular linear system with a bounded solution**, which is a simplified proxy for:

- The relationship between ML-DSA's public key `t` and secret key `s` (which is also a modular relation with bounded coefficients).
- The lattice problem of finding a short vector in a lattice defined by the relation.

Key differences from real ML-DSA:

| Aspect | Toy Problem | Real ML-DSA |
|--------|-----------|--------------|
| Ring | Integers Z/qZ | Polynomial ring Z_q[X]/(X^n+1) |
| Structure | Single square matrix | Module lattice with matrix polynomials |
| Size | n=8,16,24 | n=256,512,1024 (power of 2) |
| Modulus | q=97,257,769 | q≈2^13 to 2^23 |
| Bound | η=2,3,4 | η≈2 to 4 (ML-DSA parameter) |
| Error term | None (exact relation) | Small error in key generation |
| Solution | Unique (invertible matrix) | May not be unique; depends on lattice structure |

The toy problem captures the **bounded modular relation** aspect but not the polynomial-ring or module-lattice structure. Adding polynomial-ring structure would make the problem more ML-DSA-like but also more complex to implement and solve.

### 25.4 What Would Make the Benchmark More ML-DSA-Like?

Options, in increasing order of fidelity:

1. **Keep the integer-matrix problem** as a self-contained synthetic challenge, and treat it as a proxy for studying lattice reduction techniques.
2. **Add polynomial multiplication** as a primitive that solvers must implement efficiently, and score it alongside the modular system.
3. **Change the problem to a polynomial-ring modular system**, where `A` and `c` are polynomials over `Z_q[X]/(X^n+1)`, and the relation is polynomial multiplication modulo the ring.
4. **Change the problem to a module-lattice reduction problem**, where solvers are given a module-lattice basis and must find a short vector or perform a reduction step.
5. **Add multiple problem types** that test different aspects of the attack pipeline, with a combined or multi-track leaderboard.

Each option trades off fidelity to ML-DSA against simplicity and speed of evaluation. The current project has started with option 1. The open question is whether to evolve toward options 2-5.

---

## 26. Appendix: Glossary

- **Lattice**: A discrete additive subgroup of R^n. In cryptography, lattices are used to define hard problems like SVP (shortest vector problem) and CVP (closest vector problem).
- **Basis**: A set of linearly independent vectors that generate the lattice.
- **LLL (Lenstra-Lenstra-Lovász)**: A polynomial-time lattice reduction algorithm that produces a relatively short basis. Often used as a preprocessing step for more expensive algorithms.
- **BKZ (Block Korkin-Zolotarev)**: A lattice reduction algorithm that generalizes LLL to larger blocks, producing shorter vectors at higher computational cost.
- **Sieving**: A lattice reduction technique that finds short vectors by sampling and reducing, often used in high-dimensional attacks.
- **Enumeration**: A search technique that finds short vectors by exploring a tree of possibilities, often used after reduction to find the shortest vector in a reduced basis.
- **Module lattice**: A lattice with additional structure from a module over a polynomial ring, as used in ML-DSA and other lattice-based schemes.
- **Polynomial ring**: The ring `R = Z_q[X]/(X^n + 1)`, where `n` is a power of 2, used in ML-DSA and other lattice-based schemes.
- **Short vector**: A vector in a lattice with small Euclidean norm. Finding short vectors is the core hard problem in lattice-based cryptography.
- **Bounded vector**: A vector whose coefficients are bounded in absolute value by some `η`.
- **Modular relation**: An equation of the form `A*c ≡ t (mod q)`, where `A` is a matrix, `c` and `t` are vectors, and `q` is a modulus.
- **η (eta)**: The bound on the absolute value of coefficients in the secret or solution vector.
- **Abstract operation count**: A hardware-independent measure of algorithmic cost, counting operations like additions, multiplications, modular reductions, memory reads/writes, etc.
- **Operation meter**: A trusted instrument that counts operations performed by a solver, used to compute the benchmark score.
- **Trusted code**: Code that defines the challenge (generator, verifier, benchmark infrastructure) and must not be modified during solver experiments.
- **Editable code**: Code that participants optimize (solvers, math primitives).
- **Profile**: A configuration of instance parameters (dimension, modulus, bound, seeds) that defines a difficulty level.
- **Public seeds**: Seeds visible to participants, used for local development.
- **Hidden seeds**: Seeds not visible to participants, used for official evaluation.
- **Suite**: A set of instances to evaluate: public, hidden, or full (both).
- **Experiment**: A single benchmark run with a specific solver, hypothesis, and metadata, recorded in the JSONL log.
- **Frontier**: The lowest valid headline score achieved so far, on the full public-plus-hidden suite with a matching trusted fingerprint.
- **Baseline**: The first validated reference result, used as the starting point for measuring improvement.
- **Fingerprint**: A hash of the trusted input files, used to verify that the benchmark contract has not changed.

---

## 27. Appendix: References

- NIST FIPS 204: ML-DSA (Dilithium) specification.
- ecdsa.fail: https://ecdsa.fail/ — the inspiration for the participation model and challenge structure.
- Lattice cryptography surveys and textbooks for background on SVP, CVP, LLL, BKZ, and enumeration.
- TRANSCRIPT.md in this repository for the source conversation that motivated the project direction.

---

*This document is the authoritative project specification. If you find a contradiction between this document and any other file in the repository, treat it as a bug and resolve it by updating the other file to match this document, or by proposing a change to this document if the other file reflects a genuine improvement.*

*Last updated: 2026-08-23*
