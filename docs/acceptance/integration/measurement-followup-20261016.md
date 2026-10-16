# Measurement investigation follow-up — 2026-10-16

The owner authorized native acceptance protocols on the existing VPS and requested
the measurement investigation now. Production setup is deferred at owner request.
This follow-up inspected retained evidence and ran read-only host probes. It did
not repeat the already completed three-pair diagnostic or run new scored pairs.

## Findings

The [derived observations](measurement-followup-20261016.json) bind all six raw
files by their existing SHA256 identities. For each process identity (PID and
birth ticks), take its last observed user+system ticks while named `python` and
convert using the recorded clock frequency. The empty runs show 480,000,
440,000 and 380,000 microseconds of observed process lifetime CPU, compared with
authoritative totals of 490,194, 450,899 and 397,843 microseconds respectively.
Between first and last Python observations, the same processes accumulate
440,000, 400,000 and 350,000 microseconds. Thus CPU continues accumulating after
the process is observed executing Python; pre-exec runtime work alone cannot
explain these observations.

Process lifetime CPU survives exec, observations are coarse, and process names
are not function attribution. These totals cannot replace whole-domain accounting
or establish a precise startup/solve/cleanup partition. The existing evidence
does not justify choosing a different OCI runtime as the first correction.

A single native host probe used the retained generation-D worker context and
engineering Python interpreter with `-B -X importtime`, importing
`mldsafail.benchmark_v060.worker`. The process CPU delta was 0.05960615 seconds;
reported cumulative import elapsed time was 73,767 microseconds. This was outside
the container, without its interpreter/filesystem/sandbox conditions. It neither
explains the remaining cost nor proves a worker optimization. Local ARM64 import
observations likewise cannot establish native acceptance.

SSH succeeded; the host reported amd64, no queued user systemd jobs, and runc
1.5.1. `crun` was not found on PATH. Historical failed units remain retained.
Neither this unit inventory nor old cleanup receipts establishes current absence
for every owned domain. No daemon, container or service was created or altered.

## Next experiment to prepare

Prepare a separately frozen, reviewed instrumentation checkpoint that profiles
the retained worker's interpreter startup/imports and adapter execution inside a
fresh isolated worker domain. Keep the ordinary source/image as a control; bind
any instrumented derivative by context and image digest. Limit the explanatory
probe in advance and retain all attempts. Do not treat instrumented timings as
acceptance or rerun unchanged pairs to search for favorable numbers. Verify
current ownership before provisioning and independently verify final cleanup.

Only select a corrective artifact after identifying where CPU is spent. That
artifact still needs the complete fault suite and at least 30 sequential pairs
under the unchanged thresholds, then reference and hosted acceptance. No adoption
or default activation follows from this investigation.

## Artifact search

The historical `6b332cdb051a9da5651a2fc1e1e1bac0f7df0acf` backup helper is
present in Git and in the retained VPS release, SHA256
`d18afe91ab255a0c3601e519f2e4f05d4798a57cadcb5075af1be9892c65b6fa`.
It supports `--verify-restore`. The retained release has `compose.yaml`,
`compose.database.yaml`, `compose.private.yaml` and `compose.dev.yaml`, but no
`compose.production.yaml`. Resolve the rollback protocol's exact configuration
requirement before native rollback; finding the helper is not protocol acceptance.

Bounded local worktree/archive searches and remote named artifact inventories did
not find the required c67 candidate archive, 570 wheel, or original reproduction
base/study archive-and-provenance pair. A different retained participant wheel
was found and hashed; it does not match the required wheel. No replacement was
silently generated. These remain unresolved artifact prerequisites.
