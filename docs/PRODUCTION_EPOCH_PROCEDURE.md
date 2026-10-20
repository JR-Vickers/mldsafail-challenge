# Production epoch operation — awaiting independent review and owner authorization

**0.5.0 preview; 0.6.0 ignored; C diagnostics abandoned; backups deferred.**
No epoch or service change is authorized by this preparation procedure. The
separate [operation entry point](../scripts/production_epoch_operation.py) provides
`prepare`, `execute`, `audit` and `finalize`. The rehearsal-only entry point and its
`disposable_rehearsal_only` guard remain unchanged.

## Current review disposition

The [independent review follow-up](acceptance/integration/production-epoch-review-20261020.md)
records why execution is blocked. The v2 packet below is preserved historical
preparation evidence; it does not satisfy the corrected wrapper. Freeze a new
version only after maintenance preparation and transfer receive their separate
owner approvals. Never edit or reuse the old approval for new bytes.

A new packet must also bind `staging_sha256`, a private `maintenance` record and
`maintenance_sha256`, `worker_cgroup_path`, `cgroup_ancestor_limits` and
`scheduler_inventory`. The maintenance record retains `original_settings`, exact
`restoration_commands`, `scheduling_exclusion_verified: true` for execution only and
`restore_after_failure: only_after_verified_operation_resources_stopped`.
False or incomplete verification must remain blocked, never be filled in as an
anticipated result. Inspect system and user units, timers, cron files and root
crontabs, queue/running evaluations, alternate coordinators and restart owners.
Uninspectable scheduling owners block maintenance design and execution approval.
Bind reviewed stable command output hashes for `SCHEDULER_COMMANDS`; permission
failures do not establish absence. Disable all identified evaluation scheduling
paths during the approved window and retain exact restoration commands.

`worker_cgroup` is Docker's systemd slice identifier. `worker_cgroup_path` is its
actual absolute delegated sysfs directory, obtained from the user manager's
`ControlGroup` property; the two strings are not interchangeable. Require Docker
systemd/cgroup v2, the slice beneath user@1000.service, UID ownership and writable
control files, cpu/memory/pids controllers available and enabled, and reviewed
limits at every ancestor. Shared capacity must accommodate the frozen 2 GiB worker
and 512 MiB controller (320 aggregate PIDs); bind actual limits and inspect idle
host capacity separately. No evaluator probe is authorized for preparation.

SIGTERM is handled as a terminal interruption. Cleanup stops and verifies the
controller before remaining labelled resources, reinspects quiescence and writes
`termination.json`, including failures. Cleanup first stops the launch client and requires the exact
phase controller to have been observed; an unobserved launch is indeterminate and
never certified stopped. A failed operation must not have scheduling
restored until `verified_stopped` is true and fresh postflight confirms no owned
resources remain running. Logs and terminal receipts also survive spawn failures.

## Historical v2 review packet and preparation

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

## New packet contract

See the [maintenance proposal assessment](acceptance/integration/maintenance-proposal-20261020.md). New packets use `mldsafail.production-operation.v2` and explicit `state`: `maintenance_proposal` requires false scheduling verification; `execution_ready` requires true verification and a SHA256-bound `privileged_receipt` path and `privileged_receipt_sha256`. Receipt provenance is `owner_root_console`, bound to hostname, collector source hash and collection time. Root inspection uses no sudo. Live unprivileged inventories remain required. Preparation receipts expire after 24 hours and execution receipts after five minutes. Old packets are not upgraded or approved by this change. Current safe-drain and evidence blockers prevent command approval.

Execution-ready packets also bind `capacity_receipt` and `capacity_receipt_sha256`. The private assessment must bind host, frozen source, a relative retained measurement path and SHA256, compatible simultaneous observed usage, retained services, headroom, separate physical/available RAM and swap, configured limits and ancestor memory limits. Missing, negative, malformed or unsupported evidence blocks execution; configured maxima alone never suffice.


Maintenance inspection update (2026-10-20): see the [v2 inspection and blocked v3
proposal](acceptance/integration/maintenance-inspection-v2-20261020.md). New v3
execution requires a v2 evidence-bound scheduling review; historical approvals
are unchanged. Owner-console evidence, deployed fence compatibility, compatible
capacity and inspected delegation remain required. No maintenance, transfer or
epoch execution is authorized by preparation.

Maintenance feasibility update (2026-10-20): [v6 host-feasibility disposition](acceptance/integration/maintenance-feasibility-20261020.md) records read-only host RAM/cgroup and deployed-source/queue inspection. Capacity remains unresolved; the coordinator is restarting and deployed checkout admission/claim sources lack the reviewed mutex. Scheduling/reference closure and delegation remain incomplete. The [separate control proposal](acceptance/integration/maintenance-control-proposal-20261020.md) requires its own authorization; no control was implemented/acquired. Item 4 remains blocked, with no maintenance/transfer approval requested. Historical receipts stay unchanged.

Maintenance prerequisite decision update (2026-10-20): the [v7 owner decision request](acceptance/integration/maintenance-decisions-20261020.md) expands retained capacity searches, inspects system/user unit states and external sources read-only, and binds recursive scheduling and relative transfer dependency gaps. Compatible simultaneous demand/headroom, complete triggerability/reference closure, production delegation and a compatible fence remain unresolved. Item 4 stays blocked; the private v7 proposal is nontransferable and rejects execution. Owner decisions concern a separate capacity-investigation protocol and maintenance-control engineering, plus missing scheduling evidence. No maintenance, transfer, probe, resize or epoch approval is requested. Historical outcomes remain unchanged.


2026-10-20 maintenance update: [v8 prerequisites](acceptance/integration/maintenance-prerequisites-v8-20261020.md) and [capacity protocol](MAINTENANCE_CAPACITY_PROTOCOL.md) add local control engineering and protocol preparation. Item 4 remains blocked; the proposal is nontransferable and cannot execute. Epoch mutations require a live reviewed maintenance fence; no production adapter or maintenance window is approved. Historical results remain unchanged.

The [v9 capacity preparation](acceptance/integration/maintenance-prerequisites-v9-20261020.md)
is a blocked local engineering packet. `python -m scripts.prepare_capacity_packet
validate PRIVATE_PACKET` verifies proposal hashes only and never authorizes transfer
or execution. Capacity investigation uses `capacity_investigation_only`; it cannot
reuse `production_maintenance` or `production_epoch_only`. No capacity execution
request is ready until the v9 blockers and exact isolated-host bindings close.

[V10](acceptance/integration/maintenance-prerequisites-v10-20261020.md) supplies
further local control engineering and explicit investigation execute/cleanup-only
interfaces. Proposal state still rejects execution. Native acceptance and actual
host/evidence/delegation bindings remain mandatory; an emulated worker-image smoke
is not a capacity measurement. The proposed common investigation envelope now
includes explicit control overhead under the amended capacity protocol. Existing
`production_epoch_only` and live-fence gates are unchanged.
