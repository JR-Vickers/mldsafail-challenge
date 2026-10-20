# Production configuration and epoch operation preparation — 2026-10-20

**0.5.0 preview; 0.6.0 ignored; C diagnostics abandoned; backups deferred.**
Configuration preparation **passes with only the future independently audited
epoch unresolved**. Item 3 remains **partial pending item 4**. The separate
production wrapper and exact private packet are ready for owner review, with
independent review pending and no execution authorization. [Status](production-preparation-20261020.json).
Historical preparation reports and original candidates remain unchanged.

Bounded SSH reused the recorded key/account and pinned ED25519 host identity.
Read-only inspections refreshed the existing rootless daemon, exact selected
images, all containers and named volumes, active mounts, paths, processes,
user-manager jobs and retained trial configurations. The committed
[inspection helper](../../../deploy/production_inspection.py) was streamed through
SSH; it wrote no remote files. Container IDs, image IDs, status, start times and
restart counts agree before/after. No images were loaded or run.
The [image-loading receipt](candidate-image-load-20261020.md) retains the owner's
accepted original-worker build-commit limitation and confirmed OAuth URLs.

The supplied database/session secrets are suitable and differ from each other,
active container values and all three executed retained rehearsal configurations.
They were preserved. The absent earlier C environment belongs to a withdrawn,
unexecuted draft: dated withdrawal evidence and the cleanup inventory's empty
operator journal/daemon inventory establish its disposition. Both records and
hashes are bound into the inspection receipt; an arbitrary missing trial record
still fails validation. Supplied OAuth values match privately. URL confirmation
remains distinct from registration inspection, live login and trusted TLS checks.
No credentials or secret-derived hashes are included here.

The new versioned owner-only candidate and receipts use directories 0700/files
0600. Previous candidates, drafts and activation links were preserved. Remote
checks reconcile evaluator/jobs/signing-key, TLS and ACME paths, symlink
resolutions, bind mounts and filesystem aliases. The production project and its
three named volumes are separate from active and retained projects/resources.
The logical database name `mldsafail` is intentionally shared inside a separate
PostgreSQL volume and project-local `db` endpoint. No production resources were
provisioned. Synthetic epoch substitution allowed an in-memory Compose check;
no deployable synthetic environment was written. Actual final rendering remains
a post-epoch requirement.

[Preflight](../../../deploy/production_preflight.py) now requires source-bound
manifest and inspection evidence in both modes. It validates candidate/receipt
hashes, daemon/socket/image identities, separate OCI index/platform/configuration
identities, immutable source revisions, retained secrets and storage namespaces.
It rejects malformed, stale, insecure or changed records and emits fixed codes
without configuration values. Upstream archive omissions are accepted only for
the previously verified non-amd64 descriptor scope; an amd64 omission fails.
Real preparation CLI and operation `prepare` pass. Full CLI refuses this candidate
because no genuine audited epoch/final manifest exists.

The [separate production entry point](../../../scripts/production_epoch_operation.py)
provides `prepare`, `execute`, `audit` and `finalize`. It binds selected frozen
helper hashes from Git, committed operator sources/runbook, host/account/socket,
controller/worker identities, output destinations and limits. Relative private
bundle references allow transfer without changing packet bytes; execution also
requires the exact reviewed remote bundle destination. No transfer took place.
The rehearsal-only entry point and its purpose guard remain unchanged.

Execution requires independent review and a separate exact owner authorization.
It holds a nonblocking lock, publishes a durable exclusive attempt marker before
creation, and invokes unchanged frozen creation once. Logs stream to private
files, including partial output and exit evidence. Failure, interruption and
timeout are terminal; timeout cleanup inspects unique ownership labels and skips
already stopped resources. Audit runs separately with a read-only epoch mount,
no socket, the existing seal and exactly 100 reference cases. Finalization checks
sealed bytes again, writes a separate final manifest with actual audited identities
and a new environment, and requires full preflight/rendering before readiness.
All creation/audit/finalization verification in this phase used synthetic mocks.

The private `HANDOFF.md`, packet and receipt hashes are in
`$HOME/.config/mldsafail-production/preparation-20261020-v2`; the
[procedure](../../PRODUCTION_EPOCH_PROCEDURE.md) gives exact commands, approval
schema, failure handling and postflight. The independent review receipt says
**pending**; implementation tests are not independent review. No owner
authorization file exists. Before later execution, refresh/rebind expiring receipts
and obtain a new exact approval. Establish a maintenance window, stop/fence the
bound existing coordinator and disable automatic restart under separate authority;
verify other scheduling owners and an adequately delegated worker cgroup. The
proposed slice has not been provisioned or accepted. An operation lock alone does
not fence scheduling. Execution remains blocked until these prerequisites hold.

No production epoch/evaluation, solver experiment, deployment, live-service change,
listener, CA issuance, OAuth login, notification, publication or push occurred.
No public API, scoring, database schema, frozen benchmark or contestant contract
changed. Scientific data and retained historical results were preserved.

Validation: **79 focused tests passed**. Final `make check` passed **1,226 tests,
15 skipped**, plus **8 contract tests** (12 existing warnings). Checks covered
purpose/authorization/source/image guards, stale or malformed receipts, private
permissions and aliases, secret reuse, scheduling fences, nonblocking locking,
single-attempt behavior, before/during-creation failures, interruption, timeout
logs/owned-resource termination, failed audits, host drift, altered seals,
relocatable bundle hashes and synthetic successful finalization. **50 local
documentation file links** and `git diff --check` passed. Receipts and test logs
remain private. Validated checkpoints were committed locally; nothing was pushed.
