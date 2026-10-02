# Engineering handoff — 2026-10-02

The optimization pilot and single-host stability study remain complete. No new
solver experiment, score, epoch or production activation is performed here.

Implemented locally: participant package 0.5.1 with default MLWE 0.5.0 scaffold,
wheel inclusion from the approved source, explicit historical options, logs/cancel,
retry-aware follow status and sanitized job metadata; isolated POSIX wheel
installer; negotiated acceptance Docker API and network preservation; serialized
cleanup/heartbeat journals, sealed cleanup and retryable cleanup diagnostics;
experimental host cgroup CPU collection; inactive recovery and webhook tooling;
bounded read-only staging load runner; production Compose preparation.

## Recovery setup (inactive)

Download the pinned Linux amd64 restic 0.18.1 archive from the URL in
`deploy/install_restic.py`. The installer verifies the upstream archive SHA-256,
refuses overwrites, and emits the installed binary SHA-256 for configuration.
Upstream release and installation verification:
https://github.com/restic/restic/releases/tag/v0.18.1
https://restic.readthedocs.io/en/v0.18.1/020_installation.html
S3 repository configuration:
https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html

Use separate `s3:https://ENDPOINT/BUCKET/staging` and `/production` repositories.
Private 0600 JSON config supplies `restic_binary`, `restic_sha256`, `repository`,
`environment`, `password_file`, `credentials_file`, `owner_retained_recovery_key`.
Credentials JSON contains only scoped AWS access variables. Retain the password
independently off host before setting the owner confirmation. Never include
credentials or the password in recovery sets. No repository has been initialized.

A new sealed recovery directory contains `recovery.json` with `files` (relative
path to SHA-256) and `categories` (file lists for database, epoch, evidence,
configuration, secrets, release and images). Copy only completed evidence and
sealed epochs, private application/evaluator configuration and secrets, release
manifests and retained image archives. Never copy mutable jobs or temporary
credentials. Stop claims, wait for active work, quiesce web, take a PostgreSQL
custom dump, and verify in an isolated restored database before setting
`database_evidence_verified`. `deploy/verify_recovery_evidence.py` independently
audits the restored MLWE database's result references and epoch identities.
Preserve the live database. Record the verification result privately alongside
snapshot identity and dump checksum. `deploy/assemble_recovery.py` prepares a new quiescent set, audits all referenced
MLWE evidence in the deployed coordinator, and restores original service states
on failure. A private maintenance journal retains restoration failures.

`deploy/recovery.py` supports backup, full repository check, isolated restore to a
new path, and retention/pruning. Pruning requires `restore_verified_snapshot`;
retain seven daily, four weekly and six monthly snapshots. Configure the supplied
daily/weekly systemd units only after repository initialization, recovery-key
retention and a successful isolated restore. The daily service invokes `deploy.daily_recovery`: assemble a fresh set, upload,
restore into a new directory and disposable PostgreSQL container, then audit the
restored evidence in an isolated coordinator container. Verified-backup state is
written only after successful verification and container cleanup. Native execution
and abrupt-process-death recovery of the assembly step remain pending.
Record the latest *verified* snapshot time, daily freshness and a four-hour
restore target. Missing or older-than-26-hour verified backups are alert failures.
Actual S3 upload interruption, repository corruption and restore tests remain
pending storage credentials. Local checksum-corruption/missing-material tests
are not substitutes.

## Monitoring, load and production gates

`deploy/host_checks.py` evaluates readiness, service health, resource floors,
expired leases, verified-backup freshness and failed scheduled jobs. Queue length
alone cannot fail it. The owner-configured monitor reads service states, coordinator leases and
scheduled-unit results, plus repository-bound verified-backup state. A separate
inactive monitor service/timer supplies native wiring; activation remains pending.
`deploy/alert_webhook.py` sends only fixed failure codes, with three bounded
attempts, ten-minute deduplication and immediate recovery notifications. Local
receiver delivery is verified; external destination activation is pending owner
URL/credential. Do not log credentials or raw exception text.

