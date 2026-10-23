# Installation substep checkpoint — 2026-10-23

The requested complete installation proposal is **unfinished**. This checkpoint
starts from `d5245ad` and records component engineering only. It supersedes no
historical receipt and grants no collector installation, protected-runtime
installation, installed-native acceptance or launch authority.

New installation journals begin with recovery protocol 2. Legacy journals remain
protocol 1; reconciliation cannot upgrade them. Unsupported or misplaced protocol
headers fail closed. Mutation intents and outcomes now carry parent-step and
expected-effect fields in addition to the journal's proposal hash.

Each snapshot file has a durable intent before exclusive creation, followed by
hash/mode verification and an identity acknowledgement. After interruption,
separate reconciliation may mark the snapshot step partially reconciled only
when every attempted file has one unchanged acknowledged identity and every
unstarted file remains absent. A fresh execution authority is still necessary;
execution rechecks those identities, reads the original inputs again and skips
unchanged acknowledged files. Replacement, deletion, dangling symlinks, changed
input bytes and unacknowledged creation block continuation. Rollback cannot treat
a partially reconciled installation as complete.

Bundle files, the copied manifest, extracted tool trees and generated private
configuration files also receive per-resource intents and verified outcomes.
Reconciliation reads bound file/tree identities and records completed, absent,
replaced or ambiguous observations. These receipts confer no partial-continuation
permission for those operations. Failed extraction preserves its partial tree and
observation error. Docker, dependencies, scheduling, units, prerequisites and
activation retain their prior conservative recovery behavior; their complete
substep recovery is still required. Regular-file identity reads now bind a
no-follow descriptor, and symlink observations recheck their birth after readlink.

The [machine record](protected-runtime-substeps-20261023.json) binds the source
checkpoint and verification evidence hashes. No complete proposal, review or owner
authority was regenerated. A future proposal must include the changed source,
regenerated release closure and new exact-byte review and authority bindings.

Focused mutation, installation, recovery, artifact and prerequisite regressions
passed. `make check` passed 1,897 tests with 58 skips and all 8 contract checks.
All 63 local links in the changed Markdown documents resolve, and
`git diff --check` passes. These local checks do not establish Linux runtime or
installed-native acceptance.

| Gate | Disposition |
|---|---|
| Implementation | Partial: snapshot continuation and artifact receipts implemented. The reusable complete concrete-engine fixture, external-effect substeps and rollback completion, and 21 remaining executable acceptance runners are unfinished. |
| Rehearsal | Local synthetic/filesystem checks only. No complete disposable PostgreSQL/Linux installation or rollback rehearsal in this checkpoint. The prior emulator failure against the unchanged 0.8-second helper deadline remains. |
| Privileged host facts | Blocked: successor installation remains a separate administrator action. Recursive owner/reference classification, at corroboration, other-owner daemons, UID joins, delegation and output preservation facts remain incomplete. |
| Independent review | Unpassed: no independent review of this change or the complete frozen installation/rollback/acceptance set has been obtained. Prior collector review retains its original limited scope. |

Read-only local inspection found macOS/arm64, an unavailable Docker Desktop
daemon and no running QEMU/Linux guest. No infrastructure was bought, no emulator
was started and no VPS action occurred. Existing retained resources were not
cleaned or reused without their ownership and lifecycle records. The tests create
only pytest-owned temporary files; no external fixture resources were created.

The $0 budget and 0.5.0 semantics remain unchanged. No solver evaluation, epoch,
capacity investigation, public listener, notification, publication or backup setup
occurred. Epoch-policy replacement remains a separate launch dependency. Paused
VPS installation and installed-native acceptance still require their own exact
artifact authorization after all four gates pass.
