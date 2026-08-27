# Hosted operations

The production target is one Linux VPS, but the web/API, database, evaluator
coordinator, and disposable worker remain separate services. Only Caddy binds
public ports. The web image has no Docker socket; only the coordinator can ask
the host's rootless Docker daemon to start a worker.

## First deployment

### Prerequisites

- Docker Engine (Docker Desktop on macOS, or Docker Engine on Linux)
- docker compose v2
- A GitHub OAuth application (for production) or local dev mode (for development)

### Local development (macOS / Linux)

The `make hosted-dev` target builds and starts the full stack on `http://localhost:8080`:

```sh
cd mldsafail-challenge
make hosted-dev
```

This starts: PostgreSQL, web dashboard, Caddy proxy, and the coordinator.
The coordinator requires the Docker socket to spawn ephemeral worker containers.

For local development, a `dev.env` file is provided at `deploy/dev.env` with
obviously synthetic credentials and a development hidden-seeds fixture.

**macOS note:** Docker Desktop must be running. The coordinator runs as uid 1000
inside its container and needs access to the Docker socket. On macOS, the Docker
Desktop socket (`~/.docker/run/docker.sock`) is symlinked to `/var/run/docker.sock`.
The coordinator Dockerfile places the `mldsafail` user in the `root` group, and
compose.yaml uses `group_add: ["0"]` so the coordinator can access the socket.

### Step-by-step local deployment

1. **Start Docker Desktop** (macOS) or ensure Docker Engine is running (Linux).

2. **Prepare hidden seeds directory:**
   ```sh
   mkdir -p /Users/jarrett/dev/mldsafail-evaluator/secrets
   cp deploy/dev-hidden-seeds.json \
      /Users/jarrett/dev/mldsafail-evaluator/secrets/hidden-seeds.json
   chmod 0400 /Users/jarrett/dev/mldsafail-evaluator/secrets/hidden-seeds.json
   ```

   For production, replace `dev-hidden-seeds.json` with a securely generated
   hidden seeds file (see "Generating hidden seeds" below).

3. **Build and start all services:**
   Build the 0.4.0 images first (one-time, or after any source or Compose change):
   ```sh
   docker compose --env-file deploy/dev.env --profile build build
   ```
   Then start the stack:
   ```sh
   cd mldsafail-challenge
   docker compose --env-file deploy/dev.env up -d db web proxy coordinator
   ```

4. **Verify services are healthy and the public demo is serving:**
   ```sh
   curl -s http://localhost:8080/health/live   # {"status":"ok"}
   curl -s http://localhost:8080/health/ready  # {"status":"ready"}
   docker compose --env-file deploy/dev.env ps
   ```
   Then confirm the dashboard renders the public-suite baseline, best-known valid
   solution, and history. For the 0.4.0 dev stack, the fresh Postgres database is
   empty, so the web process falls back to `results/experiments.jsonl` and serves
   the same public-suite records you see with `make web`:
   ```sh
   # Homepage: leaderboard, current score, progress chart, frontier, recent records.
   curl -s http://localhost:8080/ | grep -E '(leaderboard|Headline score|Progress|frontier|experiment-row)'

   # Experiment detail for any ID surfaced on the homepage.
   EXPERIMENT_ID=$(curl -s http://localhost:8080/ \
     | grep -oE 'href="/experiment/[^"]+"' | head -1 | sed 's#href="/experiment/##' | sed 's#"##')
   curl -s "http://localhost:8080/experiment/$EXPERIMENT_ID" | grep -E '(metric-card|provenance|Metadata|Audit)'

   # Static pages render correctly.
   curl -s http://localhost:8080/about | grep -E '<h1>'
   curl -s http://localhost:8080/methodology | grep -E '<h1>'
   ```

5. **Sign in (dev mode):**
   The dev environment uses a synthetic login endpoint. Open `http://localhost:8080/auth/dev-login`
   in your browser, or use the API:
   ```sh
   # The dev-login creates a browser session; then create an API token via the web UI
   # at http://localhost:8080/tokens or via the API with a session cookie.
   ```

6. **Submit a test solver:**
   See "Testing the submission pipeline" below.

