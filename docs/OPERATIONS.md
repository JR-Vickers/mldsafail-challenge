# Private staging operations

As of 2026-10-01, the native Linux amd64 VPS runs private MLWE 0.5.0 staging.
Authenticated immutable-source evaluation and a verified leaderboard result are
documented in [PRIVATE_STAGING_STATUS.md](PRIVATE_STAGING_STATUS.md). Integrated
failure/recovery and rollback acceptance, automated off-host backups, and the final
migration decision remain open. The public measurement boundary and production
configuration remain separate requirements. See [PLAN.md](PLAN.md).

## Access and service boundaries

Use the non-root deployment account and its rootless Docker context:

```sh
ssh -i ~/.ssh/mldsafail_vps -L 8080:127.0.0.1:8080 mldsafail@178.128.17.58
```

`mldsafail` owns application/evaluator files and rootless Docker, without sudo or
root-owned Docker-socket access. `mldsafail-admin` is the separate maintenance
account. Password/root SSH and the root Docker daemon are disabled. The firewall
limits SSH to the maintainer source address; public HTTP/HTTPS are closed.
Changes to that address require maintenance access or the provider console.

The standalone `compose.private.yaml` defines web, coordinator, proxy, PostgreSQL,
and a single migration service. Only the coordinator receives the Docker socket
and evaluator mount. UID 0 inside its rootless namespace maps to the non-root
host deployment user. Contestant workers run separately as UID 65534. The proxy
publishes only `127.0.0.1:8080`; PostgreSQL and Docker stay private.

Staging uses real GitHub OAuth, with callback
`http://localhost:8080/auth/callback`. Development authentication is disabled.
Private staging uses HTTP-only, SameSite=Lax cookies through the SSH tunnel;
production must use HTTPS and secure cookies.

Use the actual release checkout and mode-0600 environment file outside it. Do not
print the environment file, expanded Compose configuration, or container secrets.
Set operator variables on the VPS, then define the command used below:

```sh
export STAGING_CHECKOUT=/ACTUAL/staging-checkout
export STAGING_ENV_FILE=/ACTUAL/private-staging.env
staging() {
  docker compose --env-file "$STAGING_ENV_FILE" \
    -f "$STAGING_CHECKOUT/compose.private.yaml" "$@"
}
```

These placeholder paths must be replaced. The installed backup unit uses its own
`/srv/mldsafail/current` working directory and separate database environment file;
verify installed unit paths rather than assume the acceptance runner's defaults.

## Immutable configuration and epochs

Pin `WEB_IMAGE`, `COORDINATOR_IMAGE`, `WORKER_IMAGE`, `CADDY_IMAGE`, and
`POSTGRES_IMAGE` to immutable image identities. Preserve the current generated
PostgreSQL, Flask, OAuth, and evaluator-signing secrets during release switches.
The environment also binds evaluator fingerprint, hidden-suite version, worker
class, and `MLDSAFAIL_MLWE_EPOCH_ID`.

The coordinator uses these existing private locations:

- `/srv/mldsafail-evaluator/epoch`: audited sealed epoch and fixed reference table;
- `/srv/mldsafail-evaluator/jobs`: source work and submission/attempt evidence;
- `/srv/mldsafail-evaluator/secrets/signing.key`: evaluator signing key.

The frozen epoch has 100 ranked cases, derived from a fresh private nonce and
20 seeds per profile. Its reference/viability executions, artifacts, host identity,
and manifests are audited before use. Keep raw nonce, seeds, candidates, streams,
and individual measurements on the evaluator host in restrictive directories.
Only whitelisted summaries may leave it.

The native worker uses `deploy/worker-linux-amd64.requirements.txt`, separately
reviewed from the original ARM64 lock. Source and dependency identities are
recorded in [HOSTED_V050.md](HOSTED_V050.md). Changing host, worker/dependencies,
case set, or execution environment requires a new compatible epoch/reference;
scores across those cohorts cannot be compared directly. Do not replace the
current staging epoch while testing recovery or rollback, upload a development
nonce, or silently select replacement seeds after failed viability gates.

