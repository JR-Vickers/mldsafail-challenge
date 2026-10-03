# Operational follow-up — 2026-10-03

The requested operational acceptance plan is **incomplete**. Failed prerequisites
stop dependent maintenance, deployment and evaluation; there is no production
approval packet or public-launch decision.

Implemented a narrow historical queue reconciliation operation and private
append-only evidence. It closes only queued jobs joined to cancelled submissions,
under the admission/claim mutex. It neither claims jobs nor creates attempts,
transitions or schema changes. Claimed/running jobs are untouched. The operation
does not commit internally; preview rolls back and repeated application is a no-op.
No live reconciliation has been executed.

Use the new operational source in an environment compatible with the deployed
database, with its existing `DATABASE_URL`. First create a mode-0700 private
report directory, then run:

```sh
python -m deploy.reconcile_cancelled_jobs --report /PRIVATE/repair-preview.jsonl
python -m deploy.reconcile_cancelled_jobs --apply --report /PRIVATE/repair-apply.jsonl
python -m deploy.reconcile_cancelled_jobs --apply --report /PRIVATE/repair-repeat.jsonl
```

Every report path must be new. Private reports synchronize intent before commit
and outcome afterward; stdout contains counts only. If interruption leaves a
prepared record without outcome, inspect persisted job state and repeat with a
new report. Preserve the earlier report. This is an explicit maintenance operation,
not automatic coordinator startup behavior; frozen 0.5.0 evaluator source is
unchanged. Native PostgreSQL concurrency/repair acceptance remains pending.

Read-only native checks this turn: SSH and readiness (HTTP 200) pass; available
disk is 40,237,064,192 bytes and available memory is 1,354,388 KiB, above floors.
Rootless Docker reports cgroup v2. Web and coordinator remain exact b4d212d:

- Web: `sha256:f7426be504bede8c5e690b385707aae181e64edca76e3fc0f1336791c5ed2565`.
- Coordinator: `sha256:0277d476f750a19fa4033089449c3ef6ed0d86d7f8cc191f02eaf0370de2499e`.

Retained b4d212d and eef20af releases independently verify using retained copies
only. This does not demonstrate rollback or epoch compatibility. The host Python
environment is absent. Existing PostgreSQL backup is a **user** service; the
existing host check is a **system** service. New checked-in recovery/monitoring
units specify `User=mldsafail` and are intended as **system** services; do not
install those unchanged as user services. No new units were installed or activated.

The owner was given instructions for creating and privately saving a dedicated
acceptance token through GitHub OAuth. No replacement token path has been supplied.
The previous record's HTTP-401 token failure and stale queue remain unresolved;
this turn did not re-test credentials or claim that the queue is clear. Approved
S3/alert configuration and independent recovery-password custody are still absent.

[Independent CPU review](CPU_REVIEW.md) failed with seven unresolved implementation
and evidence findings. One scoring ambiguity was clarified without adoption.
0.6.0 supervisor, evaluator, audit, dispatch, cohorts, native acceptance and
participant publication remain pending. Native PostgreSQL admission/fencing,
both five-minute load gates, off-host recovery, alerts, restart acceptance,
production rehearsal and external pilot remain pending.

Local verification: six focused admission/reconciliation tests pass. Full
`make check` passes with 363 tests passed, eight native Docker tests skipped,
and historical smoke score 3901, correct. These are local engineering results.
No live database/service changes, deployments, secret rotation, migrations,
timer activation, pushes or public exposure were performed.