### Build images

All three images are built from the project root:

```sh
# Web dashboard (Flask + Gunicorn)
docker build --no-cache -f Dockerfile -t mldsafail-web:0.4.0 .

# Coordinator (has Docker socket access, runs migrations)
docker build --no-cache -f Dockerfile.coordinator -t mldsafail-coordinator:0.4.0 .

# Worker (disposable, non-root, no Docker socket)
docker build --no-cache -f Dockerfile.worker -t mldsafail-worker:0.4.0 .
```

Or use docker compose's profile-aware build:

```sh
docker compose --env-file deploy/dev.env --profile build build
```

### Configuration reference (dev.env)

| Variable | Dev value | Production value |
|----------|-----------|-------------------|
| `POSTGRES_PASSWORD` | `local-development-password` | Strong random password |
| `MLDSAFAIL_SECRET_KEY` | `local-compose-development-only` | 32+ random bytes |
| `MLDSAFAIL_ENV` | `local` | `production` |
| `MLDSAFAIL_DOMAIN` | `http://localhost` | Actual domain |
| `MLDSAFAIL_EVALUATOR_FINGERPRINT` | `development` | SHA-256 of reviewed release |
| `MLDSAFAIL_HIDDEN_SUITE_VERSION` | `development-public-fixture` | Version identifier |
| `EVALUATOR_WORK_DIR` | `/Users/jarrett/dev/mldsafail-evaluator` | `/srv/mldsafail-evaluator` |
| `EVALUATOR_UID/GID` | `1000` | Match evaluator account |
| `DOCKER_SOCKET` | `/var/run/docker.sock` (mounted directly) | Rootless Docker socket path |
| `GITHUB_CLIENT_ID/SECRET` | (empty, dev auth used) | GitHub OAuth app credentials |

## Generating hidden seeds

Hidden seeds are the secret evaluation suite that participants never see. They
must be:

- **Deterministically derived** from the public seeds using a known derivation
  function (so the maintainer can regenerate them from scratch if needed).
- **Kept out of the public repository** (file mode 0400, not committed to git).
- **Versioned** so rotations are traceable in the experiment log.

### Generation procedure

The hidden seeds are generated by applying a deterministic derivation to the
public seeds. The derivation function is:

```python
import hmac
import hashlib
import json

derivation_key = b"mldsafail-hidden-suite-derivation-v1"

public_seeds = {
    "small": [1101, 1102, 1103],
    "medium": [2201, 2202, 2203],
    "large": [3301, 3302, 3303],
}

hidden_seeds = {}
for profile, seeds in public_seeds.items():
    derived = []
    offset = {"small": 10000, "medium": 20000, "large": 30000}[profile]
    for seed in seeds:
        h = hmac.new(derivation_key, str(seed).encode(), hashlib.sha256).digest()
        value = int.from_bytes(h[:8], 'big')
        hidden_seed = offset + (value % 9000)
        derived.append(hidden_seed)
    hidden_seeds[profile] = derived

# Write to the hidden seeds file (mode 0400)
with open("/path/to/hidden-seeds.json", "w") as f:
    json.dump(hidden_seeds, f, indent=2)
    f.write("\n")
```

**Important:** The derivation key and algorithm above are for the dev fixture.
For production, use a different derivation key (stored separately from the repo)
and a different seed range. The actual seeds must never be committed to the
public repository.

### Rotating hidden seeds

1. Generate a new hidden seeds file with a new `MLDSAFAIL_HIDDEN_SUITE_VERSION`.
2. Stop the coordinator (`docker compose stop coordinator`).
3. Replace the hidden seeds file at `EVALUATOR_WORK_DIR/secrets/hidden-seeds.json`.
4. Update `MLDSAFAIL_HIDDEN_SUITE_VERSION` in the environment.
5. Start the coordinator.
6. Old results remain in their original cohort; new submissions use the new suite.

## Configuring GitHub OAuth (production)

