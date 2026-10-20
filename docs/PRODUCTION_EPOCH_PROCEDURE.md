# Production epoch operation — awaiting independent review and owner authorization

**0.5.0 preview; 0.6.0 ignored; C diagnostics abandoned; backups deferred.**
No epoch or service change is authorized by this preparation procedure. The
separate [operation entry point](../scripts/production_epoch_operation.py) provides
`prepare`, `execute`, `audit` and `finalize`. The rehearsal-only entry point and its
`disposable_rehearsal_only` guard remain unchanged.

## Review packet and preparation

The versioned owner-only packet directory is
`$HOME/.config/mldsafail-production/preparation-20261020-v2`. Its `packet.json`,
`packet-receipt.json`, `review.json`, `manifest.json`, `inspection-receipt.json`
and `HANDOFF.md` record exact private locations, hashes and blockers. No execution
authorization file is present. Preserve earlier candidates and activation links.
The current packet is for review and has no execution authority. Missing retained
configuration evidence must be resolved or explicitly returned as a blocker;
never mark its inspection successful. The withdrawn, unexecuted C draft is
distinguished from the three executed trial configurations by retained records.

From the repository root, using the existing environment:

```sh
source .venv/bin/activate
python -m deploy.production_preflight \
  --production-env "$HOME/.config/mldsafail-production/preparation-20261020-v2/preparation.env" \
  --staging-env "$HOME/.config/mldsafail-production/preparation-20261020-v2/staging.env" \
  --preparation-manifest "$HOME/.config/mldsafail-production/preparation-20261020-v2/manifest.json" \
  --inspection-receipt "$HOME/.config/mldsafail-production/preparation-20261020-v2/inspection-receipt.json" \
  --preparation
python -m scripts.production_epoch_operation prepare \
  --packet "$HOME/.config/mldsafail-production/preparation-20261020-v2/packet.json"
```

Preparation runs no evaluator. It requires source-bound inspection evidence and
renders Compose only in memory with `SYNTHETIC_RENDER_ONLY_NOT_AN_EPOCH` substituted
for the absent epoch. This value is never written to a deployable environment.
A passing preparation explicitly retains the future audited epoch dependency.
Full mode requires a final manifest, actual epoch binding and actual rendering.
Both modes reject missing, stale, changed or insecure inspection records.

The packet binds deployment account `mldsafail`, host `178.128.17.58`, UID 1000,
rootless socket `/run/user/1000/docker.sock` and pinned ED25519 fingerprint
`SHA256:OtjIfXCrqewb9FTJ8jpU7Rq7aZL4P8P7U0dKZ8DoB5w`. Frozen controller source is
`1c9ca9eff3a1133aa8b508a35f6b174a587a4f01`. It records OCI index, amd64 manifest
and configuration identities separately, hashes `cli.py`, `evidence.py` and
`execution.py` from that Git object, and binds local operator dependencies,
candidate, manifest, receipt, this runbook, output destinations and timeouts.
Loaded images, the accepted original-worker build-commit limitation and owner
OAuth URL confirmation are retained in the [image-load receipt](acceptance/integration/candidate-image-load-20261020.md).

## Prerequisites before later execution approval

An independent reviewer must inspect the exact packet and wrapper and publish a
private review with `packet_sha256`, `decision: approved` and their `reviewer`
identity. The current `review.json` says pending; implementation tests are not an
independent review. Owner authorization must separately bind that review's path
and SHA256, packet SHA256, `authorized_by: owner` and
`purpose: production_epoch_only`. No existing rehearsal or image-load permission
satisfies this guard. Any packet change invalidates its approval.

Refresh bounded read-only SSH inspection with the recorded key and pinned host
file. Inventory receipts expire after 24 hours for preparation and after five
minutes for execution. Bundle-internal configuration and evidence references are relative and remain
hash-identical when transferred. The packet binds its remote bundle destination
`/home/mldsafail/production-epoch-preparation-20261020-v2`; execution requires that
exact location. Later transfer/provisioning requires its own authority. Verify
the private receipt's file hashes after transfer and use the exact reviewed
operator checkout. No transfer or remote configuration provisioning occurs now.

Execution additionally requires the existing coordinator containers to be stopped
and their automatic restart policies disabled under **later separate owner
authority**. Record exact coordinator IDs and allowed running services. Establish
that no other scheduler/evaluator can start during the maintenance window; an
operation lock alone does not fence the coordinator. The wrapper verifies stopped
coordinators, restart policies, running-container allowlists, process inventory,
absence of user-manager jobs, service-scope disk/RAM floors and load below 0.5.
Require a reviewed existing worker cgroup with adequate delegation. This phase
neither stops services nor provisions that cgroup. Do not approve execution while
scheduling ownership or delegation is uncertain.

## Later execution, audit and finalization

These commands are for the separately reviewed packet on the deployment host,
from its reviewed operator checkout. `HANDOFF.md` records checkout/file identities. They are not to be run during preparation:

```sh
python -m scripts.production_epoch_operation execute \
  --packet /home/mldsafail/production-epoch-preparation-20261020-v2/packet.json \
  --authorization /home/mldsafail/production-epoch-preparation-20261020-v2/owner-authorization.json
python -m scripts.production_epoch_operation audit \
  --packet /home/mldsafail/production-epoch-preparation-20261020-v2/packet.json
python -m scripts.production_epoch_operation finalize \
  --packet /home/mldsafail/production-epoch-preparation-20261020-v2/packet.json \
  --destination /home/mldsafail/production-epoch-final-20261020
```

The destination must equal the packet's `final_destination`. Execution holds an
exclusive nonblocking lock and publishes an exclusive durable attempt marker
before output allocation or evaluation. It invokes frozen `create_epoch` exactly
once, with the unchanged worker and no profile/seed choices. Controller constraints
are network none, read-only root, no capabilities, no-new-privileges, rootless user,
512 MiB, one CPU, 256 PIDs, bounded tmpfs and reviewed cgroup. Worker invocations
retain frozen limits and receive only operation ownership labels/cgroup tagging.
Creation and audit deadlines are 5,400 and 600 seconds. Inspection commands are
bounded at 20 seconds; process/systemd queries at ten seconds.

Creation failure, timeout, interruption or audit failure is terminal. Do not
remove the attempt marker, rerun creation, replace the destination, reseed, reseal,
rank partial evidence or resume failed evidence. Retain journal, streamed stdout
and stderr, exit receipts and the entire complete or partial evaluator directory.
On failure the wrapper terminates only resources whose exact unique operation
label is independently inspected; it retains stopped resources and evidence for
owner disposition. Cleanup failure is itself retained, never a retry invitation.

Audit uses a separate controller with a read-only epoch mount and no Docker
socket. It invokes the frozen auditor against the existing seal and requires 100
reference cases. Successful audit records actual epoch/environment, trusted
fingerprint, daemon, seal, manifest and reference hashes. Finalization verifies
all sealed file hashes again, writes a new private final candidate and final
manifest, and runs strict full configuration checks and actual Compose rendering.
It never modifies the preparation candidate or scientific evidence.

Postflight: inspect `journal.json`, `create.exit.json`, `audit.exit.json`,
`audited.json` and the new final `preflight.json` privately; compare epoch and
reference hashes to audit receipts, refresh host processes/containers/mounts and
resource floors, and record disposition of scheduling controls under their later
authority. Independently run full preflight with the final `production.env`,
`manifest.json` and `receipt.json`, omitting `--preparation`. A successful epoch
and final preflight do not authorize deployment, public listeners, CA issuance,
OAuth login, notifications or publication. Item 3 remains partial pending item 4.
