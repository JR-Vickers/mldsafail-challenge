# Disposable diagnostics: stopped before provisioning

Updated 2026-10-18. **Full-rehearsal approval is not ready.** The authorized
continuation found a disk-floor failure before generation one. Zero additional
spending, zero new diagnostic generations, zero image builds and zero private
epochs. No disposable service or heartbeat was started. Nothing was pushed.

## Frozen implementation and independent review

Source checkpoint: `f194bfaa69baff0f47b6137215e02ea5b693d138` on local `main`.
This repairs the load harness and adds a stop-only read-only image footprint
preflight. Application/monitor code, hashing and authentication protections,
worker/evaluator bytes, profiles, costs and thresholds remain unchanged. The
existing immutable image identities and archive provenance remain those in the
[C terminal receipt](production-rehearsal-20261016.md#c-terminal-disposition--2026-10-18);
no new candidate application image is claimed. The image-footprint preflight was
executed from the earlier clean checkpoint `439d91d`; its script bytes are
unchanged in the final implementation checkpoint.

The load harness now uses a separate ownership observer and independent owned-client
and evidence registries. Initial inspection must complete before dispatch; failures
and observations older than five seconds stop dispatch. Refresh starts every 2.5
seconds to leave room for a nonzero check duration within the five-second freshness
limit. Absolute deadlines prohibit catch-up, with a 100 ms lateness limit applied
to each dispatch. Ten request threads retain the existing two-second timeout,
1,500 anonymous plus 60 authenticated requests, nominal 300-second window and
original latency measurement point/p95/p99 thresholds. Reports retain measured
phase elapsed time, dispatch/start/end, queue delay and incomplete requests. A
five-second drain is bounded. Surviving requests/observers make the phase invalid.
Completed requests publish partial evidence during the phase; sanitized evidence
publication failures invalidate acceptance. The API now requires explicit
`read_only_health=True` review before starting an asynchronous observer. The
production caller and pure CLI checks opt in. Older staging/disposable callbacks
write lifecycle journals and now fail before observer/request startup until they
receive a separate ownership-observer redesign; their outer entrypoints may have
already performed setup. This is a compatibility restriction, not validation of
those older workflows. Progress callbacks must be nonblocking; a pathological
callback can survive only in a phase already marked termination-incomplete.
Observer cancellation reaches owned subprocesses, and a 35-second quiescence
barrier precedes lifecycle cleanup's registry snapshots. Failure to quiesce fences
cleanup rather than racing new process births against it.

Independent source review identified and resolved the first draft's cleanup race
and paired-request timing gap. Focused tests cover those corrections, registry
isolation/ingestion, failed/slow/stale observation, no catch-up, queue delays,
measured elapsed time, incomplete reads, bounded termination, sanitized errors,
monitor error handling and full-mode backup requirements. Independent reviewer
ran 88 focused tests on the final code. Final `make check`: **1,097 passed, 13 skipped**, plus **eight
contract checks passed**. These are local engineering results; native observation
cadence and HTTP performance remain unvalidated.

## Demonstrated resource blocker

A separately reviewed script streamed and hashed layers from the five required
retained archives without extraction or remote writes. It deduplicated only
byte-identical layer content and excluded sparse entries from its regular-file
lower bound. Execution was bounded by a 60-second alarm; no retry occurred.

| Observation | Bytes |
|---|---:|
| Free space at completed scan | 5,731,893,248 |
| Required free-space floor | 5,368,709,120 |
| Available headroom | 363,184,128 |
| Distinct unpacked nonsparse regular files | 1,184,630,872 |
| Deficit before all other overhead | 821,446,744 |

The required image files alone exceed headroom by about 783 MiB. Content-store
copies, metadata, PostgreSQL and transient writes require additional space. A
lower-bound failure is decisive; a lower-bound pass would not admit provisioning.
The earlier archive-size scan was preparatory and is not an allocation estimate.
Do not delete retained evidence, reuse C's daemon/database/cache, weaken the floor
or purchase another host to bypass this stop.

## Retained evidence and final scoped audit

Private evidence stays under `results/production-diagnostics/20261018/`, ignored
by Git. Frozen C cleanup/diagnosis receipt hashes were rechecked locally against
the published terminal receipt. A separately reviewed final read-only VPS audit
then confirmed nine C receipt entries (eight distinct paths) unchanged, all four
protected container/image identities unchanged, the exact C daemon socket absent,
C monitor MainPID zero with empty cgroup, timer inactive, delivery disabled and
no user jobs. Available disk/RAM at final audit: 5,731,880,960 / 1,497,260,032 bytes.
Independent result review passed. This does **not** claim a new full audit of
C's 2,791 historical cgroups or 2,793 births. No new owned diagnostic resources
exist because no creator was invoked; no cleanup mutation was needed.

| Private artifact | SHA256 |
|---|---|
| `storage-footprint.json` | `0ef7a07e06eba291174f2f5cebf434fe639f57b8440fdc01594552e2c66b20cc` |
| `independent-load-source-review.json` | `8ca9966b07422c9f12ef04d0e723908a75582bed454b5d55c56ea650c6347c4c` |
| `independent-final-load-delta-review.json` | `4daaffb7e1fe10288f0dae7fef18f34edacd4d708933192c6bc3986bb8284421` |
| `readonly-postflight.json` | `b1f5e260fc667cb6d1108b804e22b83c70f4423b9fd914a0cf5bd925060a44a8` |
| `independent-readonly-postflight-source-review.json` | `0e028d5b2404bd96415de749fb8cebd49d7b92b264ea53d405f6430edfa3ae8c` |
| `independent-final-postflight-review.json` | `59baed3bb7cbf48cbda0bfa978b1f65739674ee3dfc274755f069fee2c0caa60` |
| `make-check-final.log` | `321f2bd071428cfc55e44499018f61449d8b998f9ac6eb5648db657be4a5a9ca` |

The private disposition inventory binds source/evidence and debits **900 seconds
conservatively** for all native read-only preflights, SSH and audits. This is not
measured utilization. Carry this debit forward against the two-hour aggregate
budget (6,300 seconds remain); local engineering is excluded. Storage still
prohibits provisioning regardless of remaining time. No baseline or post-fix
generation has been consumed, and no automatic retry is scheduled.

## Remaining diagnostic and approval work

The monitor exception and authenticated-read bottleneck remain unclassified;
CPU contention/authentication cost and ten-second monitor timeout remain
hypotheses. The isolated baseline comparisons, 60-second legacy experiment and
post-fix idle/worker 300-second phases were not performed. No causal production
monitor/application fix or native improvement claim is supported.

A separate synthetic no-epoch callback remains incomplete. Its exploratory draft
is retained privately and excluded from tracked runnable code. After resolving
capacity within the owner's retention and spending constraints, implement its
component/server timing instruments, immutable common fixture/token inventory,
actual instrumented legacy-source binding, full import/configuration/image
inventory, external budget/lifecycle admission and cleanup; freeze and independently
review the exact executable protocol before any generation. Preserve production's
fresh-epoch requirements. Follow the [bounded diagnostic protocol](../../PRODUCTION_DIAGNOSTIC_PROTOCOL.md).

Only after successful diagnostic comparisons can a full-rehearsal approval packet
bind the final source, images, reviews, pacing evidence and cleanup, plus an exact
fresh-epoch protocol repeating application, rollback/forward, faults, both load
phases, scheduled monitor, notification/failure/recovery and missed-heartbeat
checks. Owner email confirmation and check pausing remain explicit. That protocol
is not frozen or authorized by this packet. No replacement epoch or full rehearsal
is requested now. Backups remain indefinitely deferred; production activation,
measurement, historical reproduction, live OAuth/trusted TLS, public launch and
0.6.0 adoption remain separate gates.
