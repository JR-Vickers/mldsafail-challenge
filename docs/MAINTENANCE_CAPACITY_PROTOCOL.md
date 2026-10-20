# Bounded capacity investigation proposal

Prepared 2026-10-20. **Preparation only; no workload is authorized.** This protocol
is part of [item 4's maintenance prerequisites](acceptance/integration/maintenance-prerequisites-v8-20261020.md).
The owner must approve the exact host, workload generation, resource delegation,
window, command manifest and one attempt before execution. No host size is certified.

The private v8 `capacity-protocol.json` binds the frozen source, controller and
worker index/platform/configuration identities, actual proposed argv, inputs,
output destinations and ceilings. Do not substitute a newly built image. The
controller owns epoch creation and its sequential reference execution; independent
audit is a separate phase using the same frozen controller, without a Docker
socket and with a read-only epoch mount. This consumes a separately approved
investigation generation, never the production epoch or an automatic retry.
Synthetic substitutes cannot support production sizing until their generator,
case count/profile, worker concurrency, image, mounts, phases and resource envelope
are demonstrably compatible. Record differences and retain `source_compatible:
false` until reviewed. A service-only rehearsal is insufficient.

Measure at 250 ms monotonic intervals, including setup, all 100 reference cases,
audit, termination and cleanup. Bind each sample to the actual host boot ID,
process start times, container IDs, cgroup inode/resolved path and phase. A missed
interval over one second, missing process/cgroup, counter reset or OOM invalidates
the measurement; preserve partial evidence. The measurement implementation and
compatibility review are prerequisites to execution, not supplied by old worker
RSS logs. Record `memory.current`, `memory.peak` where available, `memory.events`,
`memory.swap.current`, `cpu.stat`, `pids.current`, `io.stat`, filesystem free bytes,
MemAvailable, swap and all ancestor memory/swap/CPU/PID limits. Bound sampling
output to 64 MiB, operation logs to 128 MiB and the whole generation to 1 GiB.

Use three disjoint scopes. `operation_resources` includes the controller, workers,
client/monitor and operation tmpfs/page cache with no double counting of parent
and child cgroups. `retained_services_excluding_operation` includes running web,
database, proxy, Docker/systemd overhead and concurrent host-check/backup demand.
`host_available_excluding_retained_usage` is concurrent host availability after
retained usage, never physical RAM minus an unrelated historical peak. Record
simultaneous maxima and raw timestamps; do not sum independently sampled RSS peaks.
Include every ancestor constraint up to `/sys/fs/cgroup`, physical RAM and swap.
Keep swap out of available-RAM certification. Apply `deploy.production_maintenance.capacity`
only to complete, compatible, hash-bound evidence with these scopes.

Proposed operation ceilings: controller 512 MiB, 1 CPU, 256 PIDs; one worker at a
time, frozen 2 GiB worker limit. A proposed common operation ceiling is 2.5 GiB,
1 CPU and 320 PIDs, subject to measured monitor/client needs and ancestor review.
These are abort ceilings, **not measured demand or a supported host size**. Do not
run if retained usage plus those ceilings and headroom cannot fit the approved
host/ancestors. Stop on any `oom`/`oom_kill` increment, memory above 95% of an
applicable finite limit, swap growth, fewer than 256 MiB MemAvailable, filesystem
free bytes below 2 GiB, PID use above 90%, unexpected workers, service degradation,
identity drift, sampler failure or verification loss. Both the 95% threshold and
256 MiB floor are emergency abort thresholds, not sizing headroom.

Sizing must include positive headroom with a written rationale: observed retained
variability, unobserved kernel/service allocations, sampler error and timer overlap.
The provisional minimum is max(256 MiB, 20% of simultaneous operation plus retained
peak); increase it if observed variation or missed coverage requires it. Reject
unsupported rationale rather than declare a host size. Missing evidence stays
`unresolved`; only compatible measurements exceeding capacity justify
`resize_decision_required`.

Keep existing host-check and backup timer settings. The host-check runs every five
minutes. The backup is daily 03:15 UTC plus up to five minutes randomization and
persistent catch-up, with a 120-second pg_dump ceiling. Either capture overlap in
the retained-services scope, or demonstrate from fresh next/last-trigger and
persistent state that the **entire** window excludes it. Do not manually trigger a
backup or change its schedule under this protocol. No maintenance window is selected.

The proposed fence lifetime is 8,000 seconds: stop 120, create/reference 5,400,
audit 600, inspection 20, cleanup 300, restoration 300, margin 1,200, plus two seconds
acquisition (7,942 seconds). A later approved sampler must cover that whole window.
The maximum allowed fence lifetime remains 9,000 seconds. Any additional phase
requires a revised budget before acquisition. Preparation freshness is 24 hours;
execution inspections are at most five minutes old.

Every command runs under an exclusive generation and an operation label. Persist
intent before launch. On failure stop the controller first, then all positively
owned workers, inspect each exact container/cgroup and client, and prove quiescence
before postflight. Preserve scientific inputs/results and the failure record; no
retry or scheduling restoration follows ambiguous launch/cleanup. Remove only
owned disposable resources after positive termination and retained-record checks
under [retention policy](RETENTION_POLICY.md). Do not prune a shared daemon.

Exact production stop, transfer, provisioning and restoration commands remain
withheld until scheduling, capacity, delegation and reviewed transport prerequisites
close. Proposed investigation argv in the private packet is review material and
must not be pasted as an execution authorization.

## V10 preparation amendment, 2026-10-20

For the [v10 follow-up](acceptance/integration/maintenance-prerequisites-v10-20261020.md)
only, the proposed common operation envelope supersedes the provisional 2.5 GiB/
1 CPU/320 PID proposal above: **3 GiB, 1.25 CPUs, 448 PIDs, zero swap**. The frozen
512 MiB controller and 2 GiB worker bounds remain unchanged. Planning reserves
128 MiB for two SQL helpers, 128 MiB for monitoring and 64 MiB for clients, plus
192 MiB remaining inside the common bound. These are unmeasured reserves; common
ancestor admission and actual sampling must verify adequacy. Retained services
and positive host sizing headroom are additional. This still rejects a 2 GiB host
and certifies no replacement host size.

The monitor and clients use a generation-owned control leaf beneath the common
parent. Gzip evidence retains raw JSON samples under the existing 64 MiB stored
limit, with bounded decompression during validation. Coverage and raw evidence
bind an exclusive operation attempt. Separate operation/epoch filesystems must
both meet the free-space floor. Isolated measurements cannot borrow production
availability, retained-service or ancestor evidence. Same-host replay/assessment
tooling does not itself supply a cross-host compatibility disposition. No change
to a frozen evaluator, scoring rule or execution authorization follows from this
amendment; older private proposals remain historical and unchanged.
