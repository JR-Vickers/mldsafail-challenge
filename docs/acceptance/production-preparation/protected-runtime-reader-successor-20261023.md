# Host-reader engineering checkpoint — 2026-10-23

The protected-runtime installation proposal remains incomplete. This checkpoint
continues the [installation proposal checkpoint](protected-runtime-proposal-checkpoint-20261022.md)
and does not grant collector installation, VPS installation or launch authority.
The [machine record](protected-runtime-reader-successor-20261023.json) binds the
implementation commit, exact source hashes, scoped review and private evidence.

The scheduling reader now distinguishes optional absent children under valid
symlink parents from genuinely dangling targets. It rechecks traversed identities
after absence and errors, preserves kernel ordering for intermediate links and
`..`, and rejects identity races. A missing `atq` alone no longer satisfies
collection completeness. Standard-location absence requires corroborating service,
process, executable and spool observations; owner classification remains required.
The server's `/bin` link and installed collector have not been changed.

A separate successor archive builder freezes a finite script/storage allowlist
and exact script hashes, with a new root directory and exact sudo fragment.
It adds bounded private script reads, identified at-job contents, other-owner
read-only Docker inventories, daemon UID/GID maps, runtime-user cgroup permissions
and output backing observations. It does not execute discovered scripts/jobs,
install utilities, change schedulers or update itself. Both collection command
paths use the existing descendant-reaping helper. Failed cleanup retains compact
birth and command evidence. See the [collection procedure](../../PROTECTED_RUNTIME_OWNER_COLLECTION.md#successor-reader-preparation-not-installed).

Independent scoped review identified privileged disclosure through replaceable
script paths, immediate-child-only timeout cleanup, mixed cgroup permission
observations and missing containment on the initial scheduling pass. Corrections
bind exported contents to frozen hashes, use the subreaper for both command paths,
reserve cleanup time and compare repeated complete cgroup snapshots. Scoped source
review found no additional actionable defect after these changes. This is not a
review of the full installation proposal or installed collector behavior.

A private dossier binds the existing scan and its raw section hashes: 34 accounts,
88 sections and 895 paths. It preserves every original path observation and every
section's original-settings reference. Ten prerequisites are marked evidenced,
proposed or blocked. Unclassified owners/references, the old `/bin` child errors,
at corroboration, other-owner daemon policies, UID joins, runtime delegation and
storage preservation remain explicit blockers. The successor is prepared locally,
not installed; it cannot refresh those host facts through the old sudo rule.

| Gate | Disposition |
|---|---|
| Implementation | Reader corrections and separate successor preparation implemented. Complete reusable installation/rollback fixture, partial substep continuation and 21 remaining acceptance runners are still unfinished. |
| Rehearsal | 65 focused tests passed in the retained emulator. `make check` passed 1,877 tests with 58 skips plus 8 contract checks. These do not replace the complete install/rollback/control rehearsal. The prior 0.8-second helper failure is unchanged. |
| Privileged host facts | Original scan preserved and dossier bound; readiness remains false. No successor installation or privileged refresh performed. |
| Independent review | Collector scope reviewed; complete source/release/installation/rollback/coverage set remains unapproved. |

The focused source fixture was removed after hash, ownership, mount and process
checks. The first unprivileged cleanup inspection was blocked by a process-cwd
permission error and made no deletion; a privileged fixture inspection resolved it.
The guest was powered off and QEMU reaped. Its resume driver returned nonzero
when its running-state assertion observed the requested shutdown. Both dispositions
are retained. The existing guest remains the named incomplete-fixture retention
exception due for review on 2026-10-29.

No scientific evaluation, epoch, capacity investigation, purchase, public listener,
notification, publication, backup setup or VPS mutation occurred. Current
installation, compatible rollback and scientific evidence remain preserved.
Historical receipts retain their original outcomes. No installation authority is
requested against these incomplete gates.
