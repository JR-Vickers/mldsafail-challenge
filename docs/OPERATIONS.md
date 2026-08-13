# Hosted operations

The production target is one Linux VPS, but the web/API, database, evaluator
coordinator, and disposable worker remain separate services. Only Caddy binds
public ports. The web image has no Docker socket; only the coordinator can ask
the host's rootless Docker daemon to start a worker.

## First deployment

1. Install Docker Engine in rootless mode for a dedicated evaluator account and
   Docker Compose v2. Do not expose its socket over TCP.
2. Copy `deploy/.env.example` to a host-only `.env`, replace every placeholder,
   and set it to mode `0600`. Set `DOCKER_SOCKET` and `DOCKER_GID` to that
   account's rootless socket and group.
3. Register a GitHub OAuth app. Its callback is
   `https://YOUR_DOMAIN/auth/callback`. GitHub supplies the client ID and secret.
4. Create the absolute host directory named by `EVALUATOR_WORK_DIR`, owned by
   the rootless evaluator account configured by `EVALUATOR_UID` and
   `EVALUATOR_GID`, with mode `0700`. Place a bounded profile-to-seed-list
   document at `$EVALUATOR_WORK_DIR/secrets/hidden-seeds.json`, mode `0400`.
   The shared root uses the identical absolute host/container path because the
   host Docker daemon must resolve assembled-harness bind mounts. Hidden seeds
   themselves are read only by the coordinator: workers receive generated
   public challenge matrices over stdin, never seed files. Give each rotation a
   new `MLDSAFAIL_HIDDEN_SUITE_VERSION`.
5. Compute and review the evaluator fingerprint for the exact release. Build
   immutable images and record their digests:

   ```sh
   docker compose --env-file .env --profile build build --pull
   docker image inspect mldsafail-worker:0.3.0 --format '{{.Id}}'
   docker compose --env-file .env up -d db web proxy coordinator
   curl -fsS https://YOUR_DOMAIN/health/ready
   ```

Caddy obtains and renews TLS certificates automatically for a public DNS name.
Keep ports other than 80/443 firewalled. `/health/live` checks the process;
`/health/ready` checks PostgreSQL. Scrape `/metrics` on a private network or
restrict it at the proxy before exposing the service publicly.

The web entrypoint runs `alembic upgrade head` before Gunicorn. For controlled
rollouts, run the migration as a separate release step and deploy web only after
it succeeds. Bootstrap an administrator by stable numeric GitHub ID:

```sh
docker compose --env-file .env exec web \
  mldsafail-admin bootstrap-admin --github-subject 123456 --login owner
```

## Development stack

`make hosted-dev` builds and starts PostgreSQL, the web/API, and HTTP Caddy at
`http://localhost:8080`. It uses an obviously synthetic public development
suite and exposes a “Development sign in” action instead of GitHub OAuth. The
fake identity route returns 404 unless `MLDSAFAIL_ENV` is `local` or `test` and
`ALLOW_DEV_AUTH` is enabled. Start the coordinator separately only on a Linux
host with the rootless socket configured. Run `make hosted-down` to stop it.

## Migrations and rollback

Before every migration, take a database backup. Alembic migrations are
forward/backward scripts:

```sh
docker compose --env-file .env exec web alembic current
docker compose --env-file .env exec web alembic upgrade head
docker compose --env-file .env exec web alembic downgrade -1
```

Rollback means: stop submission intake, stop the coordinator, restore the
previous application images, and downgrade only when the reviewed migration
declares that safe. Never downgrade after new-version writes if that would
discard data; restore the pre-migration backup instead.

## Backup and restore drill

Create encrypted, off-host backups and test them regularly:

```sh
docker compose --env-file .env exec -T db \
  pg_dump -U mldsafail -Fc mldsafail > mldsafail-$(date +%F).dump
docker compose --env-file .env exec -T db \
  pg_restore -U mldsafail --clean --if-exists -d mldsafail < backup.dump
```

For a drill, restore into a disposable database, run Alembic to head, compare
row counts for users, submissions, attempts, results, and audit events, then
load the leaderboard and a private submission detail. Database backups never
include hidden seeds; back up that secret independently with access auditing.

## Rotation and incident response

- OAuth or Flask secret compromise: stop web, rotate the secret, revoke the
  GitHub OAuth credential, and revoke all browser sessions. Rotating the Flask
  key also invalidates signed cookies.
- API-token exposure: set `revoked_at`, record an audit event, notify the owner,
  and inspect submission/audit history. Tokens never belong in URLs or logs.
- Submission revocation: cancel queued jobs; request cancellation for running
  jobs. Retain accepted-result and audit history rather than deleting it ad hoc.
- Hidden-suite exposure: stop the coordinator, generate a fresh bounded suite,
  update the version, rotate the file, rebuild the evaluator cohort baseline,
  and keep old results in their old cohort.
- Worker/kernel concern: stop the coordinator immediately, replace the host or
  worker environment, rotate hidden data, database credentials, and evaluator
  metadata, then audit attempts. Containers are not VM-grade isolation.

Monitor request/authentication failures, queue depth, job latency, worker
failures, and accepted/rejected/infrastructure-failed counts. Logs are JSON,
bounded, sanitized, and must be shipped without request authorization headers.