New epoch provisioning follows the frozen contract and native deployment process
in [HOSTED_V050.md](HOSTED_V050.md). It is separate from ordinary release updates.
Production requires fresh secrets, its own hidden-suite version, and a distinct
native epoch; staging evidence is not production evidence.

## Application release and migrations

Build from a clean committed checkout, with Linux amd64 application images labeled
with the full source commit. The existing release recorder expects the hosted
application tags and native worker tag:

```sh
cd "$STAGING_CHECKOUT"
export RELEASE_COMMIT=$(git rev-parse HEAD)
docker build --platform linux/amd64 --label "org.mldsafail.source=$RELEASE_COMMIT" \
  -f Dockerfile -t mldsafail-web:hosted-0.5.0 .
docker build --platform linux/amd64 --label "org.mldsafail.source=$RELEASE_COMMIT" \
  -f Dockerfile.coordinator -t mldsafail-coordinator:hosted-0.5.0 .
python scripts/hosted_release.py --output /PRIVATE/new-release.json
```

Retain prior source, immutable images, and manifests before replacing application
tags. Review the release's evaluator fingerprint and worker environment against
the existing epoch. Updating application/docs alone does not authorize rebuilding
or replacing the frozen worker. Use manifest image IDs in the deployment
environment; source changes require a new recorded release.

For a normal first deployment or reviewed schema update, Compose orders database
health, successful migration, then application startup:

```sh
staging up -d db migrate web coordinator proxy
```

The private web/coordinator environment sets `MLDSAFAIL_SKIP_MIGRATIONS=1`.
Only the dedicated migration service runs Alembic; application processes do not
run it again. Plan migrations as separate reviewed operations with backup and
compatibility evidence. Application rollback below must not invoke that service.

## Participant submission, logs, and cancellation

With the SSH tunnel open, sign in at `http://localhost:8080`, create a participant
token at `/tokens`, and use the CLI:

```sh
mldsafail login TOKEN --server http://localhost:8080
mldsafail submit --repo https://github.com/OWNER/REPO --commit FULL_40_CHAR_SHA \
  --benchmark-version 0.5.0 --solver-path examples/mlwe/primal-lll \
  --idempotency-key UNIQUE_REQUEST_KEY --hypothesis "reference acceptance"
mldsafail status SUBMISSION_ID --follow
```

The selected directory must contain Python-only `solver.py` source satisfying
[MLWE_LOCAL.md](MLWE_LOCAL.md). Immutable sparse acquisition does not execute
repository installation scripts. `file://` targets are rejected in staging.
The owner publishes participant/fixture repositories manually; agents do not push.
Participant package 0.5.1 defaults `clone` and submissions to benchmark 0.5.0.
Use `--benchmark-version 0.4.0` for historical work; `mldsafail run` remains 0.4.0.

The existing bearer-token API provides status, sanitized attempt logs, and
cancellation. TOKEN and SUBMISSION_ID below are placeholders:

```sh
curl -sS http://localhost:8080/api/v1/submissions/SUBMISSION_ID/logs \
  -H 'Authorization: Bearer TOKEN'
curl -sS -X POST http://localhost:8080/api/v1/submissions/SUBMISSION_ID/cancel \
  -H 'Authorization: Bearer TOKEN'
curl -sS http://localhost:8080/api/v1/leaderboard \
  -H 'Authorization: Bearer TOKEN'
```

Cancellation is checked between frozen worker invocations; a running invocation
may take its full 60-second limit. Invalid candidates reject a run. Complete
crash/timeout/no-answer runs remain eligible with frozen penalties. Infrastructure
failures retry with separate attempt evidence and backoff; exhausted retries
become `infrastructure_failed`. Incomplete evidence is not rankable.

