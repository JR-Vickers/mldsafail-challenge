# Next development phase: make protected-runtime deployment executable

Status: in progress; no installation or native-test authority granted.

Latest [substep recovery checkpoint](acceptance/production-preparation/protected-runtime-substeps-20261023.md)
versions new recovery journals, binds snapshot and artifact substeps, and permits
identity-checked snapshot continuation after separate reconciliation and fresh
execution authority. External mutations retain conservative recovery. This is
component engineering, not completion of the installation proposal or acceptance.

Latest [host-reader checkpoint](acceptance/production-preparation/protected-runtime-reader-successor-20261023.md) corrects symlink/absence races and prepares a separately versioned fixed-reader successor. Existing privileged scan and private prerequisite dossier remain incomplete; full installation/rollback and acceptance implementation are still outstanding.

Latest [conservative recovery checkpoint](acceptance/production-preparation/protected-runtime-recovery-20261022.md) adds identity-bound whole-step acknowledgement recovery and three narrow proven-absence transitions. Partial substep continuation, the complete fixture and acceptance coverage remain unfinished.

Preceding [mutation and termination checkpoint](acceptance/production-preparation/protected-runtime-mutation-evidence-20261022.md) adds durable prerequisite substeps, failed-command receipts, incremental descendant identities and independent final cgroup checks. Complete installation recovery and scenario coverage remain unfinished; scoped review is not full-proposal approval.

Preceding [installation proposal checkpoint](acceptance/production-preparation/protected-runtime-proposal-checkpoint-20261022.md) separates implementation, rehearsal, privileged facts and review. Runtime integration does not complete deployment acceptance. The unchanged 0.8-second helper deadline blocks complete runtime rehearsal on the available emulator; remaining independent implementation is explicitly listed.

The [artifact-hardening checkpoint](acceptance/production-preparation/protected-runtime-artifact-hardening-20261021.md) records positive scheduling permission, wheel integrity checks and a tracked
full-runtime inclusion policy. The end-to-end implementation remains incomplete.

The deliverable is a complete, independently reviewed installation proposal,
backed by a successful disposable installation, interruption-recovery, rollback
and control-acceptance rehearsal. Today the runtime has extensive local tests,
and its v3 release and scheduling helpers are now connected to preparation. The
concrete engine, full acceptance coverage and complete proposal review remain
unpassed. Finish that engineering before requesting VPS changes.

The starting evidence is the
[blocked follow-up checkpoint](acceptance/production-preparation/protected-runtime-followup-20261021.md).
Historical receipts remain immutable. Preserve the existing VPS, $0 budget,
0.5.0 preview, current installation, one verified compatible rollback and retained
scientific evidence. No production epoch, solver evaluation, capacity measurement,
public listener, notification, publication, 0.6.0 work or backup setup belongs here.

Current progress is recorded in the [paused handoff and delegation checkpoint](acceptance/production-preparation/protected-runtime-handoff-20261022.md). Handoff is implemented with synthetic coverage; real handoff and full-engine/rollback rehearsal remain unfinished, separately from privileged host facts.
The complete synthetic preparation path and fresh offline Linux runtime-package
installation pass. Real delegated cgroup/output/reboot and disposable PostgreSQL
fixtures pass within their recorded scope. Full concrete installation/rollback,
complete native control runners and complete independent review remain unfinished;
privileged VPS facts are a separate outstanding requirement.

## 1. Establish the v3 contract and one complete fixture

Extend `deploy/workload_preparation.py` and
`scripts/prepare_workload_packet.py` with explicit v3 deployment-review,
bootstrap-proposal and installed-inspection contracts. Retain CLI stage names and
historical v1/v2 validation without granting old packets new authority.

Represent each resource as either observed, with its collected identity, or
proposed, with creation and preservation preconditions. Missing sockets, heavy
slices and output mounts must not require invented device/inode or process births.
Define permitted installation transitions and freshness rules explicitly.

