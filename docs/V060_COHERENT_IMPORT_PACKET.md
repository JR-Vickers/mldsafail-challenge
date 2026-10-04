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
