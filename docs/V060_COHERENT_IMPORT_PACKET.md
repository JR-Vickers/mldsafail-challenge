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