1. Go to GitHub → Settings → Developer settings → OAuth Apps → New OAuth App.
2. Set the authorization callback URL to `https://YOUR_DOMAIN/auth/callback`.
3. Copy the Client ID and Client Secret.
4. Add them to the production `.env` file:
   ```
   GITHUB_CLIENT_ID=your_client_id
   GITHUB_CLIENT_SECRET=your_client_secret
   ```

For local development, OAuth is not required — use the `/auth/dev-login` endpoint
instead (only available when `MLDSAFAIL_ENV` is `local` or `test` and
`ALLOW_DEV_AUTH` is enabled).

## Database migrations

The web and coordinator containers run Alembic migrations on startup. The
`start-web.sh` and `start-coordinator.sh` entrypoint scripts run
`alembic upgrade head` before starting the application.

To run migrations manually:

```sh
docker compose --env-file deploy/dev.env exec web alembic upgrade head
docker compose --env-file deploy/dev.env exec coordinator alembic upgrade head
```

To check migration status:

```sh
docker compose --env-file deploy/dev.env exec web alembic current
```

## Testing the submission pipeline

### Create a test solver repository

```sh
mkdir -p /tmp/test-solver/src/mldsafail/solver
mkdir -p /tmp/test-solver/src/mldsafail/math

# Create a minimal solver that uses the lattice solver (candidate_b)
cat > /tmp/test-solver/src/mldsafail/solver/__init__.py << 'EOF'
"""Trivial solver for testing hosted evaluation."""
from mldsafail.solver.candidate_b import solve as lattice_solve

def solve(instance, meter):
    return lattice_solve(instance, meter)
EOF

# Create empty math package
cat > /tmp/test-solver/src/mldsafail/math/__init__.py << 'EOF'
# Math primitives package
EOF

# Create a bare git repo for the coordinator to clone
git init --bare /tmp/test-solver-bare.git
cd /tmp/test-solver
git init
git config user.name "Test"
git config user.email "test@test.com"
git add .
git commit -m "test: minimal solver"
git remote add origin /tmp/test-solver-bare.git
git push origin main
```

### Submit via the API

```sh
# First, get an API token by signing in and creating one at /tokens
# For dev mode, use the web UI at http://localhost:8080/tokens

# Then submit:
curl -X POST http://localhost:8080/api/v1/submissions \
  -H "Authorization: Bearer mldsa_PREFIX_SECRET" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: unique-key-123" \
  -d '{
    "repository_url": "file:///tmp/test-solver-bare.git",
    "commit_sha": "FULL_40_CHAR_SHA",
    "hypothesis": "Test submission",
    "notes": "End-to-end test",
    "tags": ["test"],
    "benchmark_version": "0.4.0"
  }'
```

For production, use a GitHub HTTPS URL instead of `file://`.

### Monitor submission status

```sh
curl http://localhost:8080/api/v1/submissions/SUBMISSION_ID \
  -H "Authorization: Bearer mldsa_PREFIX_SECRET"

curl http://localhost:8080/api/v1/submissions/SUBMISSION_ID/logs \
  -H "Authorization: Bearer mldsa_PREFIX_SECRET"
```

States: `queued` → `validating` → `running` → `accepted` (or `rejected`).

### Check the leaderboard

```sh
curl http://localhost:8080/
curl http://localhost:8080/experiment/RESULT_ID
```

## Monitoring the stack

### Service health

```sh
curl http://localhost:8080/health/live   # Process alive
curl http://localhost:8080/health/ready  # DB connected
docker compose --env-file deploy/dev.env ps
docker compose --env-file deploy/dev.env logs --tail 50
```

### Coordinator status

```sh
docker compose --env-file deploy/dev.env logs coordinator
# Check for: job claims, worker launches, result acceptance/rejection
```

### Database queries

```sh
docker compose --env-file deploy/dev.env exec db \
  psql -U mldsafail -d mldsafail -c "SELECT * FROM submissions ORDER BY created_at DESC LIMIT 5;"
docker compose --env-file deploy/dev.env exec db \
  psql -U mldsafail -d mldsafail -c "SELECT * FROM experiment_results ORDER BY accepted_at DESC LIMIT 5;"
```

## Isolation verification

The worker container runs with strict isolation constraints. Verify with:

