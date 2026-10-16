# Email and missed-heartbeat preparation — 2026-10-13

The inactive adapter is `deploy.healthchecks`. It sends fixed service/recovery
status bodies to private UUID endpoints, with TLS verification, no redirects,
three bounded attempts and redacted delivery errors. A 200 response containing
an ignored/rate-limited marker is a delivery failure. Every healthy monitor run
pings, including when status is unchanged. Failure uses `/fail`; a later healthy
ping signals recovery, as documented by the [Healthchecks Pinging API](https://healthchecks.io/docs/http_api/).

The owner must create two checks and verify an email integration:

| Check | Period | Grace | Success condition |
| --- | --- | --- | --- |
| service | 5 minutes | 10 minutes | All current host readiness/service/resource/lease/backup checks pass |
| recovery | daily | 4 hours | Upload, restore/audit, independent cleanup and retention finish successfully |

Store UUID URLs in separate 0600 files outside source, contestant and public
artifacts. Add `healthchecks.enabled=true` and the two endpoint-file paths to the
private monitor configuration; add the same recovery endpoint configuration to
the daily recovery configuration. `deploy/templates/monitor.json` remains
disabled. No endpoint, recipient or account was created or contacted.

`host_checks` sends regular service heartbeats; `daily_recovery` sends recovery
success only after its verified marker, and failure on exceptions. Cleanup-only
invocations do not imply backup success. Delivery failure remains observable as
nonzero exit; a completed backup receipt is retained even if its notification
fails. Do not treat notification failure as permission to redo a backup blindly.

Local tests cover repeated heartbeats, failure/recovery signals, transient retry,
exhausted delivery, endpoint rejection and ignored responses. Actual email and
missed-heartbeat acceptance require owner-supplied endpoints, verified recipients
and explicit delivery authorization: on separate disposable checks, stop pings
for period plus grace, confirm email, send a recovery ping and confirm recovery
email. Repeat with an unreachable endpoint and inspect fixed local errors. Keep
timestamped delivery receipts private and publish only pass/fail/check names.
