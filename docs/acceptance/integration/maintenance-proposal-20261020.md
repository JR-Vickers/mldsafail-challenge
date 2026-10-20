# Maintenance proposal preparation — blocked

**0.5.0 preview; 0.6.0 ignored; C diagnostics abandoned; backups deferred.**

The new contract is `mldsafail.production-operation.v2`. Historical packets and
approvals are unchanged. A `maintenance_proposal` has
`scheduling_exclusion_verified: false`; only `execution_ready` binds a complete
owner-console receipt and verified exclusion. Neither preparation nor a proposal
confers execution authority. The five-minute execution window is unchanged.

The read-only [collector](../../../deploy/privileged_scheduling.py) is ready for
owner use in the existing root console. It requires no new sudo rules, stored root
credentials or SSH changes. Supply its SHA256 as `COLLECTOR_SHA256`, paste the
reviewed source into `python3 - <<'PY'`, and retain stdout privately with the exact
source and collection provenance. Commands have ten-second deadlines; outputs
are capped, cron/queue contents are represented by hashes, and file contents are
never printed. Explicit failures and unclassified paths block acceptance. The
collector intentionally emits an incomplete receipt: an owner/reviewer must
classify all inventories, symlinks and referenced scheduling scripts, including
paths outside the enumerated roots. Retain raw console evidence privately;
never copy credentials into receipts. Installed units, loaded units, timers and
running processes are distinct evidence. A missing `atq` alone proves nothing;
verified absence also needs absent service and spool evidence and owner review.
The earlier owner-pasted inspection is preliminary, not a complete receipt.
No new privileged evidence was collected during this local implementation.

Source review: `deploy/bootstrap/mldsafail-host-check.sh` only reads disk usage,
user-manager activity, socket and swap-file existence. It is inspection-only.
`deploy/backup_postgres.py` performs a 120-second bounded database `pg_dump` to a
private archive, then hashes the archive and writes metadata. It consumes CPU,
RAM, database reads and output disk; no resource cap or measured peak is provided.
The backup service invokes it against the deployment socket and existing secret
file. Preserve all backup settings. Backup provisioning remains deferred.

Safe draining is unresolved. The coordinator's continuous `while True` loop calls
`run_once`, which recovers stale leases and claims jobs; `--once` is a different
startup mode, not a live drain command. The admission/claim transaction mutex is
not an operator drain interface. No existing safe pause/drain mechanism was found.
An empty snapshot cannot close the admission/claim race. No database writes,
termination commands or assertions of an empty queue are proposed. Before command
approval, establish an existing safe admission fence and bounded drain, prove
queued/claimed/running state, record exact container IDs/restart policies and all
restart owners, then prepare stop/delegation/restoration commands. Keep web,
database and proxy running. Abort on nonempty/running work, timeout or identity
change. This blocker prevents a concrete runnable maintenance command packet.

Capacity remains unresolved. The retained prior host inspection is not a
compatible simultaneous worker/controller/services peak measurement. Configured
worker 2 GiB and controller 512 MiB limits remain frozen; adding them does not
establish required physical RAM. Physical RAM, available RAM, swap, observed
simultaneous usage, retained-service peaks and every ancestor cgroup limit must be
recorded separately. Swap is not capacity proof. No new capacity probe or
evaluation ran. Do not recommend this host or resize it without compatible
retained measurements and documented headroom. A separately approved resize is a
possible next decision if evidence cannot support this host.

Delegation remains unresolved: derive the Docker slice identifier and actual
sysfs path from the inspected user-manager hierarchy; verify UID 1000 ownership,
control files, cpu/memory/pids controllers and all ancestor limits. Do not create
a slice to discover its identity. Exact provisioning commands remain blocked on
that evidence. The existing execution delegation gate stays in place.

The private versioned proposal is under
`$HOME/.config/mldsafail-production/maintenance-20261020-v4`. It records blockers,
source/evidence identities and proposed destinations; evaluator destinations and
attempt markers remain uncreated. Transfer must bind the final committed operator
checkout, each bundle file hash and exact private destination; verify ownership,
0700 directories, 0600 evidence/configuration files and identical hashes after
transfer. Do not transfer until a concrete maintenance-and-transfer proposal is
approved. Final packet review and `production_epoch_only` authority remain later,
separate steps. On failure, restore scheduling only after positive verified
operation-resource termination and fresh postflight; ambiguous launches require
manual reconciliation. Original settings and exact restoration cannot be certified
until scheduling and drain blockers close.
