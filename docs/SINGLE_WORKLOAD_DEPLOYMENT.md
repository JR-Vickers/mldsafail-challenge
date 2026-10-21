# Single-workload engineering review, 2026-10-21

This is an incomplete local implementation and a blocked deployment review
packet. It is not production readiness or execution authority. Budget remains $0;
no capacity experiment, deployment, epoch, provisioning, notification, benchmark,
or abandoned diagnostic is authorized by this document. Scope remains 0.5.0
preview; 0.6.0, supplied credentials and deferred backups are unchanged.

## Implemented source

The evaluator's `workload.py` provides an exclusive host file lock, private
fsync/replace journal, boot/daemon/workload bindings, durable launch intent,
inspected-birth adapter contract, cleanup-only reconciliation, persistent pause
and explicit resume. Participant and administrative adapters must share the
same host root, regardless of database identity. WorkloadSession monitors at
250 ms and requests termination on a protection violation. Completion checks
protection before and after cleanup. ResourcePolicy specifies the conservative
1 GiB reserve, one CPU, 448 PIDs, zero swap, 256 MiB availability abort floor,
95% operation-memory threshold, 5 GiB disk floor, 128 MiB logs and 1 GiB generation
output. These numbers are policy, not measured demand or a fit guarantee.

Expired queue leases now remain claimed/running unless an explicit reconciler
supplies verified termination. Existing attempt limits still apply after that
verification. No database schema migration is needed. Legacy expired jobs remain
blocked; do not reset their statuses or infer worker death from database expiry.
The proof callback is an internal adapter contract, not an operator checkbox.

The v4 operational-evidence validator binds the policy hash, runtime identities,
structured control evidence files, freshness and a separately scoped owner authorization to
exact serialized packet bytes. Older v2/v3 capacity requirements are unchanged.
The production epoch entrypoint still rejects v4: enabling it before the missing
runtime is implemented would create an unsafe policy bypass.

## Unfinished implementation and acceptance gates

The private Linux Unix socket transport and bounded helper transport now exist
as library components (`workload_socket.py` and `runtime_io.py`). The socket
checks SO_PEERCRED UID, enforces owner-only directory/socket permissions, rejects
arbitrary launch specifications, bounds client reads and retains durable request
outcomes and unresolved intents. Mutation IDs use durable `generation:sequence` counters. The replay window
retains the latest 64 completed outcomes; evicted sequences and expired workload
generations are rejected without execution. Sixteen compact completed-workload
records are retained, and unresolved intents are never evicted. The unresolved
ledger still blocks safely if it reaches its 1,024-entry bound. A lost acquire acknowledgement conservatively blocks ownership if it
falls between the acquisition and response journal writes. Recovery never repeats
an ambiguous mutation.

Journal reads validate schema, policy hash, lifecycle shape, identity fields,
request ledger and private regular-file ownership; duplicate JSON keys, oversized
files, symlinks and inode replacement are rejected. Completed ownership cannot
be reopened through bind or launch. Helper I/O uses nonblocking pipes and an
800 ms deadline without reader threads; unresolved helpers retain process handles
and block subsequent helper calls. A late sample aborts at one second. This does
not make unbounded legacy callbacks safe: the bounded transport is not yet wired
to a reviewed native adapter.

The native runtime adapter, runnable daemon/client integration, Docker router
generalization, coordinator integration and administrative integration are not
implemented. The new gate therefore does not yet enforce production exclusivity.
No current launch path may claim protection from this library. The existing web
service receives no additional endpoint or Docker access.

The runtime must launch every controller, acquisition process, Docker client and
worker in one inspected heavy subtree, with tmpfs and charged page cache included;
keep the supervisor outside it and charge control overhead to the reserve.
Derive memory.max from physical RAM minus reserve and every available ancestor
allowance, bind cgroup birth identities, retain frozen per-worker limits and
service limits, and prevent launch before preflight. All adapter I/O must have
independent deadlines and survive lost acknowledgements. The current library
assumes bounded adapter callbacks; it does not itself kill a stuck callback.
Supervisor death must independently terminate the subtree, preserving the journal.
Never certify an ordinary process thread as that independent death barrier.

Coordinator acquisition must precede claim and source acquisition. Low resources
must defer without an attempt. Protection aborts require no result/score and no
automatic retry; database disconnection cannot release host ownership. Result
commit must follow monitored cleanup and postflight. Maintenance retains the
existing zero-pending transaction fence and cannot bypass accepted queued work.
New adapter source changes the hosted evaluator fingerprint and requires matching
release/configuration evidence; historical acceptance is insufficient.

Native VPS Linux acceptance, real cgroup hierarchy/parent OOM and
container cleanup tests remain unavailable in this local macOS verification.
A cached PostgreSQL 17.5 container in the local Linux VM passed all 36 disposable
loopback admission and maintenance-fence tests, including atomic queue limits,
competing claims, cleanup-authorized recovery and cancellation fencing. The
container and its tmpfs data were removed after verification. These tests exposed
and corrected legacy 0.4.0 admission fixtures; all inputs remain synthetic. Skipped tests are not certification. Complete
full/rate-limited admission, process/supervisor death, daemon replacement, lost
acknowledgement, database outage, output exhaustion, failed termination, monitor
loss and restart interference scenarios before enabling v4 execution.

## Offline packet and commands

From the repository root, prepare a new review packet without contacting a host:

```sh
source .venv/bin/activate
python -m scripts.prepare_workload_packet --output /tmp/mldsafail-workload-review-new.json
pytest tests/test_workload.py tests/test_workload_policy.py tests/test_evaluator.py tests/test_production_maintenance.py
make check
git diff --check
```

