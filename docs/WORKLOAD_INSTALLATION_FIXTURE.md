# Disposable installation fixture

The reusable driver implements `prepare`, `provision`, `inspect`, `install`,
`reconcile`, `rollback` and `cleanup`. The independently reviewed implementation
is committed at `f442684`, with reviewed fixes at `e61ac65` and `94c9b3e`. The [latest checkpoint](acceptance/production-preparation/protected-runtime-fixture-20261024.md)
records an unsuccessful fresh-guest rehearsal; native acceptance remains open.

Use canonical absolute private paths without symlink components. Preparation
exclusively creates a generation and freezes its Git source snapshot, input
hashes, final paths, target identity and resource plan. Changed inputs require a
new generation. Every mutating phase holds the lifecycle lock; bounded workers
must prove the inherited lock and a single-use parent request. Failures preserve
intents, observations and logs and stop dependent execution.

The implementation has three layers:

- [Guest provisioning](../scripts/provision_installation_fixture_guest.py) accepts
  pinned package versions and hash-bound archives, wheels, image archives and a
  rootless launcher. It requires a newly allocated disposable x86_64 QEMU guest,
  systemd, cgroup v2 delegation and subordinate UID/GID mappings. Downloads are
  allowed here. It creates its own rootless Docker daemon and refuses inherited
  Docker resources. See Docker's [rootless requirements](https://docs.docker.com/engine/security/rootless/tips/).
- [Recipe preparation](../scripts/prepare_installation_fixture_recipe.py) freezes
  actual environment identities, reviewed source bytes and final absolute paths.
  Its built-in recipe declares schema `mldsafail.installation-fixture.v1`,
  `fixture_only: true`, target hostname/machine ID/UID, absolute input paths,
  built-in provision/inspect/postflight/cleanup adapters and a generated resource
  plan. Arbitrary adapter code is unsupported.
- [The case runner](../scripts/rehearse_workload_installation_fixture.py) drives
  the concrete installation engine, fresh frozen-proposal observation and
  rollback. Component review receipts must approve the exact source hashes with
  scope `disposable_fixture_components_only`. Synthetic review and execution
  inputs are visibly fixture-only and generation-bound; engine validation stays
  in force.

Allocate each case in a fresh guest using
[the VM lifecycle helper](../scripts/workload_vm_fixture.py). Its `--allocate-from`,
`--download` and `--case` arguments produce independent disks and ownership
records; running the resulting root starts the guest. Existing retained guests
require their explicit adoption audit. The fixture commands are available through
`python -m scripts.workload_installation_fixture --help`; guest provider, recipe
and rehearsal modules expose their Python entrypoints for orchestration.
A private component receipt and real offline inputs are required before native
mutation. Do not substitute empty archives or fabricated image identities.

Provisioning creates disposable PostgreSQL with deterministic contents, inert
retained web/proxy services, synthetic credentials, a previous supervisor and
scheduling owner, bounded persistent output and three private configurations.
The previous release is observed for compatibility before rollback selection.
Actual interpreter and installer archives, locked wheels and retained images are
used; dependency installation runs offline. Computational permission remains
absent. Baselines bind retained container/image identities, database schema/data,
unit bytes/settings, activation, release dependencies and output mounts.

The five fixed cases are `complete`, `partial-snapshots`,
`partial-configurations`, `unacknowledged-images` and `interrupted-rollback`.
Each interruption has an explicit boundary and reconciliation assertions.
Unacknowledged image effects must block conservative replay. A case result alone
cannot certify native performance or the production host. The mapped peer-UID
probe is integrated with synthetic credentials and no Docker socket inside it;
its native result remains unexecuted at this checkpoint.

Each attempt is bounded to 30 minutes, reserving five minutes for cleanup and
postflight. Cleanup proves identity and inactivity before changing resources,
refuses unresolved effects and records uncertainty. Successful fixture cleanup
can retain named active retained services, output, rollback dependencies and
journals under an explicit retention exception; that is not complete retirement
or permission for bulk deletion. Partial provisioning does not erase unacknowledged
resources. [The retention policy](RETENTION_POLICY.md) governs later removal.

The local Docker regression suite passes. The latest fresh x86_64 emulated guest
could not finish loading the offline runtime images within the existing
35-second command bound. Its observer recorded a timeout, no remaining children
and no cleanup errors. The provider stopped its daemon and VM shutdown was
verified. Earlier attempts exposed a package-provisioning containment issue and
a worker deadline-journal defect; reviewed corrections were tested in new
generations. Historical emulation failure at the 0.8-second helper deadline and
the separate 0.6-second containment regression remain recorded. Deadlines are
unchanged. No full installation, rollback, interruption or native peer-UID
success is claimed.

This fixture does not authorize VPS installation, whole-proposal approval,
epochs, notifications, public activation or publication. Benchmark 0.5.0 and the
$0 budget remain unchanged.

The [2026-10-26 engineering handoff](acceptance/production-preparation/protected-runtime-engineering-20261026.md)
adds the independently supervised installed-native control context. It reuses
owned fixture runners without granting installation, rollback or VM lifecycle
authority. The complete fixture installation → fresh inspection → rollback path
and its four interruption cases remain separate from one-case native packets.
