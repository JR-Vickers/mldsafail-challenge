# Item 4 maintenance prerequisites — v8

Local engineering is authorized by the owner's implementation request. v7 remains
unchanged. The next private proposal is
`$HOME/.config/mldsafail-production/maintenance-20261020-v8`; it remains
`maintenance_proposal`, `scheduling_exclusion_verified: false`, nontransferable and
nonexecutable. Item 4 remains blocked pending separately authorized investigation,
maintenance/transfer and finally `production_epoch_only` execution and audit/sealing.
0.5.0 remains the preview, 0.6.0 ignored, C diagnostics abandoned and backup
provisioning deferred.

[The capacity protocol](../../MAINTENANCE_CAPACITY_PROTOCOL.md) binds scope,
ceilings, frozen images, coverage, sampling, headroom, timer overlap and abort rules.
It supplies no measurements. Capacity remains `unresolved`, not a resize decision.
No workload, new epoch, cgroup, transfer or VPS service change ran.

`deploy/maintenance_fence.py` is a separate local control. The diagnostic guard's
bytes and historical behavior are preserved. Preparation is offline and exclusive.
Acquisition persists intent and PID/birth authority, obtains the advisory
transaction lock and SHARE table lock with two-second contention timeout, then
rejects queued, claimed or running work without mutation or draining. The server
enforces a finite statement lifetime capped at 9,000 seconds. Budgets include
stop, create/reference, audit, inspection, cleanup, restoration and margin.

An independent connection checks database/container identity, backend birth and
both locks throughout ownership and before each phase. The watchdog runs every
100 ms with 100 ms per-query timeouts and rejects checks taking 800 ms. Transport
identity lookup and connection must themselves have bounded I/O; the local test
transport is not a certified VPS adapter. Lock loss/expiry/disconnect/phase failure
latches failure, terminates owned phase resources and rejects subsequent phases.
Release terminates only the exact owned backend and verifies backend/lock absence
and holder/verifier thread termination. Cleanup-only reconciliation never acquires,
resumes or restores scheduling, and does not claim an external client's termination.
Ambiguous acquisition/launch/cleanup remains a manual reconciliation requirement.

Epoch execute, audit and finalize now require a live `bind_operation` scope bound
to operation, tag, database and container identity, then enter the corresponding
monitored phase. The CLI has no production transport and refuses those mutations
without the live scope. A reviewed maintenance supervisor covering coordinator stop,
all restart owners, operation cleanup and restoration is still a prerequisite;
this patch does not certify that supervisor or make the proposal execution ready.

Real disposable loopback PostgreSQL tests exercise SHARE conflict with writes and
compatibility of actual current and retained deployed admission, claims, recovery
and heartbeats. The retained fixtures bind captured deployed source hashes. Pending
rejection, contention, server expiry, disconnect, identity drift, lost acknowledgement,
backend birth mismatch, stop failure, release and interrupted continuation are
covered locally. Existing operation tests cover partial launch, owned termination,
failed cleanup and durable failure evidence. Production restart-owner exclusion
and restoration cannot be certified by those local tests.

A read-only application-account follow-up queried valid getty instances, preserving
installed, loaded, active, alias, restart and activation dependencies separately.
It captured existing app/session slice control-file ownership/writability and every
ancestor's limits without creating cgroups. `app.slice` has writable controls and
cpu/memory/pids enabled; `session.slice` lacks enabled CPU; the proposed production
parent and leaf remain absent. The shared app slice is a structural candidate,
not an approved bounded operation delegation. Scheduling semantic dependencies,
owner-only evidence, runtime dependencies and source-to-destination transfer closure
remain explicit blockers. No complete reviewed collector allowlist or new owner
console collection is represented as ready.

The private packet binds retained v7 evidence, new inspection, proposed argv,
review limitations and validation artifacts. It preserves 24-hour preparation and
five-minute execution freshness. Keep web/database/proxy running, existing timers
and original settings intact. No window or runnable maintenance sequence is approved.
