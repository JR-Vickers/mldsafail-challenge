# Installation fixture lifecycle checkpoint — 2026-10-23

The requested complete fixture is **not implemented**. Source checkpoint
`754f545` adds a private, generation-bound lifecycle foundation and 26 focused
filesystem/failure tests. It does not satisfy the owner's completion condition.
The [driver contract and remaining work](../../WORKLOAD_INSTALLATION_FIXTURE.md)
describe the precise usable interface and implementation gaps. The latest
[protocol-3 engine checkpoint](protected-runtime-recovery-v3-20261023.md) retains
its original scope; engine, benchmark and deadline bytes are unchanged.

Preparation exclusively creates a namespace, records its intent, freezes source
and input hashes, binds directory/file births and retains preparation failures.
Inspection exclusively publishes a fresh private local environment report. The
lifecycle lock rejects overlap, symlinks and shared/replaced lock files. Failed
provisioning fences dependent phases; attempt expiry preserves unresolved
ownership rather than claiming cleanup. No deletion is implemented.

Independent review rejected the initial draft's unlocked internal worker,
unrestricted adapters, unbounded observations and cleanup assertions based only
on exit codes. Native transitions, arbitrary adapters, the internal worker CLI
and callable engine paths now explicitly refuse execution. The final scoped
review passes only preparation, inspection and fail-closed handling. The native
findings are fenced; they are not resolved by complete implementation.

The local host is macOS/arm64. Both Docker contexts, a direct Unix-socket probe
and the owner's own `docker ps` return connection failure at the Desktop socket.
`docker desktop start` reports that Desktop is already running, while no backend
process was observed. No daemon restart or container mutation was attempted.
Even a restored Docker connection still requires a verified x86_64 systemd,
cgroup-v2, rootless-Docker environment with actual offline runtime inputs. The
retained QEMU guest was not located in the scoped inventory, reused, started or
deleted; its ownership, disk hashes and complete lifecycle were not established.
The historical failure against the unchanged 0.8-second helper deadline remains.

Five distinct private generations exercised prepare → inspect → refused
provision. Each records `linux_required,x86_64_required`, the independent
implementation blockers, its failure and evidence retention. These are guard
checks, not concrete installation attempts or native rehearsal results.

| Requested case | Disposition |
|---|---|
| Installation → fresh installed inspection → rollback | Not run; native environment unavailable and concrete fixture engineering incomplete. |
| Acknowledged partial snapshots | Not run against a complete fixture; existing focused engine regressions remain separate. |
| Acknowledged partial configurations | Not run against a complete fixture. |
| Image load before acknowledgement | Not run against a complete fixture. |
| Rollback activation before acknowledgement | Not run against a complete fixture. |
| Coordinator-image mapped/incorrect peer UID | Not run; concrete fixture probe runner missing. |

`make check` passed **1,950 tests with 58 skips**, plus all **8 contract checks**.
The first full-suite invocation failed the existing untracked-runtime-source
guard while the new script was still untracked; after staging that script the
suite passed. Both results are retained. Changed-document local links and
`git diff --check` pass. These checks establish no Linux service, database,
installed-runtime, cleanup or performance acceptance.

| Gate | Disposition |
|---|---|
| Implementation | Incomplete. Lifecycle foundation only; native mutation paths fenced. |
| Rehearsal | Unavailable and unimplemented; no complete installation or interruption case executed. |
| Privileged host facts | Unchanged and incomplete; no VPS collection or installation performed. |
| Independent review | Passed only for prepare/inspect/fail-closed foundation; full fixture and whole-proposal approval unpassed. |

Private evidence retains per-generation manifests, creation/failure intents,
inspections, hash-chained journals, local runtime observations, both full-suite
logs and the scoped independent review. The
[machine record](protected-runtime-fixture-20261023.json) publishes redacted
dispositions and evidence hashes. No external fixture resources were created;
private evidence namespaces remain intact. No bulk cleanup, solver evaluation,
epoch, notification, public listener, VPS action, publication or budget spend
occurred. The owner still handles publication and all commits remain local.

Next engineering work is concrete fixture provisioning and resource receipts,
bounded frozen-source worker execution with inherited lifecycle locking, native
observations and invariants, the peer-UID probe, four interruption runners and
ownership-verified cleanup. These are implementation tasks, not facts that can be
waived because Docker is unavailable. The other 21 acceptance runners,
comprehensive external-effect recovery, privileged collector installation,
whole-proposal approval, epoch-policy replacement and public activation remain
outside this checkpoint. No protected-runtime installation authority is requested.
