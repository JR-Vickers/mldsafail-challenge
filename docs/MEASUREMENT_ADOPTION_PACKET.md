# Proposed 0.6.0 contract and future-default decisions

**No adoption or activation is approved.** This packet prepares two separate
owner decisions. Current evidence does not support either activation: generation
G failed the predeclared native measurement thresholds, and acceptance of the
new prospective artifact remains pending. The machine-readable companion
[decision.json](acceptance/v060-contract-decision/decision.json) contains explicit evidence and decision slots.
It is a review packet, not an evaluator authority or application configuration.

The reviewed engineering checkpoint is
`b0421cdcda842e4dd6c4b43fafd90541a7ae0cd2`, incorporating the approved offline
native artifact preparation at `b232c544ff4823da13775eaa1e5bbbdf68500936`.
The exact proposed CPU source family is
`748477a7faad41e4adf913f6fd0c7a4602a769b6f1e206ca6bac22d218fa35de`.
An executable release may contain separately reviewed operational changes, but
its retained commit, this source-family digest, worker context/image/archive,
reference authority and environment must be recorded and checked together.
A source checkpoint, retained archive or local test does not supply native proof.

| Question | Frozen0.5.0 | Proposed0.6.0 candidate |
| --- | --- | --- |
| Successful CPU measurement | Cooperative worker clock after trusted adapter imports; parsing, contestant loading, lazy mathematical imports and verification included; startup and final serialization excluded | Host-observed kernel CPU for the entire exclusive worker domain, including startup, imports and descendants |
| Source/public input/verifier | Existing frozen tiny profiles and approved Python contract | Same scientific profiles and independent verifier; separate versioned accounting evidence |
| Repetitions and ordinary failure | Exactly three measured invocations; whole-case frozen60-second penalty | Exactly three measured invocations; same whole-case ordinary-failure penalty |
| Invalid accounting or surviving cleanup | Existing frozen semantics and acceptance limitations retained | Infrastructure failure, fenced ownership and no score |
| Evidence/reference/cohort | Existing0.5 epochs and costs unchanged | New independently audited versioned evidence, fresh epochs and costs, separate cohort |
| Default | Existing private staging0.5 | Inactive candidate; explicit owner decision required |


## Decision 1: adopt an explicit 0.6.0 score contract

The proposed score counts authoritative hierarchical cgroup-v2 `usage_usec`
from before creation of a worker to after its removal and all descendant exit.
Interpreter startup, worker imports, parsing, contestant computation and
serialization remain charged. Operator clients use a separate delegated
parent; no contestant timing field, startup subtraction or historical cost
conversion is permitted. Correctness is verified independently outside the
untrusted worker. The host, kernel, isolated rootless daemon, trusted operator,
exclusive cgroup delegation and auditor form the declared trust boundary.

Each case has one unscored warmup and **exactly three** independently audited
measured invocations. Three successful verified invocations use their median
CPU, floored at one microsecond. Any ordinary failure makes the entire case
cost 60,000,000 microseconds; an invalid decoded candidate makes the submission
ineligible. Missing/invalid accounting, unfinished cleanup, incomplete invocation
sets and the fixed 1,200-second whole-evaluation deadline are infrastructure
failures and never replacement scores. A worker's ordinary limit remains
60 seconds. Private evidence retains failures, bounded raw output, source,
input, generation ownership and independent dispositions.

A fresh epoch contains 100 distinct repository-generated tiny instances: twenty
per each of the five unchanged challenge cells. Fresh per-host reference costs
must bind that exact epoch, source, immutable worker, environment and independent
reference audit. A separately authenticated sealed reference authority is
required; a draft table is inadmissible. The independent reference viability
floor remains 18/20 successful cases in each cell. Scoring minimizes the equal
cell-weighted geometric mean of case CPU/reference ratios. Competitive ranks
retain anchored 1% ties. No confidence-interval or cross-version comparability
claim is supplied by this packet.

The owner may choose:

1. **Defer adoption**: retain inactive preparatory code and collect missing proof.
2. **Adopt explicit 0.6.0 after reviewing completed evidence**: approve only the
   bound prospective contract and its separately identified cohorts. This does
   not approve a default change, production activation or public exposure.
3. **Request a contract revision**: state the required change. A change to score
   meaning or a threshold requires an explicit decision, updated reviewed
   protocol/version identity and fresh applicable gates; it cannot erase G.

The choice is currently `null`. The implementing agent cannot select it.

## Evidence required before adoption is actionable

Generation G used the retained frozen 0.5.0 image, completed its native fault
suite and all thirty sequential pairs, and failed the paired gate: deterministic
child CV **0.1164559302 > 0.05** and empty median CPU
**395,795 > 250,000 microseconds**. Empty wall p95 was 2.893689 seconds and passed
the fixed five-second limit. The child median was 640,808.5 microseconds.
Reported whole-domain cleanup passed. These are historical outcomes on that
artifact, not acceptance of the proposed worker. Raw evidence stays protected;
operator-supplied sanitized references must fill the historical slot.

