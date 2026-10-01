# Private VPS failure and rollback acceptance

This operator runner tests the existing frozen 0.5.0 staging epoch. It does not
change evaluator code, worker limits, scoring, authentication, database schema,
or private evidence. Failure submissions stay in staging history. Crash penalties
remain eligible and can appear on the leaderboard.

## Prepare the fixtures and releases

The reviewed Python-only fixtures live in `fixtures/hosted-failures`: reference
primal-LLL, malformed candidate, immediate crash, and infinite loop. Export once:

```sh
source .venv/bin/activate
python scripts/hosted_vps_failure_acceptance.py \
  --export-fixtures ../mldsafail-failure-fixtures
```

The owner publishes that standalone repository to public GitHub manually. No
agent pushes. Record `git -C ../mldsafail-failure-fixtures rev-parse HEAD`; use the
full SHA, not a branch or tag. The runner fetches this commit on the VPS and
compares every tracked file with the reviewed fixture hashes before submitting.

Retain the exact source and web/coordinator images for
`b4d212da3109b7716eb41553986848e377fb5b3d`. Record its immutable manifest **before**
replacing the current application tags. Build the new Linux amd64 web and
coordinator release with the usual source labels, leaving the worker image and
private epoch intact. From a clean source checkout, record it using
`scripts/hosted_release.py`. Deploy using the normal immutable release process.
The runner verifies image/source labels, configuration hash, worker identity,
trusted fingerprint, rootless Docker, loopback exposure, and the epoch's native
evaluator/environment compatibility. It is an acceptance runner, not an initial
deployer. Keep current staging secrets and cohort configuration for both releases.

## Run

Provide a mode-0600 file containing the saved participant bearer token, plus a
mode-0600 file containing the already revoked disposable token. The runner does
not create, revoke, or delete tokens. Supply the actual deployment checkout and
environment file paths (the defaults are only conventional paths):

```sh
python scripts/hosted_vps_failure_acceptance.py \
  --fixture-url https://github.com/OWNER/FIXTURE_REPOSITORY \
  --fixture-sha FULL_40_CHARACTER_SHA \
  --token-file /PRIVATE/participant-token \
  --revoked-token-file /PRIVATE/revoked-token \
  --ssh-identity ~/.ssh/mldsafail_vps \
  --release-manifest /PRIVATE/new-release.json \
  --rollback-manifest /PRIVATE/b4d212d-release.json \
  --deployment /ACTUAL/staging-checkout \
  --env-file /ACTUAL/private-staging.env \
  --run-id staging-failures-20261001
```

The runner announces a maintenance window on stdout and stops the normal
coordinator. There must be no unrelated queued, claimed, or running work. One
runner-owned one-shot coordinator runs at a time, cloned with the deployed image,
environment, mounts, user, network, and isolation settings. A separate idle
inspector performs read-only database and native evidence checks. No public
fault-injection endpoint is installed.

Each submission key is persisted before its API request. A lost response is
reconciled through the existing persisted idempotency record. The private VPS
journal resides in `~/.mldsafail-acceptance-RUN-ID/journal.json`, mode 0600.
Concurrent use of the same run ID is blocked with a file lock. Completed scenarios
can resume after cleanup; active interrupted scenarios must be cleaned up and
allowed to reach terminal cancellation before a fresh run is started. The same
key is never reused for a different payload.

Use the same command with `--cleanup` after a disrupted run. Normal errors and
signals invoke cleanup automatically. An independent VPS watchdog detects a
45-second missing heartbeat, disk space below 5 GiB, or available RAM below
128 MiB for 30 seconds, then attempts bounded cleanup. It restores the recorded
work-directory mode, requests cancellation of incomplete owned submissions,
removes only owned coordinators and workers proven by image and exact
submission/attempt solver mount, restores the new application release if a switch
was interrupted, and restarts the normal coordinator. It never targets a worker
by its name alone. A transient mode-0600 cleanup-token file supports cancellation
if the SSH connection dies; successful cleanup deletes that copy. The run journal
contains no bearer tokens or raw hidden evidence. Private failure details remain
in `failure.log` on the VPS.

## Gates and deadlines

- Running cancellation requires a live isolated worker, cancellation acknowledgment,
  terminal cancellation within 90 seconds, no result, and worker cleanup.
- Timeout requires an independently verified persisted real 60-second timeout,
  followed by cancellation. The entire probe is bounded by 150 seconds. This
  does **not** test full-cohort timeout scoring (about 6 hours 40 minutes).
- Malformed candidates must complete as `rejected` / `invalid_answer`, with no result.
- Immediate crashes must complete as accepted eligible penalty results. The native
  audit independently verifies all records and recomputes the equally weighted
  geometric score using frozen 60-second failed-case costs.
- Recoverable infrastructure failure removes write bits from the existing work
  directory only. Effective denial is checked under the deployed identity. Attempt
  1 must safely fail/requeue; after restoring the original mode and respecting
  backoff, attempt 2 must accept exactly one result.
- Exhaustion keeps the same fault for exactly three claims, respecting each
  persisted backoff; there must be no result or fourth attempt.
- Lease recovery kills the runner-owned coordinator during a live reference
  invocation, removes only its proven orphan worker, and waits for the actual
  lease expiry. A new attempt must record recovery and accept exactly one result.

Complete invalid/crash/reference evaluations each have a 20-minute ceiling.
Exceeding a deadline fails the gate. Limits are never shortened to make a test
pass. All scenarios check exact persisted transition chains and attempt counts,
terminal API state, logs, leaderboard membership, and cleanup. Dashboard pages,
API responses, and bounded service logs are compared with private material on the
VPS; raw evidence, nonce, and seeds are never downloaded.

After the scenarios, web and coordinator evaluation are stopped for a quiescent
PostgreSQL dump and restore verification in a disposable database. The live
application database is never restored or downgraded. Immutable user, identity,
token, and result fields are hashed locally on the VPS; token last-use timestamps
and mutable update timestamps are excluded. The runner switches only web and
coordinator images with `--no-deps`, creates the coordinator without starting
any evaluation during either switch, and checks readiness, active/revoked tokens,
leaderboard equality, data hashes, and evaluator/epoch compatibility in both
rollback and forward releases. It never invokes the migration service.

The sanitized final stdout report and private VPS `report.json` distinguish the
scenario gates and rollback from remaining off-host backup, overall migration,
and production-launch requirements. A passing run is not public-launch approval.
