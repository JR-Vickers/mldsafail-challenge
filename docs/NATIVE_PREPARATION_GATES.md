# Disposable native preparation gates

These commands are for the primary native operator only. Record exact source,
interpreter, database/worker image and protocol before execution; preserve failed
logs. Serial execution on an idle host is required. They do not mutate staging.

## PostgreSQL admission, idempotency and evaluation ownership

Provision an empty disposable database named `mldsafail_acceptance_UNIQUE` in a
separate PostgreSQL service, without public exposure and without staging volumes.
Give its scoped credential only to the test process. Tests refuse missing URLs,
non-PostgreSQL URLs, other database prefixes or pre-existing tables. They create
and remove only repository ORM tables in that explicitly disposable database;
this does not establish migration compatibility.

```sh
MLDSAFAIL_NATIVE_TEST_DATABASE_URL="$DISPOSABLE_DATABASE_URL" \
  python -m pytest tests/test_native_postgres_admission.py -q
```

Three gates use synchronized simultaneous connections: exactly one outstanding
submission per account with deterministic rejection; stable idempotency replay
without duplicated jobs; global queue bound across accounts; one evaluation
claim across coordinators/restart; explicit expired-lease recovery and rejection
of the old owner's heartbeat after re-claim. Record PostgreSQL version and source
identity, then verify/drop only the owned disposable database. An absent native
URL causes skips, not passes. This suite does not prove process cleanup fencing,
resource floors, production OAuth or hosted MLWE result audit; those remain their
separate native gates.

## Frozen 0.5.0 baseline production-like rehearsal

The current `compose.production.yaml` can rehearse existing **frozen 0.5.0
application baseline** behavior in a disposable environment before 0.6.0 adoption.
It is not approved-design production acceptance and does not authorize public
timing use. The approved-design rehearsal remains a distinct task, depending on
contract adoption, completed native accounting and separately versioned integration/
fresh epoch/artifacts; baseline results cannot satisfy it.
Use the protocol in [PUBLIC_LAUNCH_PACKET.md](PUBLIC_LAUNCH_PACKET.md) with retained
baseline application/worker images, fresh disposable 0.5.0 epoch/costs and
separate loopback-only proxy override. Real production credentials are unnecessary
for migration/isolation/health/backup/rollback and synthetic authentication gates.
Label these outcomes baseline-only; actual OAuth/TLS/accounting acceptance remains
pending applicable inputs and adoption. The primary operator provisions/manages
native services; engineering agents may prepare artifacts and protocol.

## Participant installation evidence

After a clean source freeze, build an owner-retained wheel into a new private
artifact directory. Compute its SHA-256, then run:

```sh
python scripts/participant_install_smoke.py --wheel "$PARTICIPANT_WHEEL" \
  --sha256 "$VERIFIED_WHEEL_SHA256" --destination "$NEW_SMOKE_DIRECTORY" \
  --approved-starter examples/mlwe/primal-lll/solver.py
```

This invokes the isolated installer, CLI help, default MLWE scaffold, approved
starter-byte equality, explicit historical scaffold and unchanged historical
small score 3901. It never logs in, submits or publishes. Partial/success logs
and `smoke.json` are retained privately; destination must be new. Installation
uses the system `python3` selected by the existing installer; record that version.
It does not promise unsupported platforms or 0.6.0 participant compatibility.
Reproduction worker builds use `scripts/mlwe_reproduce.py` with two exact clean
build identities and the reviewed frozen image, comparing public generated
fixtures/normalized outputs and dependency artifacts. That CPU-heavy native gate
belongs to the primary operator's serialized schedule; existing evidence remains
historical unless source and image identities match.

## Monitoring synthetic native fault runner

```sh
python -m scripts.monitoring_fault_acceptance --destination "$NEW_PRIVATE_MONITOR_EVIDENCE"
```

Run on the primary operator's idle Linux host. The runner reads actual resource
floors, injects only synthetic readiness/service/lease/backup/job inputs, and
exercises real loopback HTTP retries, deduplication, immediate recovery and fixed
payload privacy. It changes no services/leases and sends no external alerts.
This establishes native tooling behavior only; installed-unit wiring, actual
scheduled-job collection, off-host backup freshness and approved external receiver
delivery remain separate acceptance gates.

## Executable frozen 0.5.0 disposable orchestrator