The prospective artifact removes an unnecessary import of the frozen timing
adapter, retaining identical address-space/affinity limits and required solver
modules. It uses a separately named AMD64 dependency lock, byte-identical to the
previously approved native deployment lock, SHA256
`35890cf7c5ed544124dc4cc86269009f11d029a5388d1627b6899e986650c1f0`.
Approved native wheel bytes and their actual retained provenance are part of
both context digests. Frozen 0.5.0 files, costs, results and epochs stay intact.
This is a justified changed-artifact experiment, not another attempt on unchanged
G code to obtain favorable numbers.

The new artifact requires separate supervisor/auditor acceptance, the complete
native fault suite, and at least thirty sequential empty/child pairs under the
unchanged limits: child CV at most 5%, empty median CPU at most 250,000
microseconds, empty wall nearest-rank p95 at most five seconds, and demonstrated
descendant accounting. Preserve every failure; do not average separate attempts
or discard outliers. Exact-source reference/audit/sealing and native API/CLI,
queue, signed evidence, cohort privacy, compatibility, deadline and cleanup
acceptance must then pass. No current evidence slot claims these passed.

| Evidence identity | Current disposition |
| --- | --- |
| Candidate clean source commit and tree | Bind exact coherent candidate checkpoint; later fixes remain separate |
| Contract document SHA and source | Pending exact final binding |
| Worker image/context SHA and approved AMD64 lock35890 | Separately reviewed candidate build/provenance; actual retained artifact receipt required |
| Independent supervisor and auditor source receipts | Bind exact current CPU source digest; historical receipts do not cover later source changes |
| Native fault suite and30 paired protocol/result | Earlier G failure retained; final changed-artifact acceptance pending |
| Fresh100-case reference table, independent audit and sealing authority | Inactive candidate tooling prepared; native source/image-bound evidence required |
| Explicit CLI/API acknowledgement and idempotency | Separately reviewed candidate source; native acceptance required |
| Separate evidence/cohort/default/privacy behavior | Native candidate application receipt required |
| Candidate production configuration and disposable full rehearsal | Prepare before adoption; owner production/default activation remains separate |
| Candidate participant wheel/archive/install/privacy/reproduction | Prepare and retain before publication approval |
| Recovery/load/monitoring/capacity and incident evidence | Bind canonical launch ledger, preserving external blockers |


## Decision 2: select a future production default

This decision is separate and remains blocked until the contract decision and
all applicable production launch gates are accepted. The owner may:

1. **Keep existing version defaults** while making any approved 0.6.0 route an
   explicit opt-in. Legacy 0.4/0.5 routing and records retain their own meaning.
2. **Approve 0.6.0 as a future production default** for the specifically bound
   new production environment and epoch after all prerequisites pass.
3. **Defer the default decision** pending operating or pilot evidence.

Approving a future default alone does not authorize deployment, public exposure,
release publication, purchases or recruitment. Production activation requires
its own explicit owner approval and an exact reviewed release/configuration
packet. No staging epoch may become production through conversion or reuse.

Before that approval can be exercised, complete and bind the separate production
volumes, evaluator roots, secrets, repositories, authentication/TLS/private
operational endpoints and explicit migration handling; fresh production-like
submission-to-leaderboard, recovery, rollback, isolation, monitoring and capacity
rehearsals; source-bound participant artifacts and documentation; protected
backup/restore custody and storage; and required pilot/go-no-go evidence. Owner
credentials, storage/service provisioning, publication, public exposure and
participant-dependent outcomes remain their own external dependencies.

## Compatibility and recording rules

The proposed registry is disabled by default. Candidate rehearsal authority is
explicitly private and always `contract_adopted=False`; only a testing
configuration can expose its explicit 0.6.0 route. It can never choose a default.
An explicit 0.6.0 CLI submission performs an authenticated capability preflight
before POST and durably retains its idempotency intent before submission.
Unsupported versions fail closed without historical evaluator fallback.

Cohorts bind benchmark version, fresh epoch, evaluator/source family, hidden
suite, worker identity, environment and measurement method. Separate signed
0.6.0 evidence is independently audited; reference and result signing authorities
are distinct. Leaderboards filter exact version/cohort. Historical results and
reference costs cannot be relabeled or compared as equivalent CPU measurements.

For every evidence slot, record the exact retained release/image/context,
protocol, environment, private receipt hash, sanitized reference, reviewer and
outcome. A missing slot remains pending. A failed slot retains its attempt;
only a corrected source/artifact and new predeclared protocol can add a successor.
Do not put credentials, raw private cases, filesystem locations or infrastructure
addresses in this committed packet. An owner decision needs identity, timestamp,
chosen scope and the accepted evidence packet hash. The companion remains
`launch_approved=false`, `contract_adopted=false`, `default_approved=false` until
actual separate decisions exist; filling a template is not authorization.
