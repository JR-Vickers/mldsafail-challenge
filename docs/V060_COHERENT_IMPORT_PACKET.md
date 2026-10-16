# Inactive 0.6.0 coherent import

Base: `8bfe1b5941d6d86f3a67681466eab6300ce013aa`.
Authoritative inactive source: `9ccaa5fd16fd8a75bcb925cd821d1c7114ccaa22`.
Reviewed accounting source SHA256: `f7ad12e9442708824282e28f61954916aeea7a4d908914d55b639b865808323b`.

Import this branch's single source checkpoint onto the base or a compatible
successor. Do not merge the inactive preparation branch wholesale: it predates
root operational work and would remove newer reports, tooling and repairs.
Do not replay its accounting/helper synchronization commits: their exact
executable bytes are already present in the base.

Own additions are `src/mldsafail/benchmark_v060/`,
`src/mldsafail/benchmark_versions.py`, `research/mlwe_v060_preparation/`,
`tests/test_v060_*.py`, and `docs/MLWE_V060_IMPLEMENTATION_PROTOCOL.md`.
Own shared-file edits are explicit CLI selection/preflight/durable submission
intent and version-correct scaffold; web capability, version dispatcher,
cohort result handling and inert configuration; their CLI/auth regressions.
These edits were merged against the common ancestor `c84277b`, preserving
root's scaffold identity fix for both historical versions and existing tests.
The single conflict was the scaffold commit message; it now names the selected
version. Existing operational documentation, ledger, acceptance packets and
other engineering files remain unchanged.

Relevant original engineering checkpoints (already consolidated here):
`76afef7`, `6f24d40`, `2ec93c1`, `051174e`, `9db7225`, `b27c0e3`, `d59d358`,
`df02049`, `83e4543`, `7424b97`, `4a47974`, `b4d41f6`, `b0a6f91`, `919b79c`,
`53a007b`, `7c6ee6f`, `ecb4e9b`, `3656b4d`, `9ab1161`, and `d956d6b`.
Do not cherry-pick this list after importing the consolidated checkpoint.

No frozen 0.5.0 evaluator, benchmark, worker, lock, config, historical epoch,
reference cost or scoring rule changes. No database migration. No shipped
0.6.0 backend registry, default activation, owner adoption or production
exposure. Candidate rehearsal requires explicit private testing selection,
fresh epoch/source/image and actual accepted native prerequisite receipts.
Its authority always records `contract_adopted=False`.

The executable native callback remains
`python -m research.mlwe_v060_preparation.native_acceptance --config PRIVATE.json`.
Run only after exact-source accounting fault and 30-pair gates pass, in the
reviewed actual operator unit with matching private image/protocol/review
configuration. Local checks do not establish those native gates.

## Prospective worker artifact after the preserved generation-G failure

Generation G used the retained frozen 0.5.0 worker and completed all thirty
pairs, but failed both empty-worker CPU overhead and deterministic-fixture CV.
Retain that failed experiment; it cannot authorize adoption. The proposed
0.6.0 gate must next use a separately built, source-reviewed 0.6.0 artifact.
Preparing that artifact before the gate does not adopt its contract.

The proposed adapter applies the same address-space and CPU-affinity limits
locally. It no longer imports the frozen timing adapter merely to obtain its
limits function, so an empty contestant does not import the historical solver,
embedding and in-worker verifier. Solver modules remain available for approved
contestants; independent host correctness verification remains mandatory.
The proposed context excludes the historical worker executable. All interpreter,
imports, runtime and descendant CPU charged to the worker parent still count.
No subtraction, timing-boundary, fixture, threshold or scoring change is made.

Review/build/retain the new source-bound context and immutable image first;
then run the full native faults and thirty-pair protocol on that exact image.
A failure requires diagnosis and preserved evidence, not another unchanged
measurement attempt. The lean dependency path is a legitimate implementation
correction, not evidence that native overhead or CV will pass.

