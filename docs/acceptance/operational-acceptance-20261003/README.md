# Operational acceptance — 2026-10-03

This is a partial engineering result. Read report.json for separate pass/fail/pending
entries. No native failure scenario, rollback, off-host restore, alert delivery,
scheduler activation, 0.6.0 adoption, production launch or external pilot passed.

Local checks: 361 passed, eight native tests skipped; make check passed. New Linux
amd64 application images and their original participant 0.5.1 wheel are durably
retained at the full source identity in report.json. Native unit validation failed
because the installed host Python environment is absent; no units were activated.

Staging remains on exact b4d212d. Both saved active credentials return 401. The one
outstanding queue row belongs to an already cancelled submission and has zero
attempts. New queued cancellations now close their job row locally; the old live
row was not changed. The preflight stopped before service maintenance.

The CPU proposal records the requested 0.6.0 contract and fixed paired-measurement
thresholds, with review/adoption explicitly pending. No evaluator version dispatch,
0.6.0 epoch, reference costs, leaderboard cohort or participant package exists yet.
Capacity controls are enabled in production preparation; local concurrency tests
are not native PostgreSQL or hosted capacity acceptance. There is currently no
browser submission-creation endpoint; browser status pages retain access.

For the staging operator: open the existing SSH tunnel, sign in through GitHub,
create a dedicated acceptance token on /tokens, and save it in a private file.
Do not revoke/delete existing tokens. Verify the old cancelled queue row and close
it through a reviewed reconciliation before rerunning the strict preflight.
For backups, provide scoped cloud-storage configuration and retain the recovery
password independently off host. Provide an authenticated alert destination.
Provision the host Python environment before validating or activating units.
Failed and partial evidence remains retained; no cleanup was used to meet floors.
