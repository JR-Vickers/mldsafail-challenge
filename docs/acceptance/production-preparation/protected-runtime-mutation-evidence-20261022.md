# Mutation and termination evidence checkpoint — 2026-10-22

The installation proposal remains incomplete. This advances the
[previous checkpoint](protected-runtime-proposal-checkpoint-20261022.md), without
changing its historical result. The [machine record](protected-runtime-mutation-evidence-20261022.json)
binds source, verification, private evidence and independent review. It grants no
installation, native acceptance or launch authority.

Prerequisite substeps now record durable intent, observed completion and failure
observations, including failures while collecting the outcome. Backing allocation,
mountpoint creation, formatting, mount-unit creation/reload/activation, ownership
and controller enablement each have separate records. Fault injection covers
before mutation, after mutation and after acknowledgement. Unacknowledged creation
remains ambiguous; the engine never adopts it from matching contents alone.
Read-only substep classification distinguishes absent, acknowledged completion,
changed acknowledged resources and ambiguity. Installation reconciliation retains
its fresh observations and identifies acknowledged partial progress; complete
interrupted-install continuation remains unfinished.

Installation subprocesses and watchdog commands use the Linux observation
subreaper. Incremental birth records survive a missing final report, including a
stalled wrapper. Failed commands retain durable exit, log, containment and cleanup
observations. Escaped descendants prevent case success even when terminated;
missing reports, unsignalable descendants or uncertain termination retain blocked
ownership. The watchdog independently reads the owned cgroup's kernel populated
state after postflight, rejecting replaced or populated scopes. Cleanup declarations
alone cannot certify that scope empty.

Verification: `make check` passed **1,816 tests**, with **56 skips**, plus all **8
contract checks**. **72 focused tests** passed in the existing x86_64 emulator.
A separately owned systemd service, capped at **64 MiB and 32 PIDs**, exercised real
kernel empty/populated/terminated/removed observations and finished inactive.
Two earlier fixture attempts failed to migrate a process from the SSH session
into the delegated hierarchy; both services were stopped and their empty scopes
removed. The corrected fixture originated inside its own delegated service.
Those failed attempts remain failed records, not native acceptance.

Independent review found no concrete defect in the exact scoped implementation
hashes in the machine record. It explicitly withheld full-proposal approval.
No complete frozen installation/rollback/coverage packet exists for that review.

| Area | Disposition |
|---|---|
| Implementation | Improved mutation/termination failure evidence; incomplete full concrete install/rollback fixture, recoverable substeps across all installation operations, remaining scenario runners and complete acceptance packets. |
| Rehearsal | Focused emulator and kernel checks passed within the scope above. Complete runtime remains blocked by the retained 1.824-second cold helper result against the unchanged 0.8-second deadline. Local Darwin/ARM64, unavailable Docker daemon and absent Lima/Colima/Multipass provide no suitable native environment. |
| Privileged host facts | Still requires all-account scheduling/reference closure, other-owner restart policies, actual UID/delegation/control permissions and output feasibility. The bounded read-only refresh succeeded after the owner restored SSH; the host pin remained enforced. Passwordless sudo is denied, and cron/at collection errors remain blockers. Earlier connection failures are retained in the machine record. The [owner procedure](../../PROTECTED_RUNTIME_OWNER_COLLECTION.md) remains applicable. |
| Independent review | Scoped source changes reviewed without a concrete finding; full frozen installation proposal remains unapproved. |

Three answered local source-transfer archives (10,301,440 bytes) were removed
after retaining exact source manifests, test results and deletion intent. Guest
source copies were preserved because unprivileged process inspection encountered
an unreadable process directory; no successful guest retirement is claimed.
The guest was powered off and QEMU reaped. Its driver returned nonzero because
its running-state assertion observed that requested poweroff. The stopped guest
and guest copies remain named exceptions owned by this task and the repository
owner, with review due **2026-10-29**. Existing installation/rollback material,
scientific evidence and unknown historical resources remain preserved.

Budget remains $0. No VPS mutation, scientific evaluation, public listener,
notification, publication, production epoch or backup setup occurred. The four
areas above must be completed before requesting exact-byte installation authority.
