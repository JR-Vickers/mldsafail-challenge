# Dedicated daemon native acceptance protocol

This protocol is private operator preparation. No native accounting or daemon
barrier gate has passed from the source checks. Do not run performance pairs
until the retained source passes both independent reviews and the complete
native fault suite. Never stop, restart, reconfigure, or target staging's shared
`docker.service`, socket, data directory, worker parent, evaluator, or epoch.

## Provisioning sequence

One trusted primary operator owns all native maintenance. Record the retained
Git commit, supervisor source digest, immutable image digest, actual dockerd
executable SHA256/server version/GitCommit, and predeclared Docker API version.
Retain private receipts and failure evidence; commit only sanitized identities.

1. Create a fresh private operator-owned parent directory for disposable daemon
   state. Supply the real staging/deployment/evaluator roots to
   `deploy.owned_daemon.provision(base, unit=..., protected_roots=...)`. The
   daemon unit must have a dedicated `mldsafail-owned-daemon-...service` or
   `mldsafail-cpu-daemon-...service` name. Existing roots cannot be reused.
2. Read the returned provisioning `id`. Provision and start an empty user slice
   named exactly `mldsafail-owned-workers-{id}.slice` or
   `mldsafail-cpu-workers-{id}.slice`, matching the unit kind. Keep that slice
   active across invocations. Obtain its actual canonical cgroup-v2 path from
   systemd; do not infer a path from a hostname or a staging slice.
3. Provision a separate delegated operator-client domain. It must be disjoint
   from the worker parent, daemon service domain, and protected staging domains.
   Set `MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT` to its exact canonical path.
   Call `bind_worker(provisioning, worker_parent=..., worker_cgroup_parent=...,
   operator_parent=..., protected_domains=...)`. Use the returned durable
   provisioning receipt thereafter. This verifies emptiness and binds kernel
   birth identities before the first daemon mutation.
4. Install a dedicated user unit from `templates/owned-daemon.service.in`, using
   only the fresh provisioned paths and exact worker slice name. Use explicit
   private socket, data root, exec root and rootlesskit state, `Restart=no`,
   `KillMode=control-group`, `Delegate=yes`, and live restore disabled. Start
   only this dedicated unit. No shared-daemon restart is permitted.
5. Set `DOCKER_HOST` to the exact private dedicated Unix socket; unset
   `DOCKER_CONTEXT`. Call `register(...)` with the unit, all provisioned roots,
   socket, private manifest path, reviewed native executable/server identities,
   exact worker parent/slice, and returned provisioning receipt. Registration
   refuses a mismatched daemon command line, kernel identity, socket, roots,
   process, worker birth, or operator domain.
6. Set `MLDSAFAIL_OPERATOR_DAEMON_MANIFEST` to that private manifest. If the CPU
   alias is also set, both aliases must refer to the same file. Verify the
   manifest/environment before loading the exact retained immutable image into
   this isolated daemon. Reconcile any failed provisioning/image operation
   before beginning measurements; unavailable images are not expected faults.

## Gates and evidence

First execute one verified/no-answer native baseline with complete audited
cleanup. Run `native_fault_suite` using the exact manifest, retained image,
worker parent/slice and a declared supported `--api-version`. The suite includes
real owner SIGKILL before client release, connection loss, existing accounting
and cleanup faults, descendant membership, and separately instrumented lost
create/start acknowledgements. The latter forward a real RPC and retain an
actual successful daemon response before owner loss; mere CLI creation is
insufficient. The start probe requires running/open stdin before attach/input.

Require every declared injection to be reached, every expected cause to match,
every generation fence to hold, and independent cleanup receipts to pass. A
lost mutation must positively stop the exact dedicated daemon domain and the
entire separately owned worker parent, including unacknowledged late workers.
Only then cancel creators, restart, and verify the exact durable next epoch.
Test interrupted restart after manifest publication and before journal repair;
reconciliation must resume that same bound epoch without signaling newer work.
Retain failed barriers and uncertainty until a positive exact proof exists.

After all native faults and two source-bound reviews pass, run the unchanged
thirty sequential empty/deterministic pairs and independently audit every
immutable generation. Preserve the predeclared CV, CPU-overhead, and wall-time
thresholds. No repeated unchanged experiment may replace a meaningful failure.

Before leaving maintenance, verify the dedicated daemon identity and health,
empty worker parent, all owned client domains removed, private socket/evidence
permissions, accounted fault resources, and unchanged staging service state.
Record the actual retained source and image identities in the canonical ledger.
Source tests, this runbook, and artifact retention do not substitute for native
acceptance, contract adoption, reference sealing, or production activation.
