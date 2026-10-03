# Private hosted MLWE 0.5.0 deployment

This deployment keeps the historical 0.4.0 integer benchmark and trusted source
fingerprint unchanged. MLWE results use a separate native floating-point score
column and immutable epoch identity. Cohorts include benchmark version,
evaluator fingerprint, hidden-suite version, worker class and epoch. The API
leaderboard uses the frozen MLWE anchored 1% tie rule.

Participant package 0.5.1 defaults clone and submissions to benchmark 0.5.0;
`--benchmark-version 0.5.0` can make that choice explicit. Historical `run`
remains benchmark 0.4.0. Select an approved Python
directory with `--solver-path`; it must contain `solver.py` and satisfy the
frozen local contestant contract. The default is `src/mldsafail/solver`.
For a reference acceptance submission from an existing published commit, use
`--solver-path examples/mlwe/primal-lll`. An optional `--epoch-id` requires the
specified cohort. The evaluator checks the requested full Git commit and
snapshots only that directory. No repository installation scripts run.
MLWE acquisition uses a partial Git fetch and sparse checkout at the requested
commit, retaining the repository and source size caps while excluding unrelated
research data. The historical acquisition path remains available for 0.4.0.

The coordinator audits a completed immutable epoch before startup, checks the
actual Docker environment before each submission, independently verifies all
worker candidates, seals and re-audits private evidence, and publishes only the
contract's whitelist summary. Invalid answers reject the submission. Complete
timeouts, crashes and no-answer runs retain the frozen case penalties. Lost
leases and infrastructure failures retry with separate private attempt
directories. Cancellation is checked between executions, each bounded by the
frozen 60-second deadline. Partial evidence is never rankable.

## Architecture lock and local acceptance

The original local ARM64 worker and benchmark package are unchanged.
`python -m mldsafail.evaluator.build_mlwe --no-cache` builds a distinct
`linux/amd64` image with `deploy/worker-linux-amd64.requirements.txt`.
The Python base-image digest and native library versions are the frozen values.
The architecture-specific release label binds platform, trusted code, worker
lock and Dockerfile. The epoch environment additionally binds interpreter,
wheel/native artifacts, image identity and the actual Docker host.

The new CPython 3.12 wheel hashes were checked against publisher metadata:
[fpylll 0.6.4](https://pypi.org/pypi/fpylll/0.6.4/json) and
[cysignals 1.12.5](https://pypi.org/pypi/cysignals/1.12.5/json).
Hash-enforced installation succeeded in two clean x86_64 builds. Both builds
matched dependency artifacts and all 36 normalized public solver cases against
the reviewed primitive-study worker. Both ARM64 clean builds passed the same
comparison. Eight Docker isolation/failure tests passed on each architecture;
the x86_64 local checks ran under emulation and do not establish native timing.
Only a new epoch on the native VPS can establish its reference costs.

## VPS access and private deployment

Ubuntu 24.04 x86_64 at `178.128.17.58` has two separate SSH accounts:

- `mldsafail`: owns the release, evaluator directories and rootless Docker;
  no sudo or root-owned Docker-socket access.
- `mldsafail-admin`: maintainer sudo access for host administration.

Both accounts were tested before disabling password authentication,
keyboard-interactive authentication and root SSH. SSH is allowed only from
the maintainer connection's source address. Change that UFW rule through
maintenance access or the provider console if the maintainer address changes.
HTTP and HTTPS stay closed. The staging tunnel is now:

```sh
ssh -i ~/.ssh/mldsafail_vps -L 8080:127.0.0.1:8080 mldsafail@178.128.17.58
```

The host has 2 GiB swap, automatic security updates without automatic reboot,
bounded system journals, a five-minute disk/service check, and restricted
deployment/evaluator directories. Docker Engine 29.8.1 runs rootless under the
deployment user; the root-owned daemon/socket are disabled. Provisioning follows
[Docker's Ubuntu installation instructions](https://docs.docker.com/engine/install/ubuntu/)
and [rootless installation instructions](https://docs.docker.com/engine/security/rootless/).

Use standalone `compose.private.yaml`, not the development Compose files.
Supply immutable service/worker image identities and generated secrets from a
mode-0600 environment file outside the release checkout. The proxy publishes
only `127.0.0.1:8080`. A single migration service must complete before web and
coordinator start; neither application process runs migrations again. All
container logs rotate after 10 MiB with three retained files.
The deployment user's daily PostgreSQL backup timer uses private mode-0600
dumps. Off-host provider backups are a separate requirement.

`MLDSAFAIL_ENV=private-staging` requires real GitHub OAuth credentials and
disables development authentication. It uses HTTP-only, SameSite=Lax session
cookies over the SSH tunnel; normal staging/production retain secure cookies.
The staging OAuth callback is **http://localhost:8080/auth/callback**.

Record the clean source/image/config identities before deployment:

```sh
python scripts/hosted_release.py --output /outside/repository/release.json
```

Do not upload the old development epoch. Create exactly one fresh private
epoch on the native rootless Docker host; failed viability gates preserve
evidence and require an explicit operator decision. Do not automatically
select replacement seeds. Production needs its own new epoch and secrets.

## Outstanding acceptance

Local checks do not establish deployment completion. See
[the private staging acceptance checkpoint](PRIVATE_STAGING_STATUS.md) for the
native VPS gates completed on 2026-10-01 and the remaining gates. Provider
access is required to enable automated off-host VPS backups; local disk copies
alone do not satisfy that requirement. No public submission endpoint may be
enabled before domain/HTTPS and production OAuth are configured.
