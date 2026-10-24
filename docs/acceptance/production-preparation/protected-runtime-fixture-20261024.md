# Disposable installation fixture checkpoint — 2026-10-24

Implementation at `f442684`, with reviewed fixes at `e61ac65` and `94c9b3e`, supplies the complete reusable fixture driver and
five targeted case runners. Independent review approved the exact component
source bytes, with scope limited to disposable fixture components. This does
not establish whole-proposal approval or production installation authority.
The [machine-readable record](protected-runtime-fixture-20261024.json) binds
private evidence hashes; the [runbook](../../WORKLOAD_INSTALLATION_FIXTURE.md)
describes the lifecycle and ownership requirements.

The full rehearsal did **not** complete. Docker connectivity was restored and
75 isolated Linux container regressions passed. The latest fresh x86_64 QEMU
guest could not finish loading the offline runtime images within the existing
35-second command bound. The observer recorded `timed_out: true`, command return
code -9, no remaining descendants and no errors. The log acknowledged only the
coordinator image before timeout. The engine refused with
`installation_subcommand_failed:b241bbc819d34e0294d2238fc4643b0d`.
The provider's failure path stopped its daemon successfully; VM shutdown then
verified reaping, an empty process group and inactivity. The attempt lasted
287.27 seconds within its 30-minute bound. No fixture installation followed.
This is a precise measured blocker for this emulated attempt, not a claim about
native image-load performance or general environment unavailability.

Two earlier failed generations are retained separately. The first package
command returned zero but left child entries after client exit; final cleanup
reported none remaining. Its root cause was unresolved, and complete rootless
prerequisites were moved to initial guest bootstrap without weakening checks.
The next generation passed that stage and exposed a worker deadline-journal
lookup defect before fixture effects. A regression now proves worker records
cannot reset the parent budget; the fix was independently reviewed before the
latest generation. No failed phase was automatically retried.

| Disposition | Result |
| --- | --- |
| Implementation | Reusable driver, built-in resources, lock-bound workers, frozen observations, offline dependencies and five case runners implemented |
| Complete rehearsal | Blocked by offline runtime image-load timeout; installation, fresh installed inspection and rollback unexecuted |
| Partial snapshots | Not run: guest provisioning dependency failed |
| Partial configurations | Not run: guest provisioning dependency failed |
| Unacknowledged images | Not run: guest provisioning dependency failed |
| Interrupted rollback | Not run: guest provisioning dependency failed |
| Mapped/incorrect peer UID | Integrated; native execution blocked before fixture provisioning |
| Privileged production host facts | Not collected; no VPS actions |
| Independent component review | Exact implementation source approved; native behavior and whole proposal unapproved |

`make check` passed 1,986 tests, skipped 60 and passed eight contracts. Separate
emulated controls passed 50 tests and failed one fixed 0.6-second containment
expectation. The retained historical 0.8-second helper failure is unchanged.
Neither emulated result establishes native performance acceptance, and no
runtime deadline or benchmark 0.5.0 semantics changed.

Private raw journals, bounded command logs, source/input manifests, guest
ownership and shutdown receipts remain retained for the unresolved failure.
Original retained guest disks and existing application containers were preserved.
Only each failed generation’s three fresh-guest image files were removed after matching stopped-receipt
hashes and identities, lifecycle locking, process/mount/open-file checks and
retaining the compact failure record outside the deleted files. Retirement is
recorded separately and restarting that generation is prohibited. No Docker
prune was performed. Cleanup of a provisioned fixture
may deliberately preserve named retained services and output under a recorded
retention exception; that receipt must not be presented as complete retirement.

The current recovery reference remains the
[protocol-3 checkpoint](protected-runtime-recovery-v3-20261023.md). General
external-effect recovery, the remaining 21 scenario runners, privileged collector
installation/host dossier, whole-proposal approval, epoch policy replacement and
public activation remain outside this milestone. No protected-runtime or VPS
installation authority is requested.
