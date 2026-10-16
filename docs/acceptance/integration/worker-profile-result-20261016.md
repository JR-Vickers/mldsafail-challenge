# Native worker profiling result — 2026-10-16

The independently reviewed [protocol](WORKER_PROFILE_PROTOCOL.md) completed once
on the existing native amd64 VPS, from frozen source `2fe0c2c`. Both invocations
used the unchanged retained generation-D worker image and fixed public tiny empty
fixture. Control and profiled workers returned exactly `{"candidate": null}`.
The driver and outer operator reported successful complete cleanup. The
[independent postflight](worker-profile-postflight-20261016.json) passed: 107
recorded domains and the new socket were absent; all 17 recorded clients and the
operator controller had no surviving exact process birth. All 41 historical
journals were unchanged, and the four protected running containers were unchanged.
Three unrelated stopped containers predated this probe and remain preserved.

The [sanitized result](worker-profile-result-20261016.json) binds source, image,
stream hashes and observations. Private raw streams, configuration, source bundle
and lifecycle journals remain retained locally and on the VPS. No production
service, benchmark contract, threshold, reference, default or score was changed.

## What the probe found

- The profiled worker's `main()` occupied approximately 3 ms cumulative elapsed
  time, after imports; the profiled worker-module execution occupied 81 ms.
- Profiler setup itself imported shared worker dependencies: `pstats` transitively
  loaded `dataclasses`, `typing`, `inspect` and regular-expression modules. Its
  cumulative import elapsed time was about 449 ms. The process CPU delta including
  profiler setup was about 471 ms; it excludes interpreter startup.
- Even after those profiler imports, the worker profile recorded 13 source
  compilation calls, occupying approximately 28 ms elapsed time.
- Read-only inspection of the retained image's ordered layers found no worker
  bytecode caches and no CPython 3.12 cache files for `typing`, `dataclasses`,
  `inspect` or `enum`. Their Python source files are present. Runtime has a
  read-only root and `PYTHONDONTWRITEBYTECODE=1`.

This supports preparing an artifact that precompiles the unchanged trusted Python
sources at image-build time. It does not prove that this change will pass the
measurement gates, or that compilation explains every excess microsecond.
Precompilation would preserve per-invocation execution and charge the complete
lifecycle; it must not cache answers or reuse a running worker.

## Limits and next checkpoint

The control domain consumed 809,675 microseconds; the instrumented domain consumed
634,739 microseconds. These are single explanatory observations using a different
attach sequence from the official harness. Ordering, filesystem cache state,
instrumentation and profiler-preloaded imports prevent a speedup claim or direct
comparison with previous official samples. cProfile function times and import
times are elapsed observations, not authoritative CPU partitions.

Prepare a separately frozen bytecode-build proposal, with source/cache identity
and interpreter binding, immutable artifact retention and independent review.
Then run the complete fault suite and at least 30 sequential pairs under unchanged
thresholds. Existing G/L failures remain. Reference and hosted acceptance would
still follow a passing measurement gate. No unchanged samples were retried.

## Local validation

`make check`: 969 passed, 13 skipped; 8 MLWE contract checks passed.
Focused lifecycle, CPU proposal/driver and operator tests: 49 passed.
A first focused invocation named two nonexistent test files and collected no
tests; the corrected invocation above completed successfully.
