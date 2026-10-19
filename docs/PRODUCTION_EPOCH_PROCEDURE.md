# Proposed production epoch procedure (not authorized)

**0.5.0 preview; 0.6.0 ignored; C diagnostics abandoned; backups deferred.**
No epoch has been created. This procedure is blocked before execution: the
selected web/coordinator are archived but not resolvable in the installation's
rootless daemon. Do not load them under the preparation authorization. Resolve
worker provenance under the separate item 1 decision before production execution.

The production wrapper is **not implemented or approved**. The existing
`scripts/native_production_epoch.py` remains rehearsal-only, including its
`disposable_rehearsal_only` guard. Do not use or relabel its output for production.
The following specifies the exact frozen creation/audit interfaces for the later
reviewed wrapper; it is not a shell recipe to run now.

## Required operation packet

Use deployment account `mldsafail` at `178.128.17.58`, UID 1000,
`/run/user/1000/docker.sock`, and the retained pinned ED25519 identity
`SHA256:OtjIfXCrqewb9FTJ8jpU7Rq7aZL4P8P7U0dKZ8DoB5w`.
Controller source is `1c9ca9eff3a1133aa8b508a35f6b174a587a4f01`;
controller image index is
`sha256:b3f27a3b1b3d25d808f21ac56f2653dc5bd29f77dd9903acfd84969080c0d0a4`.
Worker image index is
`sha256:6aaf71aa16e36631dec607f0726fb1e8d6f94954ce55a15a74ba4989777b5cfe`.
Use Linux amd64 and Python 3.12.10. Reconcile index, platform manifest,
configuration and actual Docker inspection separately against the
[artifact report](acceptance/integration/mvp-artifact-verification-20261019.md).
Never replace index identities with config digests merely because they look alike.

Before authorization, finish a separate production wrapper and independently
review its bytes and a private operation packet. Record SHA256 for that wrapper,
the exact selected source versions of benchmark_v050/{cli,evidence,execution}.py,
the Docker tagging/cgroup wrapper if needed, the host-check helper, this runbook,
and the private packet. Source hashes must come from the selected Git object,
not the evolving working tree. The packet must bind those hashes and a single
explicit `production_epoch_only` authorization, output paths, host, user, socket,
controller/worker identities, resource limits and audit command. Tests must mock
Docker and prove missing authorization, wrong purpose, failure and timeout leave
an attempted operation terminal with all partial evidence retained.

## Single-attempt execution contract

1. Independently verify source/image bindings, original-worker provenance decision,
   operation ownership and an exclusive nonblocking production operation lock.
   Refresh processes, Docker containers, active mounts, systemd jobs, disk/RAM and
   idle-host checks. Pause scheduling only under its separate authority; an idle
   coordinator is not proof that no work can arrive. Record before/after receipts.
   Use the existing service-scope resource-floor checks without inventing a backup
   pass. Refuse active jobs, unknown ownership, path aliases or concurrent operators.
2. Reserve a fresh private operation directory and a durable attempt marker with
   exclusive creation **before** any evaluator invocation. Directories are 0700,
   files 0600; no shared hardlinks. Proposed evaluator destination is
   `/srv/mldsafail-production-evaluator/epoch`, with new private sibling receipt
   storage selected and checked in the packet. Require the epoch destination not
   to exist; never delete, resume or replace a failed attempt automatically.
3. Invoke one controller with the exact immutable image, rootless socket,
   `--network none --read-only --cap-drop ALL --security-opt no-new-privileges`,
   user namespace and reviewed worker cgroup/resource constraints. Mount only its
   new evaluator output, rootless socket and reviewed optional Docker wrapper;
   no OAuth/database credentials, public ports or notification endpoints.
   The controller entrypoint is `/app/.venv/bin/python -c` with this frozen body
   (the wrapper supplies the two literal reviewed values):

   ```python
   from pathlib import Path
   from mldsafail.benchmark_v050 import cli, execution
   cli.environment = lambda: execution.environment(WORKER_IMAGE)
   cli.create_epoch(Path(EPOCH_DESTINATION))
   ```

   This executes the frozen three-baseline, four-repetition protocol and viability
   gates. One attempt only. Preserve stdout, stderr, exit status and all files,
   including FAILED.json or an incomplete directory, on failure or interruption.
   No retries, new nonce, replacement seeds, alternate worker or automatic cleanup.
4. On creation success only, run a **separate controller invocation** with the same
   exact source/worker/host binding and read-only epoch mount. Independently invoke:

   ```python
   from pathlib import Path
   from mldsafail.benchmark_v050.evidence import audit_epoch
   manifest, reference = audit_epoch(Path(EPOCH_DESTINATION))
   assert len(reference) == 100
   ```

   Creation already seals and audits via the frozen `create_epoch`; independent
   audit must validate that existing seal, not reseal modified data. Keep audit
   failure terminal. Hash COMPLETE.json, manifest, reference costs and both
   controller receipts privately; preserve failed or partial audit evidence.
5. Extract the actual epoch ID and environment from the audited manifest. Check
   worker ID, trusted fingerprint and complete host/interpreter/artifact bindings.
   Retain actual reference costs privately. Suite label `mlwe-v050` identifies
   the frozen version; `rootless-docker-v1` comes from the selected coordinator
   default. Neither supplies the missing epoch identity. Bind all actual cohort
   values into a **new** final environment and reviewed final manifest; preserve
   the preparation candidate. Recheck separation from every retained trial cohort.
6. Re-run strict full configuration preflight, Compose rendering privately in
   memory, private-file checks, image resolution, project/volume and mount/path
   isolation checks. No unresolved preparation manifest may pass full validation.
   Record resource/process/mount postflight and release the lock. A successful
   epoch does not authorize deployment, TLS/OAuth activation or publication.

## Current readiness

Wrapper implementation, its independent review and mocked failure verification
remain pending the image-resolution blocker and later operation authorization.
Consequently this is an interface-bound procedure draft, **not** an exact executable
item 4 packet. Item 3 remains partial pending item 4 and other preparation blockers.