The retained [review packet](acceptance/production-preparation/workload-review.json)
binds implemented source and this runbook, discloses `unmeasured_capacity`, and
lists unresolved gates. It is intentionally a review schema rather than an
executable operation packet. No receipt asserts controls that have not passed.

## Deployment, delegation and recovery contract

Do not transfer or install this revision as a protected runtime. Exact executable
deployment/restoration commands cannot be approved until the daemon entrypoint,
unit names, delegated cgroup paths, socket ownership, target release/configuration
and retained rollback image IDs exist and have been inspected. Fabricated commands
would not constitute a concrete safe deployment procedure.

The final packet must bind those exact commands and bytes, owner-reviewed root
scheduling inventory, recursive trigger/reference closure, cgroup delegation,
zero-pending maintenance, original service restart settings and inspected birth
identities. Preserve 24-hour preparation and five-minute execution freshness,
source/image checks, one-attempt epoch authority and the existing restoration
safeguards. Require separate owner maintenance/transfer and epoch authorizations;
this packet requests neither.

On interrupted ownership: block scheduling, stop and verify only resources with
matching workload and birth identity, retain the journal and evidence, then run
cleanup-only reconciliation. A changed daemon or boot requires independent old
resource reconciliation; never kill replacements by name. Resume must be an
explicit operator action after fresh checks, never a consequence of reconciliation.
Do not resume computational phases.

Rollback must first verify owned resources are gone, retain the journal and pause,
and restore the inspected compatible installation without starting scheduling.
The old stale-lease recovery code is unsafe for unresolved resources: independently
fence its coordinator before rollback. Restore original settings only after
postflight and verified termination. No shared hardlink mutation or scientific
evidence deletion is part of this change.

## Current local checkpoint, 2026-10-21

Commit `6a8cf0e` adds journal validation, bounded helper I/O and the private socket
protocol. Focused verification: 47 passed, one Linux-only socket test skipped on
macOS. `make check`: 1,400 passed, 45 skipped, 12 warnings; frozen contract: 8
passed. These tests cover durable duplicate requests, changed request rejection,
lost launch acknowledgements, request replay across workloads, malformed journals,
helper deadlines and output caps. They do not certify the missing integrated
runtime or native VPS behavior. The structured evidence validator rejects hashed
arbitrary JSON; per-control semantic proof and the native records remain gates.
The previous retained review packet remains historical and unchanged.

No host was contacted, no solver executed and no epoch or capacity workload was
created. Exact installation/restoration commands remain blocked by uninspected
host delegation, scheduling and rollback identities as well as missing runnable
components. The native acceptance authorization is absent. This checkpoint does
not satisfy the requested integrated implementation or executable deployment
packet; those remain explicit engineering work, not merely an authorization gate.

## Previous local verification record

Final `make check`: 1,377 passed, 44 skipped, 12 warnings; the separate frozen
contract invocation passed 8 tests. The focused gate tests include a separate
process killed with SIGKILL: the kernel lock is released, but the retained journal
still blocks a replacement workload. Disposable PostgreSQL: 36 passed. Changed
runbook links resolve and `git diff --check` passes. None of these checks ran a
benchmark, created an epoch or contacted the VPS.


## Ownership and result-transaction checkpoint, 2026-10-21

The private protocol now requires a matching workload ownership token on every
mutation after acquisition, validates argument shape and lifecycle before durable
intent, and exposes separate `postflight`, `commit_intent`,
`acknowledge_commit` and `release` operations. Postflight verifies cleanup while
retaining host ownership. The dispatcher must journal a nonempty exact result
binding before its database transaction, reconcile an ambiguous database outcome
under the database transaction lock, and acknowledge that same binding before
release. Cleanup and resume cannot erase a pending commit. The socket no longer
exposes the combined `complete` compatibility helper. These are adapter contracts;
no current database dispatcher implements that transaction protocol yet.

Monitoring and launch adapter I/O no longer share the launch journal mutex.
Launch repeats resource preflight, rejects reduced ancestor allowance, and binds
its response to a workload and launch nonce. A protection check can detect a
failure and request cleanup while launch I/O is blocked. A late birth cannot
restore running state; outstanding launch responses block resume, acquisition
and release. Other legacy control methods still hold the journal mutex across
adapter I/O; runnable native monitoring and bounded control integration remain
engineering work. No unbounded adapter is made safe by these changes.

The protocol's mutation IDs must be canonical positive decimal
`generation:sequence` pairs. Acquisition uses the next workload generation;
subsequent new mutations use the current generation and a sequence above the
durable high-water mark. A client must persist and retry the exact request after
a transport failure. Once its outcome leaves the replay window, reconciliation
is required; replay cannot execute it again. Status is private and read-only.
Completed prior-generation requests are deliberately expired when a new workload
is acquired, rather than replayed against its new owner.

Local synthetic tests cover retained postflight ownership, matching commit
acknowledgements across restart, invalid requests leaving journal bytes unchanged,
bounded request/workload retention, expired replay, shrinking launch headroom,
and a blocked launcher with concurrent protection failure and rejected late birth.
These checks do not implement native acceptance. Production coordinator/admin
routing, the native runtime and runnable daemon/client/cleanup entrypoints,
filesystem output enforcement, independent systemd cleanup, database commit
reconciliation and control-specific v4 evidence remain missing implementation.
The requested complete deployment packet cannot yet be generated. Exact VPS
scheduling/delegation/rollback identities and separate native authorization remain
additional prerequisites. No host operation, solver run or epoch was performed.

Verification for this checkpoint: focused workload/protocol tests passed 38 with
one Linux-only socket test skipped; `make check` passed 1,406 with 45 skipped and
12 warnings, followed by all eight frozen contract checks. Skips remain explicit
native/database acceptance limitations. Changed local documentation links and
`git diff --check` were checked separately.
