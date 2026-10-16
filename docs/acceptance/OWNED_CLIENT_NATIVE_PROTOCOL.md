# Disposable operator client native fault gate

This gate uses only tiny local Python touch/sleep fixtures. It does not use Docker, staging mounts, ports, benchmark data, recovery credentials, or the benchmark accounting cgroup parent. Local filesystem emulation tests are not native evidence.

Retain a clean committed source checkout and exact interpreter. Run inside an exclusively owned delegated systemd unit (`Delegate=yes`) with `MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT` set to its canonical cgroup-v2 domain. The parent and created children must belong to the executing UID and prohibit group/world writes. No CPU controller is required. Create a separate mode-0700 evidence parent, then run:

```sh
python -m deploy.native_owned_client_acceptance --output /private/operator-client-gate/fresh-run
```

The pre-release fixture publishes its domain and PID receipt, blocks before gate release, and its controller is killed through a separately durable owned cgroup. The native gate proves bootstrap EOF makes the client domain empty before invoking cleanup and that no mutation occurred. The released fixture exits its CLI leader while a grandchild remains; killing the fixture owner and cancelling the recorded client domain must stop the inherited descendant. Device, inode, and UID mismatches refuse cancellation; a prior-boot receipt cannot signal the current domain. Both fixtures require exact domain removal, no late mutation, and repeated idempotent cleanup.

The report binds source commit, helper/script SHA-256, Python identity and boot ID. Private owner/client journals and failure logs are retained. A source/emulation result does not satisfy this gate. Run its cleanup independently after interruption or a failed run:

```sh
python -m deploy.native_owned_client_acceptance --output /private/operator-client-gate/fresh-run --cleanup
```

Cleanup cancels fixture controllers first, then independently attempts each client journal. Every retry publishes a fresh receipt and preserves earlier failures. Do not run another native host gate until cleanup is complete. Successful execution proves fixture clients have no remaining executable domain members; kernel zombies have no executable work. The separate helper unit tests cover bounded-output retention, streamed input, failed acknowledgement, closed input pipes, and independent wait/log/journal failure handling.
