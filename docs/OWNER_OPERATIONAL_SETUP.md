# Owner inputs for encrypted recovery and external alerts

Prepared 2026-10-04. Host inspection found no installed off-host recovery/monitoring
timers or corresponding private configuration at the documented locations. The
checked-in units and tools are preparation, not a working backup/alert service.
Existing local PostgreSQL backup is a distinct mechanism and does not satisfy
encrypted off-host recovery. No new account, secret, repository or timer is created
by this guide.

The owner supplies **two things**: scoped object-storage access with independently
retained recovery password, and an approved alert receiver with its bearer token.
The agent can fill installed paths, release/image identities, hashes and native
verification after these inputs are supplied privately. Do not paste secrets into
chat, Git, public issue records or command logs.

## Object storage and password custody

Choose an S3-compatible HTTPS endpoint and bucket outside the staging host's failure
domain. Supply endpoint hostname/URL, bucket name, region if required, and a scoped
access-key ID/secret via protected files or existing secret custody. Use separate
repository prefixes ending exactly `/staging` and `/production`; the recovery code
requires that environment suffix. No provider or paid purchase is selected here.

Grant bucket listing/location lookup and object read/write/delete only for the
chosen recovery prefixes, including restic lock objects. Restic writes encrypted
packs/indexes/snapshots/config and transient locks; repository check/restore needs
read/list; retention/prune and lock cleanup need delete. A read-only credential
cannot run backup; a no-delete credential cannot run declared pruning/lock cleanup.
Do not grant account administration or access to unrelated bucket prefixes.
Provider IAM syntax differs: have the owner/provider verify scoped permissions;
manual repository initialization/check/upload/restore/prune acceptance verifies
the actual grants. Bucket versioning/object-lock policies must be compatible with
restic deletion and declared retention, rather than silently defeating prune.

Create a strong unique restic repository password under owner control. Store one
copy in an independent password manager or other protected off-host custody that
survives host loss; place the operational copy in a private 0600 regular file.
The password is required to decrypt a restore. Its only host copy does not satisfy
custody. Keep repository coordinates and scoped recovery access retrievable off
host as well. Do not include password or storage credentials in a recovery set.
Set `owner_retained_recovery_key` true only after custody is actually confirmed.

Copy [backup-credentials.json](../deploy/templates/backup-credentials.json) outside
the repo and fill its literal JSON strings. Supported keys are exactly
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, optional `AWS_SESSION_TOKEN` for
short-lived credentials and optional `AWS_DEFAULT_REGION`. Omit optional keys
that your provider does not use. Expiring session tokens require an explicit
renewal process; static timers cannot invent renewed credentials. File mode must
be 0600 and it must not be a symlink. Use 0700 parent directories.

Copy [daily-recovery.json](../deploy/templates/daily-recovery.json) to a private
0600 regular file. Operator fills `assembly` deployed env/Compose/interpreter
paths and all sealed material sources. `material` maps safe relative archive
names to source paths; include all required application/evaluator secrets,
configuration, retained manifests, rollback identities and image archives. Copy
only completed audited evidence and sealed epoch; the assembler collects those
from the deployed coordinator. Never add mutable jobs, cleanup tokens,
`restic-password`, `backup-credentials` or the entire secret directory blindly.

Operator fills installed restic binary/hash and exact immutable restore image
IDs (`sha256:` plus 64 hex digits). `backup_state` is a private output file;
do not fabricate it or manually set restore verification. A standalone
`deploy.recovery` check config uses the template's `backup` object, not the whole
daily wrapper. `restore_snapshot` is a real recorded snapshot ID for an explicit
restore; `restore_verified_snapshot` is required for prune after native isolated
restore. The daily pipeline obtains/restores the uploaded snapshot itself.

Before any timer activation: verify installed frozen interpreter/module paths,
quiescent assembly and migration-safe service restoration; initialize the approved
encrypted repository; complete manual upload/full `check --read-data`, interrupted
upload and corruption rejection, isolated DB/evidence restore and cleanup; then
verify retention, latest verified snapshot freshness and four-hour restore target.
The first backup must be manually verified. The monitor fails if no verified
snapshot exists or it is older than 26 hours. Keep at least two verified local
sets; remote policy is seven daily, four weekly and six monthly snapshots.
Never restore into the live database. Native tests and owner-supplied inputs must
pass before units are installed/enabled.

## Alert receiver contract

Supply an approved **HTTPS** URL and scoped bearer token privately. It must accept
POST with `Content-Type: application/json` and `Authorization: Bearer TOKEN`, and
return a direct HTTP 2xx response. Redirects are rejected. URL-embedded username/
password is forbidden. A Slack/Discord/email webhook with a different payload is
not automatically compatible; configure an approved adapter or receiver first.
No external message is sent until delivery acceptance is explicitly authorized.

Failure body example (sanitized):

```json
{"status":"failure","checks":["backup","lease"]}
```

Recovery body:

```json
{"status":"recovered","checks":[]}
```