Keep active/revoked-token behavior and existing accounts/results intact during
acceptance. Do not automatically delete or revoke accidental token duplicates.
Tokens stay in the OS credential store; the CLI's private-file fallback is opt-in.

## Health, isolation, and logs

On the VPS, or through the tunnel for HTTP checks:

```sh
curl -sS http://127.0.0.1:8080/health/live
curl -sS http://127.0.0.1:8080/health/ready
staging ps
staging logs --tail 50 web coordinator proxy
```

Logs rotate at 10 MiB with three retained files. Host monitoring includes bounded
journals, disk/service checks, security updates without automatic reboot, and
2 GiB swap. These checks are not evidence of delivered alerts or completed load
tests; verify those production gates separately. Inspect diagnostics locally and
sanitize material before sharing; OAuth callback queries are excluded from access
logs. Avoid broad database dumps or container-environment output for diagnosis.

Live contestant isolation must show no network, read-only root, UID 65534, all
capabilities dropped, no-new-privileges, one CPU, 2 GiB memory/address-space limits,
64 PIDs, bounded output, 64 MiB temporary storage, and only a read-only solver
mount. No epoch, credentials, repository, Docker socket, or prior result mount
may enter a worker. Public-input isolation does not independently establish
hostile-code CPU measurement integrity; that remains a public-launch gate.

## Failure handling and application-only rollback

