# Private staging acceptance checkpoint — 2026-10-01

The deployed immutable application release is
`b2eb806cc7900811272afbc67cb9528283c9a636`. This document is a subsequent
documentation checkpoint, not a replacement application release. No commits
were pushed by the deployment agent. Full migration acceptance remains open.

## Completed

- Latest application `make check`: 273 passed, 8 Docker tests skipped. The
  historical 0.4.0 small score remains 3901. Real Docker tests and clean-build
  reproducibility were separately verified during release preparation.
- Ubuntu security updates, dedicated deployment and maintenance users,
  verified non-root SSH, disabled root/password SSH, maintainer-IP-only UFW,
  rootless Docker, disabled root Docker services, 2 GiB swap, restricted
  deployment directories, monitoring and bounded logging.
- Pinned Linux amd64 worker and application images; release manifests record
  source, locks, trusted code, configuration and image identities.
- One fresh native private epoch passed viability and sealing. Secret material
  was generated on the VPS, protected and never downloaded or committed.
- Native valid/invalid/crash/timeout/memory/output worker probes passed.
- PostgreSQL migrations applied; a second upgrade was a no-op. Backup and
  restore were demonstrated with a synthetic audit record. Daily local backups
  are enabled and their service was successfully exercised.
- Real staging GitHub OAuth created a browser session. Development login is
  disabled, unauthenticated API access returns 401, live/readiness return 200.
- A participant-created, expiring API token authenticated through the CLI;
  credentials were stored in the operating-system credential store without
  displaying their value.
- CLI submission `34b0829d-0b76-4aab-b500-9aab9c7f508a` acquired exactly
  `c2ca852728a6dbec4cee6fde6d8ffb4f1156e3e0` from the public repository,
  selecting `examples/mlwe/primal-lll` through sparse immutable acquisition.
- A live contestant worker was inspected: network disabled, read-only root,
  UID 65534, all capabilities dropped, no-new-privileges, one CPU, 2 GiB,
  64 processes, only a read-only solver mount, no hidden material, database
  credentials or Docker socket.
- The submission completed 400 invocations and all 100 cases succeeded. The
  coordinator independently verified and accepted it. A separate native
  evidence audit recomputed the same persisted CPU-ratio score:
  `1.0104512307931532`. It appears as rank 1 in the 0.5.0 cohort; this is a
  staging acceptance result, not evidence of an algorithmic improvement.
- Result version, evaluator fingerprint, hidden-suite version, worker class,
  epoch identity, native score and whitelisted diagnostics were checked.
- API leaderboard, public dashboard/detail pages and service logs were checked
  against the actual private nonce/seeds on the VPS: no nonce, seeds or
  evaluator filesystem paths appeared. Raw evidence stayed on the VPS.
- Duplicate CLI submission requests reused the same job. Incompatible version,
  epoch and worker identities were rejected with 422. Queued cancellation
  succeeded. A missing-solver submission was rejected by the coordinator.
- The host remained stable during sequential evaluation. The proxy publishes
  only `127.0.0.1:8080`; PostgreSQL and Docker remain private. OAuth callback
  query strings are excluded from web access logs.

## Remaining gates

- Verify participant API-token revocation using a separate disposable token.
- Complete integrated running-cancellation, infrastructure retry and worker
  failure-state checks through the deployed submission path. Local hosted
  tests and native worker probes cover these components but are not the full
  deployed-path gate.
- Demonstrate application rollback to a previous healthy immutable release.
  Older source/image artifacts are retained; retention alone is not a rollback
  demonstration.
- Configure and verify automated off-host/provider backups. Local daily
  PostgreSQL dumps do not satisfy this requirement.
- Finish and record the full VPS acceptance decision before claiming the
  migration complete.

## Access and production boundary

Use the deployment user, because direct root SSH is disabled:

```sh
ssh -i ~/.ssh/mldsafail_vps \
  -L 8080:127.0.0.1:8080 \
  mldsafail@178.128.17.58
```

Staging OAuth callback: `http://localhost:8080/auth/callback`.
The external firewall does not expose staging, HTTP or HTTPS. Production still
requires DNS, HTTPS, production OAuth, secure cookies, fresh production secrets
and a distinct hidden-suite version and private epoch. Do not reuse staging
evidence in production.
