# Shared workload deployment and recovery

The local integrated runtime routes production participant work and v4 administrative
creation, reference and audit through one private supervisor. Deployment and native
acceptance have not run. This packet grants no execution authority. Retain the
0.5.0 preview, existing VPS and $0 budget; no solver runs, capacity measurements,
production epoch, public listener or activation belong to this phase.

## Installed control model

`mldsafail.evaluator.workload_service serve` owns the physical-host file lock for
its lifetime. Its private Unix socket checks Linux peer UID, bounds reads to
800 ms, limits concurrent clients and accepts configured roles rather than caller
commands. The persistent dispatcher and supervisor stay outside
`mldsafail-heavy.slice`. Source acquisition, controllers, launch helpers and
workers run inside inspected descendants. The production coordinator has no
Docker socket mount or socket permission startup step.

The journal binds boot ID, daemon process/socket identity, supervisor generation,
workload and process/cgroup/container births. Mutation requests require the current
ownership token and durable generation/sequence ID. Completed replay outcomes are
bounded to 64, recent compact workloads to 16; expired generations/sequences never
execute. Unresolved intents are retained. At the unresolved limit, scheduling
blocks until verified cleanup and explicit compaction. Permanent compact records
under `root/records` retain ownership and outcome evidence without an expanding
request ledger. Malformed, replaced or nonprivate journals block execution.

Monitoring runs independently every 250 ms; adapter subprocess reads have an
800 ms deadline and sample age over one second aborts. Launch/control I/O does
not hold the journal mutex. Container create and start have separate durable
intents and inspected acknowledgements. Frozen evaluator commands, worker images,
limits and benchmark execution bytes are preserved by the configured Docker router.
Fast completed containers require kernel containment evidence as well as immutable
configuration and birth identities.

## Resource and output enforcement

Admission and launch verify cgroup v2 delegation, cpu/memory/pids controllers,
ancestor births/allowances, at least 1 GiB available host RAM and 5 GiB backing
filesystem free space. Aggregate memory is bounded by physical RAM minus the
1 GiB reserve and effective ancestor allowance. The heavy subtree is limited to
one CPU, 448 PIDs and zero swap. Frozen per-worker limits remain in force.
Controller processes, subprocesses, tmpfs and charged page cache share that bound.

Combined logs have a 128 MiB kernel write limit: two 64 MiB participant streams,
or at most eight 16 MiB administrative streams. The installed persistent ext4/xfs
output mount must enforce a maximum of 1 GiB with noexec/nosuid/nodev. This shared
conservative bound also includes retained generation files; it makes no promise
that a workload fits. Missing filesystem enforcement is a deployment blocker.
Periodic size scans do not substitute for write enforcement.

Monitoring checks host/ancestor/operation memory and local events, swap, disk,
output bounds, identities, controller liveness and preflight baselines through
postflight. Ordinary frozen worker OOM retains frozen evaluator semantics; parent
OOM, aggregate exhaustion and monitoring loss yield infrastructure failure with
no score and no automatic retry. Protection failure durably pauses scheduling,
revokes launch authority, stops creators and verifies absent containers and empty
owned cgroups for up to 30 seconds. Unverified cleanup retains blocked ownership.

## Database and administrative transactions

The dispatcher acquires host ownership before claiming a database job. Resource
deferral leaves queued jobs without consuming an attempt. It binds existing job,
attempt, source, epoch and evaluator identities, while retaining database secrets,
heartbeat and cancellation outside the controller. Controller results are private
and authenticated. Database outage, lease loss and controller disconnection trigger
termination; none proves workers stopped.

Successful postflight retains ownership while the dispatcher records commit intent
and commits the database transaction. Only acknowledged or transactionally reconciled
commit permits release. Ambiguous acknowledgement preserves a matching committed
result; uncommitted orphan output becomes infrastructure failure after cleanup.
Computation and result insertion are never repeated. Ordinary infrastructure retries
require verified cleanup. Protection aborts stay paused. Legacy expired jobs remain
blocked unless resources can be independently reconciled; no schema migration or
attempt reset is provided.

The actual epoch entrypoint routes v4 through `deploy.protected_epoch`: host gate
first, existing zero-pending maintenance fence second. Queued participant jobs block
maintenance. Configured create/reference/audit roles use the same protected runtime.
An unused failed fence releases only after verified cleanup. Administrative commit
receipts and reconciliation preserve completed outcomes without rerunning roles.
Legacy unprotected computational streaming is retired; v2/v3 capacity-receipt
validation requirements remain unchanged.

V4 requires `unmeasured_capacity`, owner authorization of exact packet bytes and
independent review. Control-specific evidence validates scenarios, observations,
ordering and identity bindings; arbitrary hashed JSON or checkboxes do not pass.
Native acceptance remains valid only for matching installed runtime/configuration.
Preparation freshness is 24 hours and live execution freshness five minutes.
Changed evaluator/configuration evidence cannot inherit historical runtime acceptance.
Finalization produces immutable candidate configuration, pending matching acceptance
and authorized installation; it does not silently activate it.

## Configuration and review packet

Three distinct private JSON files are bound together: supervisor (`root`, `socket`,
`helper`, configured `roles`), native runtime (inspected cgroups/ancestors, daemon,
Python, images, bounded output mount, retained services and controller config), and
controller (`native_configuration`, frozen identity/epoch/image and signing key).
Exact validators live in `workload_service.py` and `native_workload.py`; the packet
binds their bytes rather than filling guessed host values. Administrative role
authority also binds operation, packet and canonical native configuration. Grants
prevent reusing a role or reopening an ambiguous operation.