Separate three outputs: missing preparation facts, proposed exact commands and
execution requirements. Once preparation is complete, emit the commands while
continuing to require independent review and exact-byte owner authorization.
Reject incomplete proposals with specific reasons rather than a permanent empty
command list. Do not remove blockers merely because a reviewer field is present.

Build a disposable fixture that supplies complete synthetic host facts and can
exercise the entire workflow. Use it throughout subsequent milestones.

Completion: regression tests show incomplete facts fail, proposed identities
cannot certify installation, and a complete fixture reaches a nonempty reviewed
installation proposal without execution authority.

## 2. Complete source and dependency closure

Extend `deploy/workload_release.py` from file verification to complete release
construction. Derive required executable content from the entrypoints and package
layout; include deployment scripts, migrations, generated units, Compose/image
selection and interpreter requirements. Reject missing runtime imports or files.

Resolve Linux-compatible offline dependencies against the unchanged lockfile.
Verify wheel metadata, architecture/interpreter compatibility, hashes and complete
transitive closure; filename-shaped files are insufficient. Bind the exact
installer and build artifacts if any build step is needed. Installation must not
fetch dependencies or update locks. Fail if bound artifacts are unavailable.

Bind coordinator image, frozen worker environment, evaluator fingerprint and all
three distinct private configuration hashes. Keep private configuration bytes in
separate owner-private artifacts, outside public bundles and manifests. Expected
installed hashes must always come from the approved frozen manifest.

Completion: an isolated Linux environment with network disabled installs and
imports every runtime entrypoint from the bundle. Missing dependencies, changed
locks, incompatible wheels, source/unit/configuration changes and extra files are
rejected. Advancing the operator checkout leaves the frozen release unchanged.

## 3. Close host prerequisites alongside local development

Use the existing pinned SSH identity for bounded read-only refreshes. Follow the
[owner-console collection procedure](PROTECTED_RUNTIME_OWNER_COLLECTION.md) for
privileged facts. Continue milestones 1, 2 and 4–6 while awaiting those facts.

Complete all account/manager scheduling owners, cron/at contents, container
restart policies and recursive script references. Preserve private raw evidence,
collector hashes, original settings and classification decisions. Permission
errors, truncation, unresolved references or unclassified owners block readiness.

Determine delegation feasibility from the actual user-manager hierarchy,
controller allowances and control-file permissions. Propose only necessary scoped
changes; do not reconfigure the shared Docker daemon or retained-service ancestors.

Prefer an existing compliant persistent output filesystem. Otherwise bind an
exclusive file-backed ext4 proposal of at most 1 GiB, verified free backing space,
exact paths, ownership, noexec/nosuid/nodev, preservation checks and reversal steps.
Do not resize or repurpose existing volumes. Preserve the 1 GiB MemAvailable and
5 GiB backing-space admission floors. If infeasible, report that prerequisite
blocker without attempting provisioning.

Completion: every prerequisite is either supported by evidence and an exact
proposal or identified as a concrete blocker. No host fact is inferred from the
disposable fixture, and no mutation occurs during collection.

## 4. Implement installation, persistent inhibition and rollback

Integrate `deploy/workload_schedule_v3.py` into preparation. Preserve original
unit/drop-in files, enable/mask states, cron contents and container policies.
Install owner-specific inhibition that survives reboot and prevents an older
coordinator from bypassing the host gate. Implement adapters only for scheduling
owners present in the reviewed inventory; reject unsupported dispositions.

Install into an exclusively created versioned staging directory. Verify every
artifact before dependency installation and again before atomic activation.
Preserve the current installation and verified rollback. Refuse partial, replaced,
symlinked or unexpected destinations; never overwrite an unknown resource.
Start the supervisor paused and keep computational services stopped.

Give each step a durable intent and outcome receipt bound to the proposal and
observed identities. On interruption, inspect the actual outcome before allowing
continuation. An ambiguous acknowledgement must not trigger blind replay, cleanup
of unknown resources or automatic computation restart.

Rollback must restore the bound executable release, dependencies, image selection
and configuration while retaining scheduling inhibition. Verify schema
compatibility; never roll back the database schema or discard ownership journals.
Preserve any operationally required bounded-output mount during reversal.

