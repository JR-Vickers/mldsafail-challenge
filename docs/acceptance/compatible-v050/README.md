# Compatible 0.5.0 staging acceptance — 2026-10-03

**The checkpoint did not pass.** Deployment failed on native Compose v5.5.1,
and dependent seven-scenario and rollback/forward acceptance stopped as required.
Staging is healthy on exact `b4d212d`; accounts, tokens, results, schema, worker,
epoch and scoring are preserved. One stale queued cancellation was repaired.

The isolated acceptance branch starts at exact `b4d212d`. Its evaluator, benchmark,
trusted source, schema, worker/application locks, Dockerfiles and private Compose
configuration remain byte-identical. The expired-token UI change and operator
runner live outside that frozen evaluator directory. Candidate `b85ce57` archives
and images were retained and independently verified locally and natively.

Native preparation passed authentication, revoked-token rejection, compatibility,
resource floors, fixture bytes, frozen host environment provisioning, backup and
disposable restore, and queue preview/apply/reapply (1/1/0). Separate synthetic
material passed signals, SIGKILL, actual SSH PTY loss, concurrent invocation,
cleanup failure and repeated cleanup. Raw journals, dumps and queue identities
remain private on the VPS.

The first PostgreSQL probe failed because its privacy variable shadowed SQLAlchemy
`text`; it was fixed before maintenance. The first preparation journal generation
failed before any service mutation and was cleaned up separately. Deployment then
failed because `compose create --no-deps` is unsupported. Restoration's
`compose up --no-deps` also restarted the existing migration service. It was
stopped, and an independent disposable restore comparison proved the live schema
matches the pre-maintenance dump. Immutable row hashes and epoch identity also
match their pre-maintenance values. No active jobs or owned containers remain.

The runner now explicitly resets web/coordinator dependencies and uses supported
`up --no-start --no-deps` to prepare a stopped coordinator. Native configuration
parsing validates the dependency reset; deployment was not retried. Failed command
output is now retained in a protected native log. These fixes require a new
source-bound build before another attempt. Local verification: 53 focused tests,
317 full-suite tests, eight skipped native tests, and historical smoke score 3901.

The older `eef20af` report's unchanged worker/benchmark identities do not establish
hosted evaluator compatibility: that source changes three fingerprinted evaluator
files. Its artifacts must not be used with this epoch. The compatible branch keeps
those files frozen. No 0.6.0, off-host recovery, production or public-launch gate
passed. See [the gate report](report.json) for separate pass/fail/pending entries.

The later [Compose remediation checkpoint](../compose-switch-remediation-20261003/README.md)
passes disposable native switches and cleanup against fresh retained release
`fd4be66575ae6dbef9785321a79a687f418df0b8`. The original failure gates above remain
historical evidence; live acceptance was not retried during that remediation.
