# Protected-runtime artifact hardening checkpoint — 2026-10-21

Disposition: implementation incomplete; no installation proposal approval. This
checkpoint does not complete the installation-ready development phase. Budget
remains $0 and benchmark remains 0.5.0 preview. No VPS operations, evaluations,
epochs, listeners, notifications, publication or backups ran.

Implemented changes:

- Systemd inhibition requires a positive owner-specific permission file. This
  proposal creates no permission file. Missing permission keeps the condition
  unsatisfied across reboot. Retained units remain excluded. Unsupported owners
  and schedulers remain blockers. This is proposal rendering, not native proof.
- Release freeze and verification reject filename-shaped fake wheels. Validation
  checks ZIP member paths, duplicate members, symlinks, distribution identity,
  metadata, Python constraints, filename/metadata tags and every payload's RECORD
  digest and size. The conservative target is CPython 3.12 on x86_64 with glibc
  at least 2.17; unsupported or uncertain Python constraints and platform tags
  fail. Actual target interpreter and libc observations are still prerequisites.
- `freeze_runtime` selects tracked runtime package files, Python/shell deployment
  and script modules, migrations, package data and explicit top-level build/image
  inputs. Missing tracked files, unknown package-data types and symlinks block
  freezing. Untracked material and deployment configuration bytes are excluded.
  The lower-level historical `freeze` primitive still accepts explicit subsets;
  its receipts must not certify full-runtime completeness.

## Verification and independent checkpoint review

Independent review by `/root/review` found unsupported glibc tags, missing
metadata/Python binding, untracked-file inclusion, omission of deleted tracked
modules and patch-version uncertainty. Each finding was corrected with regression
coverage. Final checkpoint re-review found no further blocking findings in this
limited scope; it expressly did not approve an installation proposal.

The focused release/wheel/scheduling suite passes 34 tests. Full `make check`
results and source hashes are retained in the adjacent machine-readable receipt.
No actual wheel was installed and no installed-runtime evidence is claimed.

A bounded local probe started `qemu-system-x86_64` with TCG, a paused CPU, no guest
image, no network, no disk and no listeners, then terminated and reaped that exact
child. This verifies emulator availability on the ARM64 Mac only. No x86_64 guest
has booted in this checkpoint; systemd/cgroup-v2/reboot/mount rehearsals remain
unperformed. No disposable VM or database fixture was created or left running.

## Remaining implementation and evidence

Implementation is unfinished: v3 preparation/installed-inspection integration,
lock-derived transitive dependency closure, exact interpreter/installer binding,
installed dependency-file verification, container restart-policy adapters,
prerequisite provisioning proposals, recoverable installation/reconciliation and
rollback, strict packet watchdog and complete control runners/validators. These
are engineering gaps, not consequences of missing privileged access.

Rehearsal is incomplete: boot and validate a disposable x86_64 Linux guest with
real systemd and cgroup v2, then run fresh offline installation, interruption,
rollback, reboot inhibition and complete bounded acceptance. Emulator availability
is confirmed; no environmental impossibility is asserted.

Host facts were not refreshed. Outstanding privileged facts remain complete
scheduling-owner/reference closure and dispositions, container policies and at-job
contents, delegation/ancestor permissions and limits, rootless UID mappings,
compliant output storage or an exclusive allocation proposal, compatible rollback
identities and fresh memory/disk admission. See the existing owner-console
procedure; historical observations do not establish current readiness.

Review is complete only for this checkpoint. Full frozen installation/rollback
proposal review remains outstanding. Exact installation authorization must not be
requested from this checkpoint. Live installation and native acceptance remain
separately gated.
