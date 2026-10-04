# Fresh authority for every operator activation

This implements the per-activation alternative to a persistent delegated
operator parent. A user oneshot unit's cgroup may disappear when it exits.
`deploy.operator_activation` derives the actual current parent, creates a new
source-bound daemon and nonce-derived worker slice through the reviewed native
driver, and retires both before reporting success. It never reuses an earlier
operator manifest for a new evaluation or restoration.

The common private activation-root flock serializes complete invocations.
An interrupted earlier driver journal is terminally reconciled under the new
controller before another daemon can start. Cleanup never restarts the old
daemon. Unknown or damaged prior journals retain a fence. `--cleanup` performs
the same reconciliation without provisioning a new daemon. The generated
`ExecStopPost` invokes that path while the unit controller still exists.

`deploy.render_activation_units` renders **inactive systemd user units** from
complete retained source hashes and a source-bound Python 3.12.10 interpreter.
These replace the earlier system-manager backup/check templates when the
repeat-activation gate and relevant manual/external gates pass. No unit or timer
is installed or enabled by the renderer. Read-only staging monitoring is a
separate unit and does not inherit the isolated daemon endpoint.

Copy the public activation templates to owner-controlled private regular files
(0600) under a private directory (0700). The driver template follows
`research/cpu_measurement/OWNED_DAEMON_NATIVE.md`: pin the exact retained source,
binary and image archive identities, protected staging/evaluator roots and
cgroups, and actual independent review packet. That packet must also contain
`acceptance_source_sha256`, equal to the retained
`deploy/operator_activation.py` hash. Each invocation overrides only its fresh
state root and actual unit/controller fields. Never fabricate review booleans.

For daily recovery, the private activation config selects the existing reviewed
daily config. The wrapper injects the fresh `owned_daemon_manifest` into its
backup configuration solely for disposable restoration. Assembly and live
database dumping retain the established same-user staging Docker endpoint.
The source line must include the reviewed recovery consumer integration and
strict verified-state publication before this job is eligible. Actual external
storage, independently held password custody, and manual daily acceptance
remain required. The lifecycle fixture needs no storage credentials and uses
only a fixed tiny Python output, no epoch or benchmark measurement.

## Native two-activation gate

Freeze the coherent source and retain the exact pinned image archive before
starting. Through the existing durable native operator launcher, execute the
fixture twice in **two actual named transient systemd user units**, each with
`Delegate=yes`, `UMask=0077`, `Restart=no`, and `KillMode=control-group`. Pass
each actual unit name to:

```sh
python -m deploy.operator_activation --config /private/fixture.json --unit mldsafail-activation-fixture-1.service
python -m deploy.operator_activation --config /private/fixture.json --unit mldsafail-activation-fixture-2.service
```

Both invocations use the same private activation root. Preserve their
`activation-<nonce>/activation.json`, driver journal, failed attempts and raw
private streams. The trusted launcher must retain unit intents and prove
terminal unit/controller absence even after interruption. These commands must
run in the declared units; invoking both in one surviving unit is rejected by
the gate's controller identity check.

From a separate reviewed delegated controller run:

```sh
python -m scripts.native_repeat_activation_verification --receipt /private/root/activation-<first>/activation.json --receipt /private/root/activation-<second>/activation.json --output /private/new-verification
```

The verifier requires two distinct controller births, driver roots and daemon
epochs from the same exact source, completed matching driver evidence, absent
old controller/daemon/worker/client domains and terminal units. It also performs
an actual cross-process native flock rejection with the dedicated contention
marker while holding the common activation lock. Its own bounded clients are
independently cleaned before a successful receipt is published. The outer
launcher separately proves the verifier controller has exited.

This gate proves lifecycle repetition and serialization. It supplies no CPU
measurement, scoring-contract adoption, external storage acceptance, timer
activation or production approval. Preserve every failure instead of treating
an empty Docker inventory as daemon quiescence.

Interrupted daily/check jobs retain a private effective configuration and exact journal path before invocation. Each first durable job-journal publication must be acknowledged in the activation journal before a client can execute; failed acknowledgement is retried on subsequent publication. The next activation terminally retires the old dedicated daemon and worker domains, then reconciles the original job journal under the same provision lease before provisioning another daemon. Shared staging mutation uncertainty remains fenced and requires its own quiescence proof. Missing job journals are permitted only for a typed durable never-admitted intent. Native two-fixture activation success does not establish daily interruption or external backup acceptance.
