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
It is not proposed 0.6.0 acceptance and does not authorize public timing use.
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
