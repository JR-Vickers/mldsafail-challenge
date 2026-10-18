# Disposable diagnostics protocol

This is the bounded preparation specification for diagnosing failed rehearsal C.
It authorizes no replacement epoch, private evaluation, notification delivery or
production activation. The final native protocol must name a separately reviewed
callback and bind the complete clean source/import/configuration inventory before
execution. An unimplemented step or missing binding stops admission; this document
alone is not an executable admission receipt.

The retained local cleanup and diagnosis receipts match their published SHA256s:
`c6ad518fa8317e3a2c54a97dc07644b035b073e3ea7fa72e12368b8639d801e8`
and `197307219b395639febf303d3ac8540badf3a4d9bb231baa56d709d5f74edd9e`.
Frozen C source is `a06bf4aa8e29b19fc81841f12cb95388aa1d13e1`;
`69cbd61` added diagnostics after C and was never installed in that run. Historical
receipts establish retained evidence, not current host absence or ownership.

## Admission and budget

Use only the existing VPS, at zero additional spending. Admit at most two fresh
generations: baseline and post-fix. Each has a 3,600-second native wall budget
including provisioning and cleanup; prohibit new work after second 2,700 and
reserve the final 900 seconds for cleanup. Charge partial/failed generations and
all setup/cleanup to the 7,200-second aggregate ledger. Image builds and local
engineering are excluded. No automatic retries or third generation are allowed.
Use monotonic deadlines in the controller; native callbacks must receive the
remaining budget rather than resetting it. Loss of ownership, insufficient budget
or a failed resource floor stops dependent work immediately.

Before provisioning, independently reconcile active evaluation, maintenance,
build and diagnostic jobs; protected staging container/image/process/domain/root
identities; available disk and RAM; and old generation absence. Require at least
5 GiB free on the relevant Docker/evidence filesystem and 128 MiB MemAvailable
throughout, preserving stricter existing admission floors. Hold the existing
host serialization lock throughout provisioning, execution and cleanup. Bind its
identity and the fresh operator unit, daemon unit, worker slice, short socket,
private evidence root, fresh PostgreSQL volume and monitor unit in the review.
Do not reuse C manifests, mounts, database volumes, domains or process births.
Never edit retained hardlinked source/context files.

The exact reviewed packet must include the full source commit and per-file
SHA256 inventory; imported helper closure; callback SHA256; configuration inventory;
public-workload inventory/order; reference solver inventory; immutable application,
worker, database and proxy IDs; image archive checksums/provenance; protected
identities; budget ledger; all deadlines; cleanup and independent postflight paths.
Baseline and post-fix use identical data, synthetic token, workload order, process
limits and configuration. Application images may differ only if a demonstrated
bottleneck justifies a reviewed application fix; worker/evaluator bytes never differ.
No implicit substitution of tags, source paths or installed helper versions.

## Synthetic fixtures and worker workload

Initialize a new application schema in the fresh PostgreSQL volume. Populate a
synthetic user and ordinarily hashed/scoped/expiring token using existing app
helpers, plus deterministic synthetic submission and lease rows. No accepted
submission, benchmark result, private epoch, reference cost or ranking is created.
Lease rows must be isolated from dispatch: keep coordinator scheduling disabled
while retaining its deployed container environment for the read-only monitor exec.
Bind row states, lease durations, row counts and sanitised fixture inventory.
Healthchecks and alert delivery must be disabled in both config and effective
rendered units; retain proof. The permanent external check stays paused.

Use the unchanged worker image
`sha256:6aaf71aa16e36631dec607f0726fb1e8d6f94954ce55a15a74ba4989777b5cfe`
and unchanged `examples/mlwe/primal-lll/solver.py`. Precompute and freeze an ordered
list from the existing public 0.5.0 development cases, using only public inputs
and public verification. Fix the sequence, repetition count and timeout policy
before execution; do not select cases in response to timing. Worker invocation
must use the existing sandbox, resource limits and durable owned lifecycle.
A controller may repeat the frozen sequence to fill a phase, stopping at its
predeclared phase deadline; record the exact prefix and every incomplete invocation.
Never submit this workload through the private acceptance path. All receipts say
`diagnostic_only`, `private_acceptance=false`, `ranking=false`.

## Ordered independent measurements

1. With no worker, invoke the actual rendered user-manager monitor three times
   sequentially; repeat three times under the fixed worker workload. Capture
   invocation exit code, phase-relative elapsed time and bounded private logs.
   Keep the ten-second per-command timeout. Record timeout, command, query and
   parsing failures separately; unknown/failed inspections stay unhealthy.
   Independently time owned-client launch, Docker inspection and exec, Python
   imports, connection establishment and the identical read-only lease query.
   Component probes supplement actual unit results and never replace them.
2. Stop the monitor and prove it inactive before HTTP measurement. Compare the
   same anonymous and authenticated read routes while idle and under the same
   worker sequence. Fix counts and dispatch order in the final packet. Correlate
   bounded sanitized server timing, verification duration, database waiting,
   CPU/memory and response class. Never retain tokens, Authorization headers,
   SQL parameters or exception text containing credential material. Every request
   retains ordinary verification, expiry/revocation/scope and dummy verification.
