# Proposed MLWE benchmark 0.6.0 contract

Status: review pending; **not adopted, integrated, or the production default**.
This document records the requested measurement change separately from the frozen
0.5.0 contract. Native feasibility, isolation, repeatability, hosted correctness
and operational acceptance must all pass before adoption. Existing 0.5.0 workers,
epochs, reference tables, evidence, scores and participant releases remain valid
only within their original cohorts.

## Problem and scoring

Use only repository-generated fixed tiny MLWE bounded-recovery profiles from
PRIMITIVE_SELECTION_SPEC.md. The public input, approved Python-only contestant
source contract, independent mathematical verifier, repetitions, warmups,
five-cell equal-weight geometric aggregation, anchored 1% ties and 2,000-draw
profile/seed-cluster bootstrap remain as specified there. No production ML-DSA
parameters or externally supplied cryptographic targets are accepted.

Successful execution cost is kernel CPU usage for the entire exclusive dedicated
worker accounting domain, including startup, interpreter/import work, parsing,
solving, serialization and all child/grandchild work. Use the median of the three
successful measured invocations, floored at one microsecond. Ordinary crashes,
timeouts, resource caps and no-answer cases retain the frozen 60-second penalty;
invalid candidates make a run ineligible. Host verification determines correctness.
Contestant output cannot supply authoritative timing or verification decisions.

## Trusted host supervisor

The host provisions an exclusive delegated cgroup-v2 accounting parent and
serializes its ownership across all supervisors. Read usage_usec before container
creation. Prove the live worker PID belongs strictly beneath that parent before
delivering public input. Workers receive no writable cgroup controls, host sockets,
evaluator state, private instance state, prior evidence or credentials. Preserve
the existing frozen network, source, output, CPU, memory, PID and wall restrictions.

Terminate the worker and all descendants, prove the parent is unpopulated, then
read final usage_usec. Keep the parent and ownership until counter evidence and
cleanup state are durably published. Counters cannot regress. Missing counters,
membership failure, accounting contamination, delegation failure, surviving
processes or unsuccessful cleanup are infrastructure failures, never penalty
scores. Retry under the existing bounded three-attempt/backoff policy, then fail
without publishing a result. Partial and failed evidence must remain available.

Private records bind method, before/after counters, supervisor source identity,
worker image, kernel, Docker/cgroup configuration, host and epoch provenance,
public-input delivery proof, verifier decision and cleanup state. Independent
host audit recomputes every score and validates completion. Public summaries
exclude raw private evidence and host paths.

## Predeclared native measurement gate

On the same idle native Linux host, run at least 30 sequential empty-worker /
deterministic CPU-fixture pairs. Require deterministic CPU coefficient of
variation <=0.05, empty-worker median CPU <=250,000 microseconds, and empty-worker
wall nearest-rank p95 <=5 seconds. Empty-worker CV is reported only. Preserve
failures and never relax thresholds after observing results.

Test forged timings, clock tampering, child/grandchild computation, early exit,
malformed output, output flooding, timeouts with descendants, incorrect delegation,
missing/regressing counters, contamination, concurrent ownership and cleanup
failures. Local simulated tests do not establish native acceptance.

## Integration and release gate

After separate contract review and successful native measurements, implement
version-aware evaluator dispatch, evidence/audit validation, API and CLI selection
and separate leaderboard cohorts. Create fresh per-host 0.6.0 epochs and audited
reference costs; never convert 0.5.0 scores or reuse its costs. Rebuild and review
a separately identified worker and participant release. Complete native correctness,
isolation, reproducibility and hosted acceptance before proposing a production
default switch. Production deployment and public exposure require owner approval
of a concrete release and acceptance packet. This proposal alone grants no switch.