```sh
docker compose --env-file deploy/dev.env exec coordinator python -c "
from pathlib import Path
from mldsafail.evaluator.docker import docker_command, WorkerLimits

harness = Path('/tmp/test-harness')
harness.mkdir(exist_ok=True)
metadata = {
    'MLDSAFAIL_SOURCE_DIGEST': 'a' * 64,
    'MLDSAFAIL_BENCHMARK_VERSION': '0.4.0',
    'MLDSAFAIL_EVALUATOR_FINGERPRINT': 'development',
    'MLDSAFAIL_HIDDEN_SUITE_VERSION': 'dev',
    'MLDSAFAIL_WORKER_CLASS': 'rootless-docker-v1',
}
cmd = docker_command('mldsafail-worker:0.4.0', harness, metadata, WorkerLimits())
print(' '.join(cmd))
"
```

This generates the exact `docker run` command the coordinator uses. Verify it
contains all required isolation flags and none of the prohibited ones:

**Required (isolation):**
- `--network=none` — no network access
- `--read-only` — root filesystem read-only
- `--user=65532:65532` — non-root user
- `--cap-drop=ALL` — all capabilities dropped
- `--security-opt=no-new-privileges` — no privilege escalation
- `--pids-limit=64` — PID limit
- `--ulimit=fsize=67108864:67108864` — file size limit (64 MiB)
- `--tmpfs /tmp:rw,...,size=64m` — ephemeral tmpfs only
- `--mount ... readonly` — challenge mount read-only
- `--stop-timeout=5` — quick container stop

**Prohibited (must be absent):**
- No `-v /var/run/docker.sock` — worker cannot access Docker
- No `DATABASE_URL` in environment — worker cannot access database
- No `MLDSAFAIL_HIDDEN_SEEDS_PATH` in environment — worker cannot access seeds
- No signing key in environment — only passed via stdin to worker.py
- No `--privileged` flag

## Rollback

1. **Stop submission intake:** Set the web service to not accept new submissions
   (or pause the coordinator).
2. **Stop the coordinator:** `docker compose stop coordinator`.
3. **Restore previous application images:** Re-tag or rebuild the previous
   image versions and update compose.yaml.
4. **Restore database from backup** (if migration was problematic):
   ```sh
   docker compose --env-file deploy/dev.env exec -T db \
     psql -U mldsafail -d mldsafail < backup.dump
   ```
5. **Downgrade migrations** (only if the reviewed migration supports safe rollback):
   ```sh
   docker compose --env-file deploy/dev.env exec web alembic downgrade -1
   ```
6. **Restart services:** `docker compose up -d db web coordinator proxy`.

**Important:** Never downgrade after new-version writes if that would discard
data. Restore the pre-migration backup instead.

## Backup and restore drill

Create encrypted, off-host backups:

```sh
docker compose --env-file deploy/dev.env exec -T db \
  pg_dump -U mldsafail -Fc mldsafail > mldsafail-$(date +%F).dump
```

Restore:

```sh
docker compose --env-file deploy/dev.env exec -T db \
  pg_restore -U mldsafail --clean --if-exists -d mldsafail < backup.dump
```

Database backups never include hidden seeds; back up the hidden seeds file
independently with access auditing.

## Incident response

- **OAuth or Flask secret compromise:** Stop web, rotate the secret, revoke the
  GitHub OAuth credential, and revoke all browser sessions.
- **API-token exposure:** Set `revoked_at`, record an audit event, notify the
  owner, and inspect submission/audit history.
- **Submission revocation:** Cancel queued jobs; request cancellation for running
  jobs. Retain accepted-result and audit history.
- **Hidden-suite exposure:** Stop the coordinator, generate a fresh bounded suite,
  update the version, rotate the file, rebuild the evaluator cohort baseline.
- **Worker/kernel concern:** Stop the coordinator immediately, replace the host or
  worker environment, rotate hidden data, database credentials, and evaluator
  metadata, then audit attempts.

## Teardown

```sh
docker compose --env-file deploy/dev.env down
# To also remove volumes (WARNING: destroys database data):
docker compose --env-file deploy/dev.env down --volumes
```
