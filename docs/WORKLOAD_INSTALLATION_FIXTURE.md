# Disposable installation fixture engineering

This fixture is **unfinished**. The driver in
[scripts/workload_installation_fixture.py](../scripts/workload_installation_fixture.py)
currently provides exclusive preparation, private input/source bindings, lifecycle
locking, read-only local environment reports and durable failed-phase records.
It does not yet provide the complete concrete Linux installation fixture requested
by the owner. In particular, an unavailable environment does not resolve the
implementation gaps below.

Run the usable filesystem lifecycle from the repository root:

```sh
source .venv/bin/activate
python -m scripts.workload_installation_fixture prepare /absolute/private/new-generation
python -m scripts.workload_installation_fixture inspect /absolute/private/new-generation
```

Use canonical absolute paths without symlink components. Each invocation requires
the root; preparation refuses an existing namespace. A failed preparation retains
its creation intent and error. Preparation records the selected case, source
revision, source file hashes, driver hash, private directory births, final release
paths and unmet environment/implementation requirements. Inputs, if supplied,
are copied exclusively without hardlinks. A changed input or driver requires a new
generation. Preparation does not create Linux resources or execution authority.

`provision`, `install`, `reconcile`, `rollback` and `cleanup` are recognized but
fail closed. No native transition is enabled. A failed provision cannot be retried
in that generation; installation cannot follow it. Existing independent engine
reconciliation is still required before any future installation continuation.
The internal worker entrypoint also refuses execution until an inherited lifecycle
lock handoff is implemented and tested. Importable draft engine helpers are not
an operational interface.

The private recipe schema is experimental and has no supported executable adapter
interface. Its adapter names freeze inputs only; the driver never executes them.
Accepting arbitrary Python adapters would not establish read-only collection,
resource ownership or safe cleanup. The declared resource list is not yet backed
by concrete provisioning operations, so it confers no mutation permission.

The intended attempt budget is 30 minutes from first provision, with the last
five minutes reserved for cleanup/postflight. Expiry blocks further automatic
execution and records unresolved ownership; it is never a cleanup certificate or
a fresh budget. The current driver performs no resource deletion. Private
namespaces and failure records remain available for inspection under
[the retention policy](RETENTION_POLICY.md).

## Remaining implementation

- Implement built-in provisioning for actual compatible interpreter/installer
  archives, lock-derived wheels, retained images, disposable PostgreSQL,
  synthetic credentials, inert web/proxy services, previous supervisor,
  scheduling owner, bounded persistent output and three private configurations.
  Enforce the frozen resource allowlist at each operation with durable resource
  intents and observed identities.
- Complete the inherited lifecycle-lock handoff to bounded native workers.
  Execute compatibility, installed and rollback observers inside those workers,
  against frozen proposal/source bytes. The draft parent-side observation calls
  remain unreachable; they must move before native transitions are enabled.
- Implement read-only resource collection and deterministic database content
  fingerprints, baseline capture and transition invariants. Check original unit
  bytes/states, image and service births, output mounts, absent permission files,
  computational inhibition, descendant termination and resolved transactions.
- Integrate the existing coordinator-image peer-UID probe, including the mapped
  UID acceptance and incorrect UID rejection, using synthetic credentials and
  no Docker socket inside the probe.
- Complete and verify the four fixed fault runners. The draft harness uses
  existing snapshot/configuration callbacks and parent-step fault boundaries;
  it has not run them against a complete fixture. Each case needs its own
  generation and assertions for its expected reconciliation disposition.
- Implement ownership/inactivity/retention checks and concrete cleanup receipts.
  Unknown or unacknowledged resources must be retained. Preserve required output,
  journals and previous-release dependencies; never downgrade PostgreSQL or
  restart the older coordinator automatically.

The five cases are `complete`, `partial-snapshots`, `partial-configurations`,
`unacknowledged-images` and `interrupted-rollback`. Case selection alone is not a
runner result. Successful completion requires all concrete adapters and gates,
independent component review, and either a verified full rehearsal or a precise
environment blocker with failure evidence. This checkpoint meets neither full
fixture implementation nor full rehearsal completion.

The production VPS, frozen 0.5.0 benchmark, runtime deadlines and $0 budget are
unchanged. This work grants no VPS installation, whole-proposal approval, epoch,
notification, public activation or publication authority.
