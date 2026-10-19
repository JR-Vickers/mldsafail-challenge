# Diagnostic continuation: verified VPS, failed artifact admission

**Decision: unresolved findings; no baseline or full-rehearsal approval.** The VPS
identity is now verified, and read-only ownership/resource admission passed.
Artifact admission subsequently timed out and exceeded its remaining allowance.
Neither diagnostic generation, private epoch, diagnostic service, worker or
native evaluation guard started. No performance comparison is available.

## Corrected identity and successful host inspection

The owner confirmed the sole DigitalOcean Droplet is **178.128.17.58**, as already
documented in `OPERATIONS.md`. The earlier agent incorrectly selected an unrelated
SSH config entry for 143.198.195.245. Those failed connections are retained and
charged; no key from that unrelated address was trusted. The correct console
ED25519 fingerprint is
`SHA256:OtjIfXCrqewb9FTJ8jpU7Rq7aZL4P8P7U0dKZ8DoB5w`.
A private pinned known-hosts file matched it before authentication using the
repository's documented `mldsafail_vps` identity and deployment account.

The read-only snapshot matched all seven retained container/image/PID/start
identities, current release, retained receipts and old C socket absence. No user
manager jobs or pending evaluations were found. Four historical slices were
present and recursively empty. The existing backup timer was waiting until
2026-10-20 03:15:03 UTC, outside the proposed window. Available disk was about
31.4 GiB and available RAM about 1.32 GiB. The retained Python 3.12.10 executable
matched SHA-256 `bb51835a056505237a67178912a78185ce18a378d65cc3a97f2bc1ed1629010c`.
Independent source/evidence review verified this snapshot; it did not certify
native artifact admission or performance.

## Engineering completed before artifact admission

Checkpoints `c9caf56`, `f8a1f88` and `8351bab445dd0c46b01d76793d635d4493b0686f`
retain append-only preflight reconciliation, actual unit reconciliation and
interpreter discovery, frozen monitor imports and an owned evaluation guard.
The original failed ledger entries remain unchanged. Continuations must be
explicitly reconciled, ordered and charge-preserving; unknown, orphaned,
interrupted or unlisted starts fence dependent admission.

Independent packet review found that a new private lock did not serialize
existing host consumers. The packet now selects the existing host load lock.
The diagnostic guard holds a bounded PostgreSQL transaction with the evaluation
advisory mutex and a SHARE lock on `evaluation_jobs`, checking zero pending jobs
after acquisition. The table lock also fences historical claim implementations
that predate the advisory mutex. No row, lease or epoch is created or modified.
Unexpected guard exit cancels the engine through the owned daemon barrier.
Cleanup uses exact connection tag/PID/birth; unacknowledged creation remains
fenced rather than becoming a false absence assertion. This guard was tested
locally and never started against the deployed database.

Independent source review found no remaining concrete blocker in these changes.
Three real local PostgreSQL guard tests passed, covering blocked claim writes,
permitted reads, cancellation, server timeout, positive interrupted-acquisition
recovery and rejection of unacknowledged cleanup. `make check` passed with
**1,175 tests, 15 skipped, plus eight contract tests**. The separately reviewed
baseline packet binds 2,493 actual source files, nine configuration files, the
original fixture and reference, exact historical scheduler, five immutable images
and archive digests. Its frozen schedule totals 1,820 of 2,100 work seconds.
These are engineering checks, not native measurement results.

## Failed artifact gate and actual budget

The remaining initial-preflight allowance was 48 seconds. The agent attempted
to upload a roughly 101 MB archive containing the complete clean source checkout,
Git metadata and private inputs, then validate actual native source/import/image
archives. This transfer/check did not produce a success receipt. Local SSH timed
out at 36 seconds. The agent failed to bound subsequent reconciliation and
independent review inside the remaining allowance. The full interval to the
independent negative review was **102.978165042 seconds**, rounded charge **103**.
This is an agent deadline failure, not evidence of an unhealthy VPS or application.

| Debit | Seconds charged |
|---|---:|
| Existing debit | 900 |
| First wrong-target SSH admission | 33 |
| Owner-requested wrong-target continuation | 32 |
| Correct-target host admission/reconciliation | 187 |
| Failed artifact admission and verification | 103 |
| **Aggregate** | **1,255** |

Initial-preflight work totals **355 seconds**, exceeding its 300-second allocation
by **55 seconds**. This violation is preserved, not hidden by a reset, a generation
start or reclassification. The aggregate ceiling remains 7,200 seconds, but unused
aggregate time does not itself waive the initial-preflight ceiling. Both generation
slots remain unstarted and fenced. No retry is authorized by this receipt.

## Cleanup and retained uncertainty

A subsequent bounded read-only cleanup check matched the newly created source
root's recorded device/inode/owner and confirmed the helper PID and both proposed
generation roots absent. It stopped at unexpected partial extraction and retained
those files. No successful source-root deletion or complete native artifact
verification is claimed. The negative independent receipt has `passed:false` and
`cleanup_verified:false`. Existing deployment identities were verified during the
host snapshot, not re-audited after the interrupted transfer.

Retain `/home/mldsafail/.mlf-diag-20261019` as a targeted interrupted-upload
exception: owner **jarrett**, review **2026-10-26**. It needs an exact inventory,
process/mount/inactivity check and identity-bound removal or validation before
reuse. Never start a generation from the partial copy. No new daemon, worker,
monitor or volume was provisioned by the artifact helper; its reviewed source
only uploads and validates files and performs read-only inspection.

The disposable local guard-test PostgreSQL was stopped; PID file, socket and
listener absence were verified before removing its exact temporary root. The
redundant local source clone and large upload archive were removed after clean
source/open-file checks. Compact manifests, package hash/size, private inputs,
transport/cleanup evidence and original Git checkpoints remain. The canonical
fixture survives unchanged, SHA-256
`04fa195ff541d8c8dc2199152f610054e984836fca4ec365c5765f7833b335b0`,
with fixed expiry **2026-10-20 07:20:54.815946 UTC**. Do not recreate or renew it.
Private compact evidence is under
`results/production-diagnostics/20261019/native-session/`.

## Required next evidence and decision

Monitor failure classes/component timings, HTTP route/condition distributions,
legacy dispatch/elapsed time, worker prefixes/contention and both 1,560-request
final validations remain **unmeasurable in this attempt** because artifact
admission failed. No application/monitor cause was established, no such fix or
image rebuild was made, and native pacing remains unvalidated.

Any further native work needs an explicitly revised bounded continuation that
preserves the 1,255-second charge, addresses the failed preflight ceiling and
unverified partial upload, and stays within the 7,200-second aggregate. Before
native admission, prepare a smaller reviewed transport of the actual executable
closure (for example a clean sparse checkout that omits unrelated scientific data)
and demonstrate its transfer/verification ceiling. Rebind all actual inventories
and review the exact packet. This is not permission to weaken inventory checks,
reuse the partial copy, reset ledger history, renew the fixture, start a third
generation or create a private epoch.

Additional spending remains $0. Delivery, public activation, publication,
recruitment, backups and Measurement 0.6.0 adoption remain separate. All commits
are local and unpushed.
