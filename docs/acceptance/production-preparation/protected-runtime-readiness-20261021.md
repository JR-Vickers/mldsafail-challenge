# Protected runtime readiness — 2026-10-21

Disposition: **blocked preparation; no installation or native acceptance**.
Local runtime integration is source-verified. The existing VPS, $0 budget and
0.5.0 preview are retained. This checkpoint does not complete the requested
installation/acceptance phase. No solver evaluation, capacity measurement, epoch,
listener, service change, release transfer, launch or notification ran.

## Host collection

Read-only Python collection ran as deployment UID 1000 over the recorded SSH
identity, with strict ED25519 pin
`SHA256:OtjIfXCrqewb9FTJ8jpU7Rq7aZL4P8P7U0dKZ8DoB5w`.
Raw observations and per-run collector/raw/stderr hashes are private under
`results/integration-evidence/protected-runtime-20261021/`.
The first observation reported 1,412,772 KiB MemAvailable, above the protected
1 GiB admission floor; it is a volatile observation, not a capacity result.
Rootless dockerd's actual UID map maps container UID 0 to host UID 1000;
container UID 10001 would map to host UID 110000 and fail the owner-only socket.
The proposed production Compose coordinator explicitly uses UID 0 in that namespace
and mounts no Docker socket. This checks the configuration's mapping, not a running
protected coordinator's peer authentication.

Seven retained containers were inventoried. The refreshed collection additionally
records filtered container births, image/restart/user/cgroup/mount information,
without environment contents. Current managers, service/timer/socket/path identities,
trigger references, daemon process births/maps, cgroup ancestors, mounts, disk and
memory are recorded. Collection is not classification or scheduling closure.
No bounded persistent output mount has been established for this runtime.
Passwordless `sudo -n true` returned 1; privileged scheduling visibility is missing.
No service was stopped and no cgroup, mount or remote file was created.

## Tooling and independent source review

Bootstrap and installed inspection schemas are now separate v2 contracts. Proposed
socket paths cannot pass installed identity validation. V1 remains unchanged.
Bootstrap validates owner/account/manager-specific scheduling commands, original
settings, restart and trigger dispositions and actual rootless UID mapping.
Unresolved/non-systemd triggers block command generation. Retained scheduling
units are excluded from computational stops. Installed validation binds the prior
proposal, three distinct configurations, paused state, supervisor birth, dependency
receipt, socket birth and matching release/configuration declarations. Native
entrypoints recheck socket, configuration/source bytes and supervisor process birth.
The CLI binds the complete frozen source manifest rather than any nonempty file list.

Independent review by `/root/review_preparation` found six blockers. The full-packet
CLI input mismatch was fixed. Manager-aware rollback fencing and complete source
manifest checks were added. Incomplete rollback commands are explicitly only
fencing fragments. Fresh installation and prerequisite commands, complete native
coverage and remaining installed observation checks are **not complete**. Both v2
stages therefore publish `commands: {}` with explicitly named fragments/blockers;
the native v2 entrypoint rejects them. No source review approved installation.
An exact reviewable blocked source packet can be prepared, but it must not be
presented as an executable installation proposal.

The control evidence matrix lists every v4 scenario, required evidence origin,
raw observations, identity bindings and validator. It identifies the three existing
native runners and missing coverage separately; no unrun case gets a receipt.
Synthetic/local Linux or PostgreSQL evidence never becomes native VPS evidence.
Historical v4 validation and v2/v3 capacity requirements remain in force.

## Required owner-assisted facts and remaining implementation

The next host step requires the existing root console or equivalent privileged
read-only collection. The revised `deploy/privileged_scheduling.py` records system
and deployment-user manager identities including Restart/Triggers/TriggeredBy;
its separate private raw file and reviewed script references must be retained.
Collect all other user managers, cron/at sources and recursively referenced scripts,
then classify every computational owner and trigger. Unresolved references block
maintenance admission. Do not stop services or clear stale jobs to collect facts.

Privileged facts must also identify a preservable delegation parent, permissions,
ancestor limits and a feasible persistent ext4/xfs output volume of at most 1 GiB,
with noexec/nosuid/nodev and at least 5 GiB free backing space. Do not assume that
these can be provisioned without root or modify the current installation to try.
Bind proposed paths, existing/missing state and reversals before generating any
prerequisite commands. If preservation/$0 feasibility fails, stop at that blocker.

Remaining source work is exact immutable release/dependency/configuration staging
and installation with preservation checks; prerequisite/restoration scripts;
verified schema-compatible rollback release/image restoration with computation
fenced; fresh installed unit/dependency/coordinator-map/scheduling observations;
and runners/raw receipts for the remaining host-dependent controls. Only after
that work and independent review should installation authorization be requested.
No approval is requested for the present incomplete packet.

After exact-byte installation authorization, refresh volatile identities, perform
approved installation and start paused. Produce a newly observed installed packet
and obtain separate exact native-test authority. Acceptance must retain services,
resolve transaction state, verify absent fixture containers and empty owned scopes,
and leave computation paused. A correction changes release/configuration bindings
and needs renewed review and affected acceptance. Production epoch/audit packets
remain a subsequent separately authorized phase.

## Verification

The focused deployment/scheduling/runtime/policy/dispatcher/service suite passed
105 tests. Disposable loopback PostgreSQL passed 46 admission/dispatcher/fence/pipe
tests. The local Linux fixture passed eight inert control cases. Its first run
omitted Docker `--init`, leaving an orphan zombie and timing out at cleanup; the
corrected invocation passed. The first PostgreSQL startup check observed the
initialization server; waiting on TCP readiness corrected it. Failed logs remain
private, and all disposable containers were removed and their absence checked.
These fixture setup failures are not production failures or native acceptance.
The full check, changed-link and immutable packet hashes are recorded in the
companion verification record after publication.
