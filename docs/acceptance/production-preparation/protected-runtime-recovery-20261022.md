# Conservative installation recovery — 2026-10-22

This advances the [mutation checkpoint](protected-runtime-mutation-evidence-20261022.md).
The full installation proposal remains unfinished and unapproved. The
[machine record](protected-runtime-recovery-20261022.json) binds this scoped change.

A verified whole-step resource acknowledgement now precedes the final engine
outcome. Fresh authorized reconciliation can accept that acknowledgement only
when the actual observed resource identities still match. An interruption before
acknowledgement still preserves and blocks an unacknowledged creation. A changed
acknowledged resource is classified as replaced, without adopting or removing it.

For three narrow operations—release-directory creation, supervisor enable-file
creation and snapshot-file creation—fresh reconciliation can record proven
absence when every observation matches the original absence and no resource
acknowledgement exists. A later, separately authorized execution rechecks that
absence before writing another intent. This does not authorize replay of image,
dependency, scheduling, unit, configuration, activation or prerequisite mutations.
Partial substep continuation remains unfinished.

Independent review identified a rollback case in which a reconciled absence was
treated as an existing enable file. The correction distinguishes positive creation
receipts from absence receipts. Rollback preserves an unknown enable file or a
dangling symlink, and absence cannot satisfy a required positive prior outcome.
The reviewer found no remaining concrete defect in the corrected scoped hashes.
This is not review or approval of a complete installation proposal.

Focused checks passed **128 tests**, including **21 new recovery cases** using
real filesystem creation under synthetic orchestration. They are not Linux host
or installed-runtime acceptance. The earlier **72 focused emulator tests** and
kernel postflight checks retain their original source bindings and scope; they
were not rerun or promoted to evidence for these new recovery bytes.

The owner confirmed the existing VPS endpoint. A read-only root-login check using
the existing pinned identity was rejected with `Permission denied (publickey)`;
the runtime account also requires a sudo password. Administrator involvement is
therefore still needed to collect privileged facts through the
[owner procedure](../../PROTECTED_RUNTIME_OWNER_COLLECTION.md). No sudoers,
SSH-server or other VPS setting changed.

| Area | Disposition |
|---|---|
| Implementation | Whole-step acknowledgement recovery and three proven-absence transitions implemented; full reusable installation/rollback fixture, partial substep continuation and remaining control runners/packets unfinished. |
| Rehearsal | Platform-neutral filesystem recovery verified locally. Complete runtime still blocked by the retained emulator helper deadline failure; no suitable native host found. |
| Privileged facts | Unprivileged refresh passed; root access denied and passwordless sudo unavailable. Scheduling/reference closure, delegation/UID mapping, ancestor limits and storage feasibility remain outstanding. |
| Independent review | Scoped finding corrected and reviewed; complete frozen proposal still unavailable for approval. |

The previous retention disposition remains current: local answered transfer
archives removed, compact records retained, guest powered off/reaped, and guest
source copies preserved pending process-visibility classification, with review
due 2026-10-29. No new Linux fixture was started for this recovery change.
No scientific work, installation, native acceptance, launch or publication was
performed or authorized. Budget remains $0.