Completion: the disposable fixture passes fresh installation, reboot inhibition,
interruption before/after every mutating step, ambiguous acknowledgements,
partial-destination rejection and complete rollback. Retained services remain
unchanged and computation stays stopped throughout.

## 5. Verify the installed release against permitted transitions

Extend installed inspection to measure actual unit bytes, installed dependencies,
configurations/images, supervisor/socket births, daemon identity, cgroup ancestry,
delegation, mount identity/enforcement and scheduling inhibition. Compare these
with the frozen proposal's permitted transitions, not unchanged bootstrap state.

Run an inert owner-only socket probe using the bound coordinator image and actual
rootless UID mapping. Supply neither a Docker socket nor production database
credentials; verify peer authentication and rejection of the wrong mapped UID.

Completion: tests reject unit/dependency/configuration/image tampering, UID-map
mismatch, replaced births, missing controllers, changed limits and mount drift.
An unchanged complete fixture passes installed inspection without consulting the
current checkout for expected bytes.

## 6. Complete bounded control acceptance and evidence

For every scenario in `deploy/workload_controls.py`, specify a runner, exact
injection, raw observation format, identity bindings, cleanup and validator.
Maintain separate origins for synthetic, disposable PostgreSQL, local Linux and
installed-native evidence. A scenario declaration is not a passing receipt.

Extend native runners for process/container placement, aggregate limits, kernel
output enforcement, independent monitoring, abnormal-exit cleanup, restart pause
and scheduling exclusion. Test drift/controller/limit failures with disposable
resources or fixture-specific bindings; never disturb retained-service ancestors
or kill the shared daemon. Keep OOM pressure within 64 MiB and 32 PIDs. Transaction
cases use synthetic results and disposable databases, never production row edits.

Implement independent packet-wide deadline supervision, including startup,
transport, final inspection and cleanup. Reserve cleanup time within each packet's
at-most-180-second allowance. Split coverage into separately bound packets; bind
case order, individual deadlines, total allowance and cleanup commands. No retries.
On timeout or failure, stop subsequent cases, preserve failure evidence and keep
ownership blocked if termination is uncertain. Publish success only after cleanup,
transaction resolution, retained-service checks and verified paused state.

Completion: a successful full disposable path covers every required control;
negative tests verify replay rejection, timeout/failure receipts, process/container
absence, empty owned cgroups and conservative unresolved-ownership handling.
Native coverage remains unaccepted until the matching VPS observations exist.

## 7. Review and hand off the exact installation proposal

Run focused regressions, disposable Linux/PostgreSQL rehearsals, `make check`,
changed-link checks and `git diff --check`. Retain failed-attempt dispositions and
verify fixture cleanup under the retention policy. Commit validated checkpoints
locally without pushing.

Freeze source, release, units, configurations, prerequisite/scheduling commands,
installation/rollback commands, progress-reconciliation protocol and acceptance
coverage. Obtain independent review of that exact set; correct findings and renew
bindings before requesting authority. Publish immutable redacted source/review
records and retain host-bound packets privately. Update current PLAN/checklist
sections without rewriting historical receipts.

Development is complete when the full disposable workflow passes and independent
review finds the installation proposal complete. If privileged facts remain
unavailable, finish the implementation and hand off the exact missing facts;
identify implementation gaps separately rather than attributing them to access.

## Execution gates after this development phase

1. Request owner authorization for exact installation bytes only after review.
   Refresh volatile facts, verify maintenance admission and apply only authorized
   commands. Start paused and retain original-state receipts.
2. Collect fresh installed observations and obtain separate exact native-packet
   authority. Demonstrate web/database/proxy preservation, fixture removal,
   resolved transaction state and computation paused. Runtime corrections require
   new release bindings, review and affected acceptance.
3. Issue operational completion only for matching installed evidence. Then prepare
   the separately authorized production-epoch and independent-audit phase,
   including disposition of its outstanding execution-policy gate. Public launch
   remains conditional on those later gates and the final participant journey.