3. Run the legacy scheduler once for a nominal 60-second diagnostic phase under
   a 600-second outer ceiling. Instrument scheduled/actual dispatch, HTTP start/end,
   executor queue delay, ownership observation duration, actual phase duration and
   unfinished requests. Preserve all partial evidence; reaching the ceiling does
   not authorize retry. This is diagnosis, not final load acceptance.
4. Only in post-fix generation, after isolated probes, run the corrected harness
   sequentially idle and under the fixed worker sequence: each schedules 1,500
   anonymous and 60 authenticated reads across 300 seconds, ten request threads,
   two-second HTTP timeout. Include both full phases in the 2,700-second work
   allowance. Do not start either without enough time to finish and clean up.

A corrected phase requires initial complete ownership inspection; one observer with
its own client registry/journal refreshes within every five seconds. Failed, raised or
older-than-five-second observations stop dispatch. Use absolute monotonic request
deadlines; lateness above 100 milliseconds invalidates the phase and stops dispatch
without catch-up. Drain within a declared bound and record every unfinished request.
Retain original latency sample origin and limits: all 1,560 complete, zero read
failures, zero floor failures, p95 <1 second, p99 <2 seconds, valid observation and
pacing. Instrumented probes cannot stand in for this validation.

## Stop, retention and later gate

On any fault retain the partial receipt before cleanup; never relabel it passing.
Stop observer and monitor, stop services and workers, then stop the owned daemon
using existing identity-bound lifecycle barriers. Preserve failed database volume
and private evidence offline. Independent postflight must verify all recorded
process births, domains and socket absent; timer/service inactive; no user jobs;
protected staging unchanged; and retained inventories/checksums intact. Failure to
prove cleanup is an incomplete outcome requiring explicit resolution, not a retry.

After focused tests and `make check`, freeze a clean checkpoint before native
execution or affected application builds. Require independent review of that exact
source/protocol. Native amd64 application rebuilds use Python 3.12.10 and the existing
lock, retain archives/checksums/actual IDs and recheck rollback/evaluator compatibility.
Document demonstrated causes, unsupported hypotheses, failed comparisons and cleanup.
Only then present the owner a concrete packet for one separately authorized fresh
full rehearsal. That later protocol repeats fresh-epoch application, rollback,
fault, load, scheduled monitor, notification and cleanup checks; it preserves owner
email confirmation/check-pausing steps. Backups remain indefinitely deferred.

## Implementation disposition — 2026-10-18

Native provisioning stopped before generation one. A reviewed, read-only scan of
all five required retained image archives found 1,184,630,872 bytes of distinct
nonsparse regular-file content after decompression. The host had 5,731,893,248
bytes free, only 363,184,128 above the protected 5 GiB floor. The lower bound
exceeds headroom by 821,446,744 bytes before image content-store copies, metadata,
PostgreSQL or transient writes. This is a resource-floor stop, not permission to
retire evidence, reuse C, lower floors or buy another host. No generation,
service, monitor, worker, image build or epoch was started.

Checkpoint `f194bfaa69baff0f47b6137215e02ea5b693d138` implements the corrected
load harness and reviewed stop-only storage preflight. The observer refreshes
within five seconds (starts at 2.5-second intervals to leave execution headroom),
uses independent client/evidence journals and stops dispatch on failure or stale
completion. Cancellation reaches owned subprocesses, and a bounded quiescence
barrier precedes cleanup's client-registry snapshots. The scheduling window and
bounded drain are measured; partial requests and missed deadlines remain failed.
Focused tests and `make check` pass. Independent review binds source identities
and tests; it does not prove native cadence or performance.

A standalone diagnostic callback was explored but is **not implemented/admitted**.
The unreviewed draft and preparatory helper/tests remain private under
`results/production-diagnostics/20261018/`. They were not executed natively and
are excluded from runnable tracked code. Remaining work includes complete monitor
component and sanitized server timing instruments, immutable common synthetic
fixture/token identity, actual instrumented legacy-source binding, complete
external lifecycle/budget admission, and independently reviewed native cleanup.
Do not relax the production callback's fresh-epoch requirements to replace this
missing implementation. Storage must be resolved before provisioning; the draft
must still be completed, frozen, tested and independently reviewed afterward.

The isolated monitor/authentication/legacy comparisons and both corrected native
300-second phases remain unperformed. Monitor and application causes remain
unproven. The tracked code changes no monitor timeout, authentication verification,
hashing, evaluator, worker, scientific score, profile or acceptance threshold.
No fresh full-rehearsal authorization is requested: the prerequisite diagnostic
comparisons and exact executable full-rehearsal packet do not yet exist.

See [the dated disposition](acceptance/integration/production-diagnostics-20261018.md)
for retained evidence hashes, end-state checks and the remaining gate.
