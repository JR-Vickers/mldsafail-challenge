# V3 preparation, offline packaging and local Linux checkpoint — 2026-10-21

Implementation remains unfinished; no installation proposal or native acceptance
is approved. This record supersedes earlier progress descriptions without changing
historical receipts. Budget remains $0 and benchmark remains 0.5.0 preview.

The v3 preparation and installed-inspection contracts are connected to the existing
CLI stages. A complete synthetic fixture produces exact installation and rollback
commands while retaining separate review and owner-authorization requirements.
Proposed resources contain no invented births. Installed transitions are checked
against the approved frozen source, including the complete systemd cgroup ancestry.

The execution engine has an exact-byte review/owner gate, single-use claims,
exclusive final-path staging, bounded journalled subprocesses, durable mutation
intents and outcomes, explicit reconciliation, atomic activation exchange and
rollback primitives. Tests interrupt every step at intent, application and outcome
boundaries. These synthetic boundary tests do not establish successful execution
of the concrete Linux backend.

Complete offline packaging now selects tracked runtime sources, migrations,
scripts, generated units and unchanged lock-derived dependencies. It binds the
CPython 3.12.10 and uv 0.13.1 archives, safe member inventories, full installed tool
trees and actual virtual-environment files, including generated entrypoints and
configuration. Final verification rechecks interpreter libraries and installer
bytes and imports entrypoints without networking or bytecode writes. Admission
reserves account for remaining package/tool/dependency allocations. Public
manifests exclude configuration contents and private configuration paths.

A disposable local x86_64 Ubuntu VM under QEMU TCG booted real systemd and cgroup
v2. Linux rehearsals established:

- Fresh final-path offline package installation with 35 locked runtime wheels,
  CPython 3.12.10 and uv 0.13.1. All 14 selected runtime/deployment entrypoint
  modules imported; 1,757 installed files and complete tool trees remained
  unchanged. This packaging rehearsal used explicitly synthetic image/configuration
  bindings and does not certify complete image or configuration selection.
- Real delegated process placement, aggregate limits, a bounded OOM injection
  using at most 64 MiB allocation and 32 PIDs, a disposable limit change, kernel
  log bounds and ext4 output exhaustion. Positive allow-file inhibition and the
  scoped output mount survived a guest reboot. Created units, mount and backing
  file were subsequently removed and checked.
- Disposable PostgreSQL transaction/admission tests: 78 passed; the unique database
  and role were dropped and absence verified.
- An inert rootless-image socket probe accepted container UID 0 mapped to host
  UID 1000 and rejected container UID 1 mapped to host UID 100000. It mounted only
  a disposable socket directory. The selected image was the pinned coordinator
  Python base, not the complete coordinator image. Both containers and the socket
  were removed. A later repeat stopped before creation when the fixture daemon
  was unavailable after VM restart; its failed-attempt record remains private.
  After inspecting and restoring the disposable fixture daemon, the revised
  probe passed in a fresh generation with verified container/socket removal.

The independent reviewer found and prompted corrections for precondition ordering,
read-time atime changes, observation deadline bypasses, missing installed tool-tree
verification, archive ancestor symlinks and watchdog cgroup aliases. The watchdog
also requires separate native authority and a raw bound postflight observation;
exit status alone cannot certify paused state or cleanup. Limited source review
has not approved the complete installation/rollback proposal.

## Outstanding work and separate external facts

Implementation: finish and rehearse the complete concrete installation,
interruption/reconciliation and guarded rollback path; complete all scenario
runners, validators and native watchdog integration; use the complete coordinator
image for the peer probe; close image/configuration installation and restoration
bindings. Generic watchdog and probe helpers do not complete acceptance coverage.

Rehearsal: local x86_64 Linux is available. The full engine/rollback and complete
bounded acceptance paths remain unpassed. Failed attempts are retained; no
synthetic or local receipt is promoted to installed-native VPS evidence.

Host facts: fresh privileged recursive scheduling owners/references and original
settings, cron/at contents and dispositions, complete container births/policies,
actual cgroup permissions/controllers/effective limits, compliant persistent output
storage or exclusive allocation, rootless mappings, rollback compatibility and
fresh memory/disk admission remain necessary. See the existing
[owner-console procedure](../../PROTECTED_RUNTIME_OWNER_COLLECTION.md).

Review: complete source, release contents, concrete proposal and coverage require
independent review after the remaining work. No exact-byte installation approval
is requested. No VPS mutation, scientific evaluation, production epoch, capacity
measurement, public listener, notification, publication or backup ran.