Prepare an exclusive offline packet and canonical release artifact:

```sh
uv run python -m scripts.prepare_workload_packet \
  --output /tmp/workload-review-new.json \
  --release-output /tmp/workload-release-new.json
```

The default emits a v2 bootstrap review. A proposed socket record contains only
`path` and `state: proposed`; it cannot pass installed validation. Bootstrap host
records additionally bind the coordinator UID mapping and each scheduling owner's
manager, account, restart policy, trigger references and disposition. System and
other-user managers receive explicit commands; unresolved cron/other triggers
block publication until a reviewed adapter exists. Retained units stay running.

`--stage installed --bootstrap /private/bootstrap-review.json` consumes the prior
full review packet (or its `deployment` proposal) plus `--inspection` containing
observed identities. It binds all three private configurations, supervisor birth,
socket birth, dependency receipt and complete frozen release manifest. It emits
only native-test command fragments, never installation authority. Current v2
packets publish no runnable commands while implementation blockers remain. Actual installed file and
socket identities are rechecked before native tests. `--stage legacy-v1` retains
the earlier installed-only contract; historical packets remain unchanged.

The v2 bootstrap implementation remains preparation tooling: fresh release,
dependency and configuration installation, exact release/image restoration and
missing-delegation/storage prerequisite proposals still require completion using
privileged host facts. V2 exposes the old rollback subset only as fencing commands,
with an explicit incomplete-restoration blocker. Do not execute an incomplete
proposal. `--unit-output` writes reviewed unit source only; it is not an installer.
The [readiness record](acceptance/production-preparation/protected-runtime-readiness-20261021.md)
tracks these gaps and the independent review. Proposed configuration hashes and
paths must never be described as observed installation evidence.

The [immutable local review](acceptance/production-preparation/workload-integrated-review.json)
and [source release](acceptance/production-preparation/workload-integrated-release.json)
record local source bytes and explicit missing host prerequisites. They do not
certify an installed evaluator fingerprint or configuration.

## Installation, cleanup and recovery

The historical v1 generator renders unit installation, maintenance, cleanup and
configuration recovery commands. Those commands alone do not install a complete
fresh release or restore a rollback image. V2 explicitly records those gaps.
The supervisor uses notification/watchdog supervision and an independent
`ExecStopPost` cleanup process outside the heavy subtree. Restart always enters
reconciliation with scheduling paused; work never resumes automatically.

Before any host action, obtain separate owner authorization for the exact packet
and independently reviewed bytes. Verify retained services and scheduling closure,
stop the identified computational scheduling owners and preserve original settings.
Install only the bound files and start the supervisor paused. Cleanup-only execution
requires the same installed configuration and inspected births; it refuses a live
or replaced supervisor and removes only its matching stale socket. Never delete the
journal or clear a database lease to bypass ownership.

After failure, reconcile the inspected resources. Resolve any database/operator
commit ambiguity before explicit resume; a cleaned DB-bound workload cannot be
resumed around the commit barrier. Fresh resource checks are mandatory. If birth
identity, daemon identity or termination cannot be established, leave ownership
blocked and scheduling paused for investigation. Rollback must use the inspected
compatible release/configuration, preserve the current installation and one verified
rollback, and keep computation stopped until separate restoration authority.

## Local verification and native gate

Local tests cover journal corruption/replay, peer rejection/slow clients, independent
monitoring, stuck I/O, create/start/completion ambiguity, process contention,
cleanup failures, parent OOM/swap/disk/output loss, database outage/commit ambiguity,
cancellation, maintenance fencing and v4 evidence/freshness. Fake cgroups and signed
synthetic results establish failure logic, not native VPS enforcement.

Disposable local Linux fixtures exercise actual peer credentials, slow clients,
process death with surviving workers, independent cleanup and kernel file/volume
write bounds. Disposable loopback PostgreSQL exercises admission, dispatcher and
maintenance transactions across real connections. Fixtures are removed after tests.
The [local verification record](acceptance/production-preparation/workload-integrated-local-verification.md) is committed alongside this runbook; skipped native
tests are not passing acceptance evidence.

`deploy.workload_native_acceptance` prepares three bounded control cases: inert
lifecycle, fixture parent OOM and supervisor death. It requires exact owner authority,
independent review and installed host/configuration identities, verifies retained
services before/after and leaves computational scheduling paused. Pressure is
limited to disposable 64 MiB/32-PID fixture cgroups. Its receipt covers those cases
only; it cannot manufacture a complete operational-controls receipt. No native
packet has been executed. Missing authorization, current host inspection, delegated
controllers, enforced output volume, compatible rollback and matching installed
release/configuration acceptance remain explicit external gates.

## Earlier local checkpoints

The ownership/result-transaction and runnable-control-entrypoint checkpoints were
partial predecessors of this integration. Historical packets and acceptance receipts
remain unchanged; they cannot certify the new native adapter.

### Ownership and result-transaction checkpoint, 2026-10-21

See the integrated transaction and recovery contracts above.

### Runnable control entrypoints checkpoint, 2026-10-21

See the integrated installation and private configuration contracts above.