`python -m scripts.baseline_production_rehearsal --config PRIVATE_CONFIG.json`
is reserved for the primary native operator. Required JSON keys are:
`run_directory` (new private root disjoint from staging), `operator_source`
(retained compatible source), `source_manifest` (full commit and source-file hashes), `release_manifest` and
`rollback_manifest` (retained source/image/worker-lock/fingerprint inventory), `python` (installed 3.12.10), `docker_socket`
(explicit rootless `/run/user/UID/docker.sock`), `fixture_repository`,
`fixture_commit`, `fixture_solver_path`, and `images`. The latter maps `web`,
`coordinator`, `worker`, `postgres`, `caddy`, `rollback_web`,
`rollback_coordinator` to exact locally retained `sha256:` image IDs. Optional
`staging_root` defaults to the frozen staging evaluator root. Use the existing
reviewed public tiny-instance fixture commit; never arbitrary cryptographic targets.

The orchestrator records protocol/source/images before execution, generates a
fresh private synthetic 0.5.0 epoch without changing the frozen generator/scoring,
uses unique owned database volumes and synthetic credentials, exposes web only
on an ephemeral loopback port, explicitly migrates the fresh DB, creates a local
expiring test token, evaluates the approved fixture under the 20-minute ceiling,
independently audits result/evidence and leaderboard, restores the quiescent
snapshot in a disposable DB, then rolls only application images back/forward
without migrate dependencies. It verifies preserved schema/stable DB contents,
sealed epoch receipt, worker ID, leaderboard and credential usability. Mutable
rate-limit/token-last-use/audit rows are omitted from the switch DB hash; the same
token must still authenticate, and those tables' schema remains in the hash.

Native epoch setup has a predeclared 90-minute overall setup ceiling; the frozen
60-second per-invocation and 20-minute hosted complete-evaluation ceilings remain.
A failed fresh epoch is preserved, never replaced until a passing seed sample is
found. Logs/manifests/dumps remain private in the run directory. No proxy/TLS/real
OAuth/off-host backup or 0.6.0 acceptance is claimed. Caddy ID is required only to
parse the production template; its service is excluded from disposable startup.

A trusted external Docker CLI shim labels every epoch/hosted worker for owned
cleanup without modifying frozen source, data or score. Epoch generation runs in
the exact retained coordinator image. Cleanup stops dispatch controllers before
worker removal, rescans for racing creation, and removes only labeled owned
containers/volumes/networks. Failed-run database volumes are retained and explicitly
accounted as private failure evidence, with all dispatch/application containers
stopped/removed; they are not silently discarded by cleanup. No live/staging database is restored. Repeated cleanup uses
`--cleanup` with the same private config; incomplete cleanup remains fenced and
must be repaired before conflicting host work. An exclusive run lock prevents concurrent cleanup, final ownership inventory
proves no live owned resource remains (apart from accounted retained failure
volumes), and overall completion requires successful cleanup. Image source labels
and compatibility identities are checked against retained baseline/b4d212d
manifest inventories before epoch setup. Primary operator must independently
review and native-verify this new orchestration before treating its result as a gate.

The baseline runner rejects overlap with `/srv/mldsafail` and `/etc/mldsafail`
as well as the configured staging evaluator root. Supply additional absolute
`protected_roots` for any host-specific deployment, secret or evidence locations.
Database readiness has a 120-second overall deadline and at most ten seconds per
Docker invocation; failed and timed-out attempts are durably recorded.

Independent baseline cleanup needs only `run_directory` and `docker_socket` in
its private configuration: private durable journal UID/socket/run identity is
authority under the same exclusive run lock. Missing or damaged optional source
and release manifests are recorded and do not block cleanup. Never edit ownership
fields to force cleanup; an invalid ownership journal requires operator review.

For public frozen-worker reproducibility use the exact clean source's
`scripts/mlwe_reproduce.py` with three immutable amd64 image IDs, a new private
`--output` root, and explicit current-user rootless `DOCKER_HOST`. Its protocol
remains all twelve public profile/eta/seed fixtures, each of three solvers, across
both clean builds and the historical frozen worker; normalized outputs and
artifact inventories must match. Each invocation durably records labeled/named
creation intent before creating a container, retains request and partial output,
and uses a 65-second limit. Timeout/SIGKILL leaves a retryable ownership journal.
Run `python -m scripts.mlwe_reproduce --output OWNED_ROOT --cleanup` under the same
socket environment to reconcile owned resources without source/release manifests.
A result passes only with matching outputs/artifacts **and** journal cleanup
complete with zero remaining owned containers. Native execution remains pending;
this runner cannot establish public-safe accounting or approved 0.6.0 adoption.
