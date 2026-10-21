# Protected-runtime follow-up — 2026-10-21

Disposition: **blocked; implementation incomplete; no installation or native
acceptance**. This checkpoint does not satisfy the full deployment plan. Budget
remains $0, benchmark 0.5.0 preview. No VPS service changes, release transfer,
mount/delegation changes, solver evaluations, capacity measurements, epochs,
public listeners, notifications or scheduling resume ran. Historical receipts
remain unchanged.

## Implemented and reviewed

- V3 offline frozen-bundle primitives verify file content/mode, generated units,
  dependency artifacts, interpreter/image/configuration bindings, reject extra
  or missing files, symlinks and shared hardlinks, and publish exclusively.
  Private configuration bytes are excluded. Tests prove checkout drift cannot
  change the frozen bundle's expected bytes. This is file verification, **not**
  proof of complete executable source or lock-resolved dependency closure.
- Installed CLI validation now uses its bound bootstrap proposal rather than
  deriving expected installed hashes from the operator's current checkout.
- V3 scheduling proposal primitives render owner-specific persistent systemd
  condition drop-ins without changing original unit files. They exclude retained
  units and require exclusive resource creation. Cron/at and cross-user private
  gate visibility have no adapter and are rejected. These are proposed resources,
  not observed births or executable installation authority.
- Native fixture authority binds case sequence, individual deadlines, total
  allowance at most 180 seconds and cleanup commands. A durable exclusive intent
  in the bound native-root journal prevents copied-authorization replay and
  requires reconciliation after interruption. Success receipt publication follows
  verified pause, resource-stop fencing, fence release and retained-service checks.
  Deadline checks are cooperative; a strict whole-process watchdog remains missing.
- Privileged collection now rejects nonzero observations instead of marking them
  complete. The additional all-account root-console collector inventories cron and
  user managers, vendor units and execution references. It explicitly leaves
  recursive classification, at contents and container-owner closure unresolved.
  The [owner-console procedure](../../PROTECTED_RUNTIME_OWNER_COLLECTION.md)
  provides exact read-only collection commands and required follow-up facts.

Independent source review by `/root/review_followup` identified disconnected v3
helpers, incomplete source/dependency closure, copied-authorization replay,
premature receipt publication and incomplete deadline coverage. Re-review confirmed
replay and receipt ordering fixes and requested the final pre-publication deadline
check, which was added. Review did not approve installation or certify full native
coverage. No independent installation review has passed.

## Fresh host facts and authorization blockers

Read-only collection reused the deployment SSH credential and existing strictly
pinned host identity. It succeeded with seven retained containers, 1,419,720 KiB
MemAvailable and `sudo -n true` exit 1. Memory is a volatile observation, not a
capacity measurement. Raw observations, stderr, collector identity and hashes are
private in `results/integration-evidence/protected-runtime-followup-20261021/`.

Missing facts: all privileged scheduling owners and recursive references,
classification/dispositions, actual delegation permissions/ancestor allowances,
a compliant existing output mount or feasible exclusive backing-file proposal,
complete compatible rollback identities and fresh admission facts. The 1 GiB
available-memory and 5 GiB backing-space floors remain requirements.

Missing authorization: independent review of a **complete** executable proposal,
then exact-byte owner installation authority; after fresh installed inspection,
separate exact native-case authority. None is requested for this incomplete packet.

## Unfinished implementation, separate from missing access

V3 deployment-review/bootstrap/installed-inspection integration, observed/proposed
resource transitions and readiness predicates are unfinished. Historical v1/v2
packets retain their existing contracts and empty v2 executable commands.

Still required: complete frozen executable source and lock-resolved offline Linux
dependencies; prerequisite planning; exclusive staged installation, dependency
installation and atomic activation; durable per-step reconciliation; preservation
and restoration of original settings and non-systemd schedulers; full guarded
release/image/configuration rollback with legacy coordinator fencing; fresh actual
installed unit/dependency/image/mapping/mount/delegation validation; owner-only
inert image socket probe; remaining native scenario runners and validators;
strict packet-wide execution bounding and failed-attempt operational receipts;
and a successful complete disposable installation/acceptance path.

These are source engineering gaps, not consequences of missing root access.
No operational-completion receipt or production-epoch/audit packet is issued.

## Verification

82 focused tests passed. `make check` passed with 1,523 tests, 45 explicit skips
and 12 warnings, followed by eight contract tests. The local Linux fixture passed
eight inert cases in a disposable container with 64 MiB memory, 32 PIDs, no network,
read-only checkout and bounded tmpfs; it does not certify native installed controls.

The first disposable PostgreSQL run used the wrong fence database name and failed
setup guards; its log remains retained. The corrected run uses separate disposable
admission and fence databases. Its final result and fixture cleanup are recorded
in the companion verification JSON. No production evaluation rows were touched.
Source/release/review packets are engineering artifacts, not execution grants.
