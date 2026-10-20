# Maintenance inspection v2 — blocked proposal

Scope remains the 0.5.0 preview. Ignore 0.6.0; C diagnostics are abandoned and
backups deferred. Historical packets, receipts and approvals remain unchanged.

New proposals use `mldsafail.production-operation.v3`. Execution requires a
`mldsafail.privileged-scheduling.v2` reviewed receipt; a v1 receipt cannot satisfy
that gate. Proposals retain `scheduling_exclusion_verified: false` and cannot
execute. Preparation freshness is 24 hours; execution freshness is five minutes
from collection start, including the time spent reviewing evidence.

## Owner-console handoff

The [collector](../../../deploy/privileged_scheduling.py) is a standalone reviewed
Python file. Do not paste it through stdin: its source identity is computed from
its actual file. In the existing owner root console, after reviewing that file
and verifying its SHA256 against the committed operator checkout, use:

```sh
umask 077
python3 /OWNER_REVIEWED_PATH/privileged_scheduling.py \
  --raw-output /OWNER_PRIVATE_UNUSED_PATH/scheduling.raw \
  > /OWNER_PRIVATE_UNUSED_PATH/scheduling.collection.json
```

These are explicit owner-selected placeholders, not certified host paths. The
parent directory must be owner controlled and 0700. Raw output is exclusively
created 0600. Never put raw content in terminal output or public records.
The structured collection contains identities and hashes, not command contents.
Commands are limited to ten seconds and 256 KiB per stream, inventory to 2,048
entries per root, regular files to 1 MiB, links to 16 hops, collection to three
minutes. Limits, permission failures, link loops, dangling targets and identity
changes block review. `/dev/null` masks and resolved aliases/wants links retain
literal targets, chain identities and final identity. Linux SIGALRM bounds the
complete collection, including filesystem reads.

Review initial raw unit/cron evidence privately. Identify every referenced script
and fragment outside inventory roots, review an explicit absolute path list and
repeat collection with `--reviewed-path /exact/path` per target. Missing target
coverage blocks the receipt. Collector evidence stays immutable; classifications
live in a separate receipt, each with path, exact canonical JSON evidence SHA256,
disposition, rationale, references, and `references_reviewed`. Scheduling entries
also distinguish installed, loaded, active, masked and triggerable states. Review
must discover references from raw evidence; software cannot prove that a reviewer
identified every script reference. A completeness boolean is not a substitute.
Bind collection bytes, raw bytes and collector source hash. Keep all private files
0600 in 0700 directories. `at` retains installed-and-inspected, verified-absent,
or failed disposition; absence of atq alone never proves absence. Queued jobs
block exclusion. No privileged receipt was collected in this local phase.

## Fence and drain assessment

The inspected source guard takes advisory transaction lock 1296843841 and a SHARE
lock on evaluation_jobs, rejects queued/claimed/running rows, and sleeps with a
server statement timeout. Admission and claims share the advisory lock; the table
lock also fences writes from recovery, whose source does not take that mutex.
Acquisition has a two-second contention timeout. Disconnect or statement expiry
rolls back the fence. The runner monitors exact backend identity and releases via
owned cancellation and positive absence checks. Connection loss immediately loses
protection, so a future operation needs continuous verification and an abort path.
This is a temporary zero-pending admission fence, not a mechanism for draining
existing work. No lock was acquired and no diagnostic generation was started.

Local source agreement does not prove deployed source compatibility. The exact
coordinator identity, all restart owners/settings, deployed source hashes, fresh
queue/lease state and verified fence lifetime through exact coordinator stop are
still missing. No runnable maintenance commands are generated. A separate change
proposal must provide a bounded maintenance-specific fence lifecycle and explicit
abort/restoration protocol, or the owner must identify an existing compatible
mechanism. Do not implement that control as part of this milestone.

## Capacity, delegation and next decisions

Retained v4 evidence has historical controller peak 451.5 MiB and monitor peak
32.4 MiB, in separate scopes. It does not establish simultaneous frozen operation
and retained-service demand. Configured 2 GiB worker and 512 MiB controller limits
are not measured demand. Physical/available RAM, swap, compatible simultaneous
peaks, positive headroom and all ancestor cgroup limits remain unresolved. v3
requires explicit nonoverlapping measurement scopes. Current host recommendation
and resize remain blocked; choose compatible retained measurements or a separately
approved resize decision. No probe, evaluation or resize ran.

The actual user-manager cgroup hierarchy, proposed Docker slice sysfs path,
ownership, controllers and ancestor limits are unavailable. Do not derive a path
from the historical `production-epoch.slice` string alone or create a slice to
inspect it. Read-only host inspection using the recorded account and pinned SSH
identity is a dependent evidence handoff; no remote session ran in this phase.

The new private v5 proposal retains this blocked disposition, exact proposed
bundle/operator destinations, committed identities and a file manifest. Transfer
requires per-file matching SHA256, UID 1000 ownership, directories 0700 and files
0600 after transfer. No transfer, evaluator destination, attempt marker or service
change occurred. Keep web/database/proxy running. Restoration requires positive
operation-resource termination and fresh postflight; ambiguous launch states need
manual reconciliation. No maintenance-and-transfer approval is requested until
these dependencies close. Final packet review and `production_epoch_only`
authorization remain separate later gates.
