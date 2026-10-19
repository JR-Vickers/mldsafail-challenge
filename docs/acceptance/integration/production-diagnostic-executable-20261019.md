# Separate diagnostic executable checkpoint — 2026-10-19

This checkpoint implements the separate controller/callback and supporting
runtime. It does not execute a full rehearsal, create an epoch, activate delivery
or establish native performance. The investigation continues through the bounded
initial preflight and two generation slots, subject to exact packet review.

The controller exposes configuration, initial preflight, execution, cleanup-only
and report operations. The engine requires its supervisor's recorded same-process
birth and an exclusive entry marker. Durable budget starts precede configuration
verification, provisioning and imports. Setup, phase transitions, owned-command
publication/setup/capture and terminal substeps share absolute deadlines.

Each phase runs in a separately owned process. Lifecycle, worker, observer and
sampler registries remain separate. The worker starts at case zero, checks the
actual public enumerator/digests and unchanged reference/image, retains invocation
intent before Docker creation, and preserves the existing sandbox/resource limits.
Loaded measurement begins after the first public input delivery to its client.
Incomplete invocations and acknowledged removal remain distinguishable.

The disposable Compose configuration retains application/worker/database images
and limits, uses a separate PostgreSQL volume, binds listeners to loopback, and
removes coordinator epoch/socket mounts and dispatch. Actual Python/image/source
identities are checked. The canonical fixture has one private local PostgreSQL
creation/export intent; it preserves the ordinary token/hash, IDs, UTC timestamps
and fixed 24-hour expiry. No native instance or private epoch was created here.

Monitor hooks preserve ten-second subprocess timeouts, actual rendered user-manager
invocations and full-mode backup requirements. The unchanged read-only query runs
inside a diagnostic-only error-classification wrapper; only a fixed SQLAlchemy
failure marker distinguishes query failures from Docker/import command failures.
Unknown inspection remains unhealthy. Separate probes measure owned-client, Docker,
imports, connection and identical query costs. CPU/memory sampling and read-only
DB-wait sampling use independent threads.

HTTP instrumentation delegates ordinary hashing, revocation, expiry, scope and
dummy verification. Only approved route/status/correlation/timing fields persist.
Every received HTTP response, including errors, requires matching server evidence.
Private per-worker Unix sockets expose the authoritative failure flag even if both
record publication and its failure marker fail. They add no HTTP route. Final load
recreates the same web image/settings with heavy hooks disabled and proves their
absence before dispatch. The corrected harness retains durable request intents
and completions, refuses dispatch after slow publication, and keeps its existing
pacing/observation/latency/failure thresholds.

The historical scheduler is loaded from frozen checked source and runs unchanged
in an owned phase with the 600-second outer ceiling. No synthetic approximation
replaces its scheduling logic.

Terminal handling freezes recorded dispatchers before taking ownership snapshots,
requires the identity-bound daemon/worker barrier before cancellation, and retains
failed authority as a cancellation fence. Cleanup-only never provisions or resumes.
An independent read-only audit checks process/domain/socket absence, inactive units
and protected installation identities before terminating the budget slot.

Independent source review identified and corrected cancellation ordering/races,
missing absolute deadline propagation, slow-publication deadline resets, worker
stdin attachment, premature sampler cancellation, gated intent-only cleanup and
missing error-response instrumentation coverage. Focused tests include those
regressions, real disposable local PostgreSQL restoration, and authoritative
worker-memory publication-failure observation. Exact final check results and
native execution records are retained privately and summarized at investigation
close. This checkpoint grants no native admission without its actual frozen
artifact/configuration packet and independent review receipt.

The existing debit remains 900 seconds. No native preflight/generation, image
build, notification, private epoch or additional spending occurred during this
local engineering checkpoint. The earlier admission engineering report remains
historical; the controller it listed as missing is implemented by this checkpoint.
