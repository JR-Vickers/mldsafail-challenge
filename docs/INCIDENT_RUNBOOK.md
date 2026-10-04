# Private operator incident runbook

Prepared 2026-10-04. Use the exact installed release environment and canonical
launch ledger. Keep raw evidence, identifiers and infrastructure details private.
This procedure never permits changing frozen profiles, scoring, epochs or worker
locks to resolve an incident.

## First response and ownership

Record a protected incident ID, UTC time, source/image identities, current
services, active job/attempt ownership and symptoms before intervention. Preserve
partial evidence and application logs. Serialize maintenance with evaluation,
load probes and recovery; one operator owns shared-host actions. Stop new claims
and admissions using reviewed controls, drain or explicitly cancel the owned
attempt, and retain intended service states plus exact container IDs in durable
maintenance evidence before stopping anything. Do not blindly resubmit on a lost
HTTP response: query the recorded idempotency key/submission until its fate is
known. Never kill an unaccounted process merely because it resembles a worker.

## Accounting, invalid answers and infrastructure failures

Missing/regressing CPU counters, ownership/membership contamination, surviving
processes and failed cleanup are infrastructure failures, not ordinary 60-second
penalties. Preserve attempts and audited status; fence cleanup ownership and
reconcile it before retry. Three-attempt exhaustion is terminal under the declared
policy. Invalid answers make the run ineligible; retain verifier evidence and
prevent leaderboard publication. Do not edit results, timings or reference costs.
The frozen 0.5.0 and proposed 0.6.0 cohorts must remain separate.

## Failed application deployment

Pause live acceptance after a failed application switch. Confirm exact retained
rollback images and immutable compatibility inventory. Restore only web/
coordinator application images with reset dependencies and `--no-deps`; invoke
no migrations. Restore original existing-container service states directly.
Verify health, auth, job state, DB/schema, result/leaderboard, epoch and worker
identities. Never restore the live database to repair an application deployment.
Document failure, cleanup and rollback before corrective engineering and a new
reviewed retained release; verify forward deployment separately.

## Recovery failure or stale verified backup

Treat absence or age over 26 hours of a verified backup as failure, even if an
upload completed. Preserve interrupted recovery journals, failed/local sets and
remote snapshots. Reconcile exact owned containers and intended service states
before another recovery run. Run the reviewed cleanup path again after correcting
its independent failure; do not mark `cleanup_complete` manually. Restore only
to a new isolated destination and database, audit restored epoch/results, then
publish verification state through the supported tool. Do not prune until an
actual isolated snapshot restore passes. If custody/storage access is missing,
record the exact missing owner input; retain local protected backups meanwhile.

## Alert or privacy incident

Inspect native checks and private delivery state. Receiver retries can produce
duplicates after a lost response; unchanged failure sets deduplicate for ten
minutes. A recovery notification follows previously delivered failure. Do not
clear failure state to silence an alert. For a suspected leak, pause distribution
and evaluation, preserve evidence privately, identify affected public artifacts
and credentials, and seek scoped owner revocation/public response. Send no public
or third-party message without explicit authorization. Never include raw evidence
or token values in the incident summary.

## Return to service and handoff

Require accounted resources, complete cleanup, intended service permissions/state,
readiness/authentication, independently audited result correctness, fresh verified
backup and relevant affected gate checks. Record exact repaired source/artifacts,
verification protocol, failure evidence, operator and UTC time. Public reactivation
or changed contract/default still needs its owner decision. Report unresolved
owner inputs explicitly; do not equate repaired private staging with public launch.

## Interrupted disposable rehearsal or public reproduction

Use the run's protected durable journal and the same current-user rootless Docker
socket. Acquire its existing exclusive run lock before cleanup; do not start a
replacement run against the same root. Source or release manifest corruption is
evidence to retain and does not grant authority to change run ownership. Cleanup
must cancel exact owned native client sessions before stopping dispatch controllers
and workers, then verify final owned container/network/volume inventories.
A missing client identity, surviving client or failed final inventory prevents
cleanup completion. Retained failed database volumes must be individually
accounted in the baseline journal; do not delete them merely to make inventory
empty. Public reproduction retains public input, partial output and failed
comparison evidence. A normalized match with incomplete cleanup is incomplete
acceptance. Reconcile interrupted clients and late Docker creation before running
another shared-host gate.