Allowed codes are `readiness`, `service`, `disk`, `ram`, `lease`, `backup`, and
`scheduled_job`. No hostname, exception text, database data, participant source,
private evidence or credential is included. The implementation retries at most
three times with five-second request timeouts, deduplicates unchanged failure sets
for ten minutes, and sends immediate recovery after a previously delivered failure.
Receiver should tolerate retry duplicates if a response is lost.

Copy [monitor.json](../deploy/templates/monitor.json) outside the checkout with
0600 mode. Fill deployed env/Compose paths, readiness endpoint, matching verified
backup state/repository, `expected_epoch_id` matching the exact deployed audited
epoch, actual scheduled units, receiver URL and private token file. Monitoring
requires the versioned `mldsafail.recovery-state.v1` receipt to bind full immutable
snapshot, repository, epoch, result count and restored manifest digest, with
strict restore/cleanup booleans and nonfuture timezone-aware upload/verification
times. Freshness uses `uploaded_at`: re-verifying an old upload cannot refresh it. Leave `alert_enabled` false while wiring read-only checks. Operator must
verify the readiness URL: production proxy blocks operational endpoints, so use
an approved private internal route rather than publicly exposing health checks.
Place the token in a private regular 0600 file, not the JSON itself. `alert_state`
is private output for delivery deduplication; never prepopulate it to fake success.

Run native checks manually; verify missing/stale backup, expired lease, failed
scheduled job, service/resource/readiness failures plus receiver retries,
deduplication and recovery. Native fault injection must be disposable or an
explicit serialized staging protocol. Only after manual acceptance and authorized
external delivery should `alert_enabled` become true and installed monitoring/
recovery timers be activated. Record exact unit/interpreter/source identities and
current health, not merely successful JSON parsing.

## Render source-bound inactive system units

The generic checked-in system units point at `/srv/mldsafail/current/.venv`.
That path is not installed in current staging. Never create an unreviewed current
symlink or change frozen application source merely to make a generic unit work.
Choose the retained **operator source** containing accepted recovery/monitoring
fixes, its source manifest (`source_commit`, `source_files_sha256`), and the exact
installed Python 3.12.10 environment separately. Existing native frozen interpreter
is in the retained fd4be66 source environment; operator modules should resolve
from the explicitly supplied retained working directory, with hashes checked.

Prepare JSON mapping `daily-recovery`, `recovery`, `monitor` to literal absolute
private configuration paths. The standalone `recovery` JSON is the daily wrapper's
`backup` object. Then render into a new protected directory:

```sh
python -m deploy.render_operator_units --source "$RETAINED_OPERATOR_SOURCE" \
  --interpreter "$INSTALLED_OPERATOR_PYTHON" --metadata "$OPERATOR_SOURCE_MANIFEST" \
  --configs "$PRIVATE_CONFIG_PATH_MAPPING" --user mldsafail --uid "$DEPLOYMENT_UID" \
  --output "$NEW_INACTIVE_UNIT_DIRECTORY"
```

The renderer verifies every `deploy/*.py` against source metadata and actual
module resolution through the chosen interpreter. It records interpreter hash
and unit hashes. System `User=` units receive explicit
`DOCKER_HOST=unix:///run/user/UID/docker.sock` and `XDG_RUNTIME_DIR=/run/user/UID`;
otherwise systemd may address the wrong daemon or lack the user's runtime path.
Missing private configs are explicitly activation-blocking in the render report.
Present configs must be private regular files; content acceptance remains separate.
No unit is installed or activated by this command.

Primary operator must native-verify the rendered units using `systemd-analyze
verify` plus manual exact-interpreter/module/container/readiness acceptance under
the intended account and rootless environment. Confirm runtime socket availability,
user/UID ownership and lingering policy. Install/enable timers only after these
checks, required owner inputs and manual recovery/monitoring acceptance pass.

The rendered system service units delegate their own cgroup with `Delegate=yes`
and set `MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT` to
`/sys/fs/cgroup/system.slice/%n` (systemd expands `%n` to the current unit name).
Each native command is born behind a durable gate and moved to a new owned child
there before exec; cleanup kills that child's complete kernel membership, including
Compose plugin descendants. No CPU controller changes or benchmark accounting
parent reuse are permitted. Keep system units in their rendered default slice;
a custom slice requires separately rendered/reviewed cgroup-root settings.

Manual native acceptance requires a separately delegated operator unit/cgroup and
an explicit writable `MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT`. It must be disjoint
from the benchmark measurement parent and staging evaluator ownership. Native
preflight checks child `cgroup.procs`, `cgroup.events` and `cgroup.kill`, delegation,
ownership and cleanup; a configuration string alone does not prove those gates.
Render only, then have the primary operator verify source/module/executable paths,
`systemd-analyze verify`, delegated child lifecycle, rootless socket access and
manual recovery before installation or activation. Missing storage/webhook inputs
still prevent external acceptance and scheduled activation.
