# Integrated workload local verification — 2026-10-21

Scope: repository implementation and disposable local fixtures. No VPS connection,
installation, native acceptance, cryptanalytic evaluation, epoch or capacity
measurement was performed. The 0.5.0 preview, existing VPS and $0 budget remain.
Historical receipts are unchanged. This record supplies no execution authority.

## Completed checks

- `make check`: 1,471 passed, 45 skipped, 12 existing fork/deprecation warnings;
  separate frozen 0.5.0 contract check: 8 passed.
- Focused native-runtime, administrative dispatch, policy, deployment, router,
  socket and service tests passed. Fake cgroup/proc fixtures exercise protection
  logic; signed synthetic controller results exercise transaction routing.
- Disposable PostgreSQL 17.5 loopback fixture: 46 tests passed across native
  admission, protected dispatcher, maintenance fence and private SQL transport.
  Tests include atomic admission/rate/queue limits, deferral without attempts,
  cancellation, lease/commit ambiguity, matching committed results and no-score
  orphan recovery. Container and tmpfs data were removed; absence verified.
- Disposable local Linux control fixture passed UID peer rejection, slow clients,
  cross-database/admin contention, supervisor SIGKILL with a surviving worker,
  independent process cleanup, durable pause, kernel file write cap and bounded
  tmpfs exhaustion. Only selected control sources were mounted read-only; no
  database credentials or private benchmark data were supplied. Container used
  `--rm`, no network, 128 MiB, one CPU and 64 PIDs.
- Changed local documentation links and `git diff --check` were checked before
  packet publication. Frozen benchmark execution bytes were not edited.

The first full-suite run encountered a five-second timeout in the preexisting
recovery SIGHUP/upload subprocess test (1,470 passed). Its entire operational
readiness module passed on rerun; the subsequent full `make check` passed. No
production code or timeout was changed to hide that failure.

Local fixture image identities (already cached; no pull or provisioning):

- Python/Linux ARM64: `sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db`.
- PostgreSQL: `sha256:fbcea1bd13b6a882cd6caa6b58db3ae5c102efe50ec625b3e2a5cbc50db5bfe4`.

## Limits and remaining native gates

Local ARM64 Docker fixtures do not certify x86_64 systemd delegation, actual VPS
Docker placement, parent resource isolation or installed release/configuration.
The native runner is control-only and requires separate exact-byte owner authority
and independent review. Its three actual fixture cases cannot substitute for all
control-specific operational evidence.

The immutable offline packet intentionally has no installation/restoration commands
without inspected host identities. Remaining prerequisites are current scheduling
ownership/closure, retained service identities, delegation/ancestor limits, private
socket identity, a kernel-enforced persistent output volume, verified compatible
rollback, complete installed release/configuration/frozen-worker identities, and
matching native acceptance. Missing prerequisites remain blockers, never passing
checkboxes. Computation stays paused through recovery and acceptance.
