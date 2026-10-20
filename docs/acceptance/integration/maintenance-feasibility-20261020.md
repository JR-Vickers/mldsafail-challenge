# Maintenance feasibility — blocked disposition v6

The 0.5.0 public preview remains blocked at launch item 4. Owner-only evidence is
in `$HOME/.config/mldsafail-production/maintenance-20261020-v6`. This is a
`maintenance_proposal`; `scheduling_exclusion_verified` remains false. No
maintenance-and-transfer approval is requested. 0.6.0 stays ignored, C diagnostics
abandoned and new backup provisioning deferred.

## Host feasibility

Bounded read-only SSH inspection used the recorded application account/key and
strict pinned ED25519 host identity. Physical RAM was 2,063,564,800 bytes,
available RAM 1,432,031,232 bytes, and swap approximately 2 GiB. Available RAM is a
snapshot, not a compatible workload measurement. Retained controller 451.5 MiB and
monitor 32.4 MiB peaks remain separate historical scopes. No compatible simultaneous
frozen worker/controller peak, retained-service peak or justified positive headroom
was found in the retained proposal evidence. The existing capacity validator
therefore returns `unresolved`. Configured worker 2 GiB and controller 512 MiB
limits and swap do not establish demand or justify a resize recommendation.

Docker reports systemd/cgroup v2. Its service is under
`/user.slice/user-1000.slice/user@1000.service/app.slice/docker.service`, with
`Delegate=yes`. The user manager, app slice and Docker cgroup are UID 1000 owned;
root, user.slice and user-1000.slice are root owned. Every inspected ancestor has
cpu/memory/pids controllers; the Docker service's subtree control is empty.
Memory maxima are `max` on the existing non-root ancestors. The cgroup root has
no memory.max interface; physical RAM still bounds capacity. Full per-ancestor
cpu, memory, swap and pids observations are retained privately.

For the literal Docker parent `production-epoch.slice`, systemd slice hierarchy
implies `/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/production.slice/production-epoch.slice`.
This path is absent. It is a proposed path, not verified delegation: neither the
missing production.slice nor the leaf's ownership/control files can be certified.
`systemd-escape --suffix=slice production-epoch` instead escapes the hyphen and
names a different unit; do not substitute that identifier. No slice was created.
No capacity probe, evaluation or resize ran.

## Scheduling and deployed state

The original [353-path collection and 310 hash comparisons](scheduling-collection-review-20261020.md)
remain immutable. v6 binds those files and records path-level topology, captured
execution directives and reference candidates separately. These are review work
records, not a complete v2 receipt. External script/configuration closure and
runtime states for all installed units remain unresolved; unknown targets cannot
be classified as unrelated. Installed fragments, wants links and masks are not
proof of loaded/active/triggerable state. Historical rehearsal daemon/monitor
units remain potential restart owners until their sources and state are reviewed.

Host-check remains enabled/active (five-minute timer); its last service run used
24,908,000 CPU nanoseconds, with no memory peak available. This is a single
inspection-only invocation, not a resource bound. Database-backup remains
enabled/active, with next observed trigger 2026-10-21 03:16:38 UTC; the service was
inactive and exposed neither memory peak nor CPU accounting. Its script can run
a bounded 120-second pg_dump, consuming database reads, CPU, RAM and disk. No
maintenance window has been selected, so overlap cannot be excluded. Preserve
both timer settings; deferred provisioning does not authorize disabling backups.

Exact coordinator identity and restart policy were reobserved: the previously
recorded container is restarting, exit code 1, under `unless-stopped`. Docker
itself has `Restart=always`. Web/database/proxy remain running. Host checkout
coordinator, queue and admission source hashes differ from current reviewed
source; the inspected old queue/admission files lack the shared advisory mutex.
Runtime image-source inspection and its limitations are retained separately.
A checkout symlink is not proof of running image contents.

A read-only database connection (default_transaction_read_only and five-second
statement timeout) ran only SELECT statements. It observed 12 complete jobs and
one failed job, no pending states, and historical lease fields on terminal rows.
Those fields do not mean a live lease. The lock snapshot showed only the SELECT's
AccessShareLock. This is an observation, not exclusion, draining or permission to
stop a coordinator. No application rows or scheduling settings were changed.

The reviewed diagnostic guard uses advisory transaction lock 1296843841 plus a
SHARE table lock, a two-second contention timeout and a bounded sleep/statement
timeout. Its maximum holder window is 3,000 seconds, whereas the retained create
ceiling alone is 5,400 seconds. SHARE conflicts with queue writes, including
recovery, but cannot replace demonstrated deployed compatibility and a complete
lifecycle through coordinator stop. Disconnect/expiry rolls protection back;
owned cancellation and positive absence verification are required for release.
It rejects pending work; it does not drain it. No compatible maintenance control
has been established. See the [separate control proposal](maintenance-control-proposal-20261020.md).

## Required decisions and remaining read-only work

| Dependency | Evidence or decision needed |
| --- | --- |
| Capacity | Identify compatible retained simultaneous measurements and retained-service/headroom evidence. If unavailable, owner must separately choose a resize investigation/decision; no size is certified here. A resize alone does not manufacture compatible measurements. |
| Scheduling | Finish recursive external-script/configuration review and all runtime-state classifications, then collect exact committed collector bytes through the owner console and bind a separate v2 receipt. Preserve the extra-newline historical source identity. |
| Fence | Owner selects an existing demonstrably compatible mechanism or authorizes the separate control engineering proposal. No implementation/acquisition is authorized here. |
| Delegation | Inspect any existing compatible delegation, or separately approve provisioning after capacity and scheduling close. Missing proposed ancestors remain unverified. |
| Transfer | Freeze complete dependency closure and exact restoration commands only after the above; obtain maintenance/transfer approval, then verify hashes, UID 1000, directories 0700 and private files 0600 at the proposed destinations. |

No further owner-console collection is requested while the external-path list is
incomplete. No placeholder collector command or unsupported maintenance/provisioning
command is certified. The private bundle records exact proposed destinations and
committed operator identity, plus a dependency manifest marking unavailable closure
explicitly; it is not transferable or execution ready. No evaluator destination or
attempt marker was created.

Keep web/database/proxy running. Failure restoration requires positive termination
of operation resources and fresh postflight. Ambiguous launch states require
manual reconciliation. Preparation freshness remains 24 hours and execution
freshness five minutes; refresh later under execution authority, not repeatedly
during proposal review. After separately approved maintenance/transfer, final
packet review and distinct `production_epoch_only` authority are still required.

## Validation and independent review

Independent review accepted committed operator `bc57f34` and the private v6
proposal as a blocked disposition, with no corrections required. Private review
and validation artifacts are bound in its final file manifest. Local verification
checked 11 raw sections, all 353 path evidence identities, 310 file-content hashes,
62 documentation links, retained-file hashes, exact collector source binding,
private ownership/modes, unresolved capacity and proposal execution rejection.
Focused scheduling/maintenance/operation/inspection/guard tests passed.

`make check` passed 1,282 tests (15 skipped, 12 existing warnings) and 8 frozen
contract tests. The initial run used umask 077 and failed an existing test whose
0755 fixture was consequently created as 0700; both the failure and successful
standard-umask rerun are retained. No code change was needed. `git diff --check`
passed. No push, provisioning, lock acquisition, service change, operation-bundle
transfer, evaluation, epoch creation or publication occurred.