The followup prospective-worker branch also imports the exact root
`dd9ccc7:deploy/recovery_daemon.py` terminal bridge. This changes the prospective
CPU supervisor source identity to
`d0ca17d2e7f1353c1c352c059971291f9137a769024407d25e55bb563b406b15`.
The earlier `f7ad...323b` identity remains historical evidence only; new native
review/configuration/prerequisite receipts must bind the new identity. Worker
accounting window, harness, fixtures and thresholds are unchanged.

The reference/application callback reuses `config.image`; it must not build a
replacement after native acceptance. Its private prerequisites additionally
require exact `worker_image`, `worker_context_sha256`, and
`worker_source_commit` from the retained build-only artifact, alongside exact
supervisor identity and independently accepted fault/pair evidence. It prepares
and hashes the current context for equality, then inspects the exact loaded
image. Candidate authority repeats the same artifact binding against the fresh
epoch manifest. Missing, swapped or legacy artifact identities are rejected.

## Approved offline wheel inventory

The failed native-A build selected a newer published wheel with a hash outside
the frozen requirements. Preserve that failure; do not edit requirements.
Both native entry points accept optional private
`v060-worker-protocol.json` beside `config.state_root`:

```json
{
  "schema": "mldsafail.v060-worker-protocol.v1",
  "approved_wheel_directory": "/PRIVATE/RETAINED/WHEELS",
  "provenance_receipt": "/PRIVATE/RETAINED/PROVENANCE.json",
  "approved_wheel_sha256": {
    "cysignals-1.12.5-cp312-cp312-EXACT_RETAINED_PLATFORM.whl": "eccbcfd762de37daf4a01a0a77ef653561a153c48c2db9104916d36ebbd3cf24",
    "fpylll-0.6.4-cp312-cp312-EXACT_RETAINED_PLATFORM.whl": "05f43362f2803207a8a6dfe5bad41c64df2479cded1338490bad773ca78b5ba1"
  }
}
```

Replace the placeholder filenames with the exact retained native x86_64 wheel
names. Inventory must contain exactly one wheel for each frozen dependency,
with the unchanged package/version and reviewed native hash and CPython 3.12 native platform tags.
No extra files, symlinks, writable shared files or nonregular objects are
admitted. The CLI validates before driver mutation and each callback rechecks
before image build or reference execution. Copies are rehashed and included in
the worker context identity. Provide the same inventory to build-only and
later candidate acceptance; omitting or changing wheels changes the context
and cannot reuse the former native prerequisites. Private paths are not public
participant inputs. No historical dependency hash or frozen artifact is replaced.

The subsequent native architecture investigation established that the historical
benchmark-directory lock is ARM64, while the already reviewed
`deploy/worker-linux-amd64.requirements.txt` is the native x86_64 lock. The
prospective worker now has its own `requirements.amd64.lock`, byte-identical to
that approved native lock (SHA256
`35890cf7c5ed544124dc4cc86269009f11d029a5388d1627b6899e986650c1f0`).
No historical lock or worker changes. Its dependency hashes are:

- cysignals 1.12.5: `eccbcfd762de37daf4a01a0a77ef653561a153c48c2db9104916d36ebbd3cf24`.
- fpylll 0.6.4: `05f43362f2803207a8a6dfe5bad41c64df2479cded1338490bad773ca78b5ba1`.

Use those native hashes in the private wheel inventory, with the exact retained
filenames. The protocol additionally requires `provenance_receipt` pointing to
private schema `mldsafail.v060-offline-wheel-provenance.v1` with exactly
`source_image`, `architecture`, `wheel_sha256`, and `artifacts_sha256`.
The trusted operator must verify actual extracted bytes before publishing it.
It binds retained image
`sha256:6aaf71aa16e36631dec607f0726fb1e8d6f94954ce55a15a74ba4989777b5cfe`,
canonical architecture `linux/amd64`, exact filename/hash inventory, and actual
`/artifacts.json` digest
`0aaec49378c4b61c93fb5edf475fb619f5b7b7950406628283773ea6470eb01c`.
The sanitized provenance is copied into both worker contexts and their digest;
private path values are excluded. The prospective Dockerfile selects
`linux/amd64`; both callbacks verify actual inspected architecture and label.
The historical ARM64 hashes remain inadmissible for this prospective native
artifact. An unverifiable provenance receipt fails closed.
