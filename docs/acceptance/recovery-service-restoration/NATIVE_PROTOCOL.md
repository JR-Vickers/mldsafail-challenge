# Disposable native recovery acceptance

Run only on a rootless Docker host with no overlapping host measurements or
maintenance. Use a preloaded immutable Alpine-compatible image with `sh`, `sleep`,
`cat` and `true`. Record host/kernel/Docker/image/source identities before running:

```sh
python -m deploy.native_recovery_acceptance --image "$FIXTURE_IMAGE_DIGEST" \
  --output "$NEW_PRIVATE_ABSOLUTE_EVIDENCE_DIRECTORY"
```

The unique Compose project exposes no ports and mounts only its own new named
fixture volume. A completed migration appends a sentinel once. Each case stops
original application containers, injects interruption or cleanup failure, rejects
concurrent ownership, retries cleanup twice, and verifies unchanged container IDs,
migration state and sentinel count. Raw logs and interrupted/reconciled journals
remain protected in the output directory. The final report passes only after
owned containers are removed. If cleanup fails, use the exact project recorded
in ownership.json to inspect and repair only those fixture resources before any
conflicting operation; do not run broad Docker cleanup.

The `connection_loss` case models loss of the controlling process with SIGKILL;
it does **not** pass actual SSH transport or host power-loss acceptance. For actual
transport loss run the suite in a disposable VM through a connection that can be
closed, reconnect, and inspect the saved operation journal before invoking its
cleanup under exclusive ownership. Verify the same identity/sentinel invariants.
Retain the transport failure and reconciliation evidence independently.

Actual power-loss acceptance requires a dedicated disposable VM whose power
control cannot affect staging. Record its machine identity and isolated Docker
project, interrupt power after boundary.json is durably present, restart the VM,
reconcile the saved operation journal under its file lock, and repeat cleanup.
Verify journals parse after restart, original IDs survive, stopped/running states
are restored, migration sentinel remains one, and all fixture resources clean up.
Use the provider's explicit hard-power operation only for that recorded VM; no
staging-host power operation is authorized by this protocol. Report each real
transport/power gate separately; simulated process failures cannot substitute.