The [failure acceptance guide](HOSTED_FAILURE_ACCEPTANCE.md) is the executable
procedure for running cancellation, real timeout/cancel, invalid answers,
crash penalties, infrastructure retry/exhaustion, expired leases, and rollback.
The [preparation report](acceptance/hosted-failures/README.md) records locally
validated tooling and every unrun native gate. The [fixture repository](https://github.com/JR-Vickers/mldsafail-failure-fixtures)
is now public, verified on 2026-10-02, and pinned to
`e547caffb06ced2e82f28cf1c130c8131613384d`. Native execution still requires the
saved participant/revoked-token files and actual deployment paths.

Retain `b4d212da3109b7716eb41553986848e377fb5b3d` as the known-good rollback target,
with exact web/coordinator images and release manifest. For the acceptance drill:

1. Announce maintenance, prevent unrelated work, drain evaluations, and stop the
   normal coordinator. Verify no active worker remains. Install cleanup/watchdog
   handling before fault injection; never modify or delete existing evidence.
2. Quiesce application writes, take a PostgreSQL dump, and verify restoration in
   a disposable database. Hash immutable account, token, and result data on the
   VPS. Keep the live database running with its current schema and volume.
3. Use only the retained web/coordinator image IDs with the current secrets and
   epoch configuration. Stop the coordinator, create its replacement without
   starting evaluation, and start web using Compose `--no-deps`. Do not start
   the migration service, restore the live database, or downgrade its schema.
4. Verify live/readiness, active/revoked tokens, leaderboard equality, preserved
   result identities, and evaluator/worker compatibility. No evaluations run
   during the switch.
5. Repeat with the frozen new application release, verify the same invariants,
   then restore normal service. Preserve failure submissions and penalty results.

The runner performs these steps using private journals and bounded cleanup.
Interrupted runs use its documented `--cleanup` procedure. Native execution has
not yet demonstrated rollback; retained images alone do not close that gate.

## Backups and restore verification

The installed daily PostgreSQL timer writes local private dumps. To perform the
acceptance backup on a quiescent source, after draining work and stopping web and
coordinator, run the checked-in helper on the VPS:

```sh
python3 "$STAGING_CHECKOUT/deploy/backup_postgres.py" \
  --env-file "$STAGING_ENV_FILE" \
  --compose "$STAGING_CHECKOUT/compose.private.yaml" \
  --output /PRIVATE/postgres-backups --verify-restore
```

The helper uses mode-0600 dumps in a private directory, creates an exact named
disposable restore database, compares its normalized dump with the quiescent
source, and removes only that disposable database. It never restores over the
application database. Restart the intended services after verification; use the
acceptance runner's cleanup during its controlled maintenance window.

Local dumps are neither automatically encrypted nor off-host backups. Configure
and verify automated provider/off-host retention and restore access separately.
Private epoch and signing material require their own protected backup/recovery
policy; a PostgreSQL dump does not contain evaluator filesystem evidence. Do not
publish database or epoch backups.

## Incident response and production boundary

For credential compromise, stop affected service/intake, rotate the compromised
secret under a reviewed recovery procedure, revoke the affected credentials or
sessions, and preserve audit history. Token/submission actions should target only
the identified objects; queued cancellation is immediate and running cancellation
is bounded by the current invocation. Preserve accepted-result identities.

For epoch exposure or a worker/kernel concern, stop evaluation, preserve evidence,
and investigate locally. Replacing the host, epoch, or execution environment
requires new compatible cohort identities and reference costs. Do not reuse an
exposed nonce or reinterpret old results as belonging to the new cohort.

Production still requires DNS, HTTPS, production OAuth, secure cookies, fresh
secrets and epoch, an enforceable measurement boundary, verified off-host backups,
and the remaining operational/pilot acceptance decisions. This private staging
runbook does not authorize opening public ports or public submissions.

## Historical local 0.4.0 development

The development prototype is separate from private staging:

```sh
source .venv/bin/activate
make hosted-setup
make hosted-dev
make hosted-down
```

`make hosted-dev` uses `compose.yaml` plus `compose.dev.yaml` and `deploy/dev.env`.
It builds historical 0.4.0 images and runs database, web, proxy, and coordinator.
Docker Desktop must be running on macOS. Setup replaces the development seed file
under `HOSTED_EVALUATOR_DIR`; never configure it to point at private staging.
Development credentials/seeds and its startup migration behavior must not be used
for the private Compose deployment. Historical solvers, scores, and local JSONL
workflows remain documented in [CHALLENGE.md](CHALLENGE.md) and
[AGENT_WORKFLOW.md](AGENT_WORKFLOW.md). Do not remove private PostgreSQL volumes
when stopping services.

## Production evaluator isolation preflight

Production requires `PRODUCTION_EVALUATOR_ROOT`; the recommended value is
`/srv/mldsafail-production-evaluator`. The coordinator mounts that directory at
exactly the same absolute path inside its container, including `epoch`, `jobs`
and `secrets/signing.key`, so sibling worker bind mounts resolve on the host.
Staging remains `/srv/mldsafail-evaluator`. Before considering activation, run:

```sh
export PRODUCTION_EVALUATOR_ROOT=/srv/mldsafail-production-evaluator
python -m deploy.validate_production --staging-root /srv/mldsafail-evaluator
docker compose --env-file /PRIVATE/production.env -f compose.production.yaml config --quiet
```

The read-only validator rejects relative paths, symlink components, and roots
that overlap in either direction. Compose interpolation alone cannot establish
filesystem isolation; both checks are required. Use a fresh production env file,
fresh secrets and distinct reviewed epoch identities. Staging Compose is unchanged.

## Daily recovery cleanup and bounded local retention (inactive)

The private daily JSON has `recovery_root` (absolute, no symlink components),
`assembly`, `backup`, and optional `local_verified_sets_to_keep` (positive integer,
default **2**). `assembly` includes `env_file`, `compose`, `python`, and explicit
`material` maps for configuration/secrets/release/images. `backup` has the restic
settings above plus absolute `backup_state`, `postgres_image`, and
`coordinator_image` immutable SHA-256 identities. Keep credentials, durable release
archives and the recovery root separate. Protect configuration with mode 0600.

```sh
python -m deploy.daily_recovery --config /PRIVATE/daily-recovery.json
# After termination, timeout, restart or an incomplete cleanup:
python -m deploy.daily_recovery --cleanup --config /PRIVATE/daily-recovery.json
```

One nonblocking operation lock covers backup and cleanup. Versioned journals in
`recovery_root/journals` remain outside uploaded snapshot directories, are written
atomically with file/directory synchronization, and bind configuration contents
and Compose/env-file identities. Restore the original configuration before retrying
cleanup if its identity changed while cleanup is pending. Once cleanup is complete,
a changed configuration archives the operation journal under its run identity and
atomically initializes a new journal, under the same operation lock. Run records
and failed evidence remain intact. Cleanup retries service-state restoration and
container removal independently, checks required service health, and retains
errors for retry. Containers must match the recorded unique name, recovery label
and immutable image; a mismatch is preserved and reported as incomplete cleanup.
SIGINT/SIGTERM/SIGHUP enter the same cleanup. The inactive systemd service includes
an `ExecStopPost --cleanup` hook; startup reconciles a pending journal before new
maintenance, covering SIGKILL and host restart. Failed reconciliation prevents
new backup work and returns nonzero. Do not activate the units here.

The daily path dumps the quiescent database without creating a temporary database
on the live server. Full DB/evidence verification runs against the uploaded
snapshot in isolated disposable containers. Verification is published only after
cleanup and health checks succeed. Each run records repository, snapshot identity,
verification time and cleanup completion. After success, remove its disposable
restore directory and retain the latest two verified local sets by default.
Only validated run-owned directories beneath the recovery root are removable;
symlinks, traversal and mismatched ownership are rejected. Failed, partial,
unverified and cleanup-pending runs remain. Journals and durable release originals
remain. Pruning records deletion intent for retry after interruption. Cloud pruning
and its seven/four/six retention policy remain separate and inactive.

A free-space floor of 5 GiB stops new backup work without deleting failed evidence.
The existing monitor reports the disk floor and failed scheduled units, and accepts
only repository-bound backup verification with `cleanup_complete`. Monitoring and
external alerts still require owner activation. Native power-loss, restore,
service-health and S3 acceptance remain pending.

## Durable application release retention

Run `python -m scripts.retain_release --inventory /PRIVATE/release-inventory.json`.
The inventory contains full `source_commit`, `artifacts` mapping safe basenames to
absolute source `path` and expected `sha256`, and `roles` mapping `manifest`,
`images`, `wheel`, `checksums`, `rollback` to artifact names. The manifest must
bind the same source commit. Copy exact artifacts; do not rebuild or relabel.

The default root is `~/.local/share/mldsafail/releases`; use
`--root /srv/mldsafail/releases` for server retention. The command checks every
source and copied checksum, syncs files, atomically publishes the full-commit
private directory, and refuses conflicting artifacts. Root permissions are 0700,
published directories 0500 and artifacts 0400. Interrupted publication leaves no
partial visible release; a power loss may leave a private `.retaining-*` directory
for inspection. Keep source originals until durable verification succeeds.

The original `68946403410935379e31411d1723bdc19caa609e` application release and exact
`b4d212da3109b7716eb41553986848e377fb5b3d` rollback archives are now verified in these
full-commit directories locally. Their manifest, `images.tar`, participant wheel,
`checksums.sha256`, `rollback-metadata.json`, and `retention.json` are durable.
Use manifest image identities for future owner-gated deployment. These copies
establish local artifact retention, not native rollback acceptance or deployment
of the operational changes in the current source tree.

Retained releases can be checked after removing source originals:

```sh
python -m scripts.retain_release --verify --commit FULL_40_CHAR_SHA --root /PRIVATE/releases
```

Verification reads only the retained directory, checks its exact artifact list,
commit-bound inventory/manifest, private permissions and all artifact hashes, and
never builds, repairs or overwrites material. Repeating retention with a matching
inventory verifies the destination before inspecting any source originals.

Off-host and monitoring units use `/srv/mldsafail/current/.venv/bin/python` and
`WorkingDirectory=/srv/mldsafail/current`. Provision that installed environment
before unit validation/activation; the existing staging checkout currently has
no such host environment. Unit activation still requires manual acceptance.