Run `scripts/staging_read_load.py` on staging with explicit server, private token
file and a new evidence output path. It uses ten client threads, five aggregate
anonymous reads/sec for five minutes, plus one authenticated read/five seconds;
no submissions. It requires no request errors or host-floor breaches, p95 <1s and
p99 <2s. Preserve failures without relaxing thresholds. Native execution pending.

`compose.production.yaml` validates with synthetic secrets and has a separate
project/volumes, HTTPS Caddy configuration and production secure-cookie settings.
PostgreSQL and Docker have no public port. Proxy blocks operational endpoints;
health checks run inside the web container. Use production DNS/OAuth, fresh
secrets and a new reviewed epoch/environment cohort. Never reuse staging secret
files, database volumes, epoch identities or automatic migrations. Verify rootless
low-port policy on the production host. No production containers were started.

Before an external pilot: native seven-scenario acceptance, application-only
rollback/forward with retained b4d212d images and live DB, verified encrypted
restore, fresh backups/alerts, bounded load gate, owner-reviewed measurement
proposal, release checksums and installation smoke, production DNS/OAuth and owner
activation decision. Public publication and recruitment remain owner actions.

## Pending acceptance and engineering

Saved active/revoked token files, SSH identity and prior release/rollback
manifests were recovered from local metadata. Private locations are recorded in
`/tmp/mldsafail-native-inputs.json` (0600). Read-only SSH to the documented VPS
timed out on 2026-10-02, so staging env/deployment paths and native execution
remain unverified. Storage configuration and off-host key retention are pending. Retain fixture commit
`e547caffb06ced2e82f28cf1c130c8131613384d`. Run the seven scenarios sequentially;
keep 20-minute evaluation, 90-second cancellation and 150-second timeout ceilings.
No native gate is reported passed by this handoff.

Remaining local engineering before declaring the entire requested plan complete:
native interruption-at-each-boundary/process-race acceptance and abrupt-death
recovery for snapshot assembly. Cleanup-stage failure injection and stale-watchdog
resumption tests pass locally. The new application image release is frozen locally. CPU fixtures
and host membership proof are implemented, but native behavior is still pending. Native cgroup feasibility,
overhead/repeatability and isolated off-host restore need their respective host
and owner inputs. Existing safety, evaluator, worker locks and scoring are frozen.

## Local verification evidence

Final `make check`: 327 passed, eight native Docker tests skipped; historical
small score 3901, correct. The wheel was installed into a new Python 3.12.10
environment; default 0.5.0 clone, explicit 0.4.0 clone and historical run passed.
Approved starter bytes in the wheel match the source. Production Compose was
validated with synthetic secrets, and authenticated webhook delivery, ten-minute
deduplication and recovery were tested against a local receiver. Tests include
cleanup-stage failures, heartbeat/watchdog generation races, interrupted uploads,
missing/corrupt recovery material, host freshness/lease decisions and forged
worker timing/verification fields. Native tests are explicitly pending.

## Frozen application release

Application source `68946403410935379e31411d1723bdc19caa609e` is frozen in
`/tmp/mldsafail-release-6894640.json`. Both new Linux amd64 images built; the web
image health/starter smoke passed. Packaged evaluator Python source matches the
retained b4d212d coordinator exactly. Worker image, worker lock, historical and
MLWE fingerprints and staging Compose hash match rollback. Only root package
version metadata changed in uv.lock; dependency selections remain unchanged.
The application image archive is `/tmp/mldsafail-launch-preparation-6894640-images.tar`
(0600), SHA-256 `37feca005c7c2a441fd996d71b1e2c13a4f642ec50cbca293650808a94147f76`.
Exact b4d212d rollback images are retained. These are local artifacts; no deployment
or native epoch compatibility result is claimed.

The pinned restic Linux amd64 archive checksum and installed binary checksum
were verified. A synthetic encrypted local repository in an isolated Linux
container passed restore byte equality, wrong-password rejection and corrupted
pack rejection. Earlier Docker Desktop shared-filesystem reads failed with I/O
errors; those failures are recorded, and successful tests used Linux tmpfs.
This does not establish S3 upload, off-host restore or native rootless feasibility.
`scripts/restic_synthetic_acceptance.py` provides the reproducible crypto gate.
