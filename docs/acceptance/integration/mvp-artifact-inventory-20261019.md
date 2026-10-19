# Retained MVP artifact inventory — 2026-10-19

Local read-only inventory against main `89ffc7918c33c753326b6bcbbf3ca6727a42340f`.
No VPS contact, transfer, image build/load, evaluation, epoch, activation or
notification occurred. Archive members were read in place, never executed or
extracted into an environment. Exact private paths, archive member inventories,
record hashes and reproducible local verification are retained in an ignored
private inventory; public location descriptions below are deliberately sanitized.

## Proposed application artifacts

Source identities: candidate **`1c9ca9eff3a1133aa8b508a35f6b174a587a4f01`**;
compatible rollback **`26c5f2f4bc771b319ffccc2cdcb1c735eaab4176`**.
All four images are Linux amd64, Python 3.12.10. Image IDs are local OCI identities,
not registry digests. The table's SHA256 is for the uncompressed saved image tar.

| Role | Image ID | Expected archive SHA256 | Availability / recorded location |
| --- | --- | --- | --- |
| candidate web | `sha256:31383f86703dcc8b4ba4c36acd8933ed5bf306ee98fa129e50d4625dd4c12a4b` | `e02d119cabfab72f9e11eac248b087fe15beeb37a122e8e06feeb0970c2dc390` | Recorded on VPS but currently unverified; B/C release-artifact store |
| candidate coordinator | `sha256:b3f27a3b1b3d25d808f21ac56f2653dc5bd29f77dd9903acfd84969080c0d0a4` | `e71474c16cc62529d1418fb587449833b58a3e603f0f0a29c5bbb2cacf5fd583` | Verified locally; retained compressed transfer |
| rollback web | `sha256:035956fde36b9131888ee8f29ab3178a143bce67dfb6419b16d30a76c31a7428` | `68e01b745177b9af16452a75e7d1eb8035467d4af2edc306b211c3021cdc50bf` | Recorded on VPS but currently unverified; B/C release-artifact store |
| rollback coordinator | `sha256:f1eed8b81d932b721950a0f15c6621c658b08e4ba437d2b4f4cbebfaf884f23e` | `758b42565f0017c5a5f01fdb1a32fce49c23cd0ea68fd162aa5b4d69a6c2becc` | Recorded on VPS but currently unverified; B/C release-artifact store |

The complete candidate coordinator transfer has compressed SHA256
`945050bb6df486db319f15d3f4d5d56ee7aff133b0544f29b0b629ab10bb64d0`.
Its decompressed hash matches the table; all 19 OCI blobs hash correctly, the
recorded image index exists, and its configuration source label matches the full
candidate commit. Build B/C report hashes match the artifact index; recorded
inspection IDs, architecture and full source labels agree for all four images.
Only the coordinator archive itself was available for that local image check.
The other local compressed transfers terminate with EOF errors. **Complete local
web, rollback and worker archives are missing**; truncated bytes are failed
transfers, not alternative release images. No artifact was regenerated.

## Worker and service dependencies

| Role | Immutable image ID | Expected tar SHA256 | Platform / availability |
| --- | --- | --- | --- |
| Frozen MLWE 0.5.0 worker | `sha256:6aaf71aa16e36631dec607f0726fb1e8d6f94954ce55a15a74ba4989777b5cfe` | `c259e98683e699000d46eb2da37dce4d8ae205c9349e349fc553e2c32c09b40c` | Linux amd64; recorded VPS worker export, currently unverified; local gzip truncated |
| PostgreSQL | `sha256:639ab7ceb90e13123085b741fb31ef493fba25463002f6da665352e7b534b652` | `7afbae099cf728bd5ee01c933261d27f4687c1d4c1c8165980a73c50b9cc1270` | Linux amd64; recorded VPS service-artifact store, currently unverified |
| Caddy | `sha256:6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b` | `db888297a9dcb25f4ed8f93c6b855ce8fa3c15fce15450dd843134cdf79bd806` | Linux amd64; recorded VPS service-artifact store, currently unverified |

Worker trusted fingerprint is
`b6f92231843fcb90695669108f0cc02d747ae0614eb9b3d25cddae602e092eee`.
The release manifest binds that fingerprint to candidate source and the unchanged
worker ID; C records native execution and audit with this worker. The original
worker build commit/label is not established by the local release manifest:
recover its original provenance and inspect the complete saved image before
claiming full source-label verification. Do not assign the application commit to
the worker or substitute an ARM64 package-test worker or proposed 0.6.0 image.
Service upstream source commits are not established here; immutable image IDs,
archive hashes and existing Compose registry pins are the recorded identities.

Verified local dependency files (also equal at candidate, rollback and main):

| File | SHA256 |
| --- | --- |
| `uv.lock` | `58d4165666f7461539ed348cf696a00524c0f356b7d23f874c2e4e2bb5cea329` |
| `deploy/worker-linux-amd64.requirements.txt` | `35890cf7c5ed544124dc4cc86269009f11d029a5388d1627b6899e986650c1f0` |

ARM64 development evidence does not establish native amd64 timing compatibility.
The evaluator's epoch, host, reference costs, trusted fingerprint, worker and
cohort must all match; a new production binding is still missing.

## Participant package, source and starter

These are distribution **0.5.1**, supporting benchmark **0.5.0**. A wheel filename
is not a scoring-contract version. Selected integration artifacts have source
`26c5f2f4bc771b319ffccc2cdcb1c735eaab4176`; the wheel is byte-identical to the
installed `0375e1c5499fb173b80847fb7081fec5217bf88a` artifact.

| Artifact | SHA256 | Local result / recorded location |
| --- | --- | --- |
| Integration wheel, 184,636 bytes | `ed002b7b2440efdf99936a9eb81df3010fa5d1b3f77c25b7e546eb15f7d62194` | Verified locally against final-package and install receipts; protected integration artifact directory |
| Integration source distribution, 44,276,642 bytes | `d0a4c9afb946ae395090e8778efb09ed644ef8432a23c9b62fc105455643c1e8` | Verified locally against final-package receipt; same protected directory; publication blocked pending packaging review |
| Embedded primal-LLL starter | `4d8df806feb996e35f7d99db71d8aa86154c3901dde786edccc4d3f80b207ed7` | Verified wheel member; byte-equal to current tracked starter |

The wheel is tagged `py3-none-any` (platform-independent Python); package metadata
requires Python >=3.12, while benchmark reproduction binds Python 3.12.10.
Wheel member inspection finds no diagnostic-named paths. This is a scoped archive
inspection, not a comprehensive secret scan or a fresh install. The sdist contains
research diagnostic scripts and operator/test material; do not publish it unchanged
as a minimal participant source release. A filtered, reviewed source package and
its new checksum would need separate preparation and validation. Retain the old
artifact and its evidence.

**Conflicting evidence:** the current `dist/` wheel and
[deployment checksum](../../../deploy/participant-0.5.1.sha256) both identify
`da4033bd75a826275f7ee4951f0d6c1f0185971a66bfe8c0864a7016cab2ede9`,
not the integration-tested wheel. The current dist sdist hashes to
`4fa6f38c61a7bc0b45beac806f25068e9d6225f9c7015b950cd5328eb4275332`,
not the retained integration source. They are distinct artifacts despite identical
version names. Their suitability is not established by the integration install
receipt; choose the tested wheel explicitly and prepare a matching publication
checksum, or review the other artifact independently. Do not silently overwrite
or relabel either.

## Source comparison and retention reconciliation

Local candidate source tar verifies all **2,442** manifest-listed files; matching
rollback source tar verifies all **2,394**, with zero mismatches. Full source commits
are present in Git. Tar SHA256s measured now are respectively
`4396e3bd2fb5b1acd885add5e00b822531b3fcfb332b5a6bff2d1432dbb87720` and
`2037d9721e298087309a6ac19efb721498556a3a3aec0392f8adc330a2d0d5b7`;
these whole-tar hashes are new inventory observations, while member checks use
historical manifests. They are operator source contexts, not participant packages.

Candidate, rollback and main have identical `src/`, `config/`, migrations,
primal-LLL starter, application Dockerfiles, `pyproject.toml`, `uv.lock` and
production Compose bytes. Candidate-versus-rollback runtime equality explains
why historical rollback demonstrates artifact switching rather than a different
implementation. The original incompatible rollback `4602f45` remains excluded.

Main adds operator/diagnostic changes, tests and documentation. Changed deployment
helpers are `host_checks.py`, `owned_client.py`, `owned_daemon.py` and
`render_operator_units.py`; current rehearsal and epoch controllers also differ.
Thus no application rebuild is justified by the compared runtime paths, but any
future operation using main needs source-bound validation of its actual helper
closure and configuration. The coordinator Dockerfile copies a broad checkout:
a main rebuild would create a different artifact, even with unchanged application
bytes. Keep diagnostic tooling outside the proposed participant release.

The [cleanup receipt](lean-launch-cleanup-20261019.md) retains the running private
installation source `6b332cdb051a9da5651a2fc1e1e1bac0f7df0acf` and its installation
rollback `b4d212da3109b7716eb41553986848e377fb5b3d`. These are **not** the proposed
preview pair. The candidate/matching rollback set is a named retention exception,
review due 2026-10-26. Both locally retained compact-cleanup and final-audit record hashes match the
published cleanup receipt. Historical cleanup verification is not proof of today's
remote availability. No remote paths were probed or any retention state changed.

## Evidence by claim

| Claim | Evidence and limit |
| --- | --- |
| Installation | [Local verification](verification.json) binds wheel, starter, isolated import and dependency receipts; macOS ARM64. Fresh selected-release production install is unverified. |
| Correctness | [C rehearsal](production-rehearsal-20261016.md) records independently audited reference result and seven declared fault assertions. Failed A and fenced B remain separate outcomes. |
| Scoring/cohort | C passed sealed rehearsal epoch and four cohort filters on exact worker/application identities. Cooperative 0.5.0 timing only; rehearsal epochs cannot become production launch data. |
| Rollback | C passed application rollback/forward with database, epoch, result and worker checks. Equivalent application bytes; no off-host disaster recovery proof. |
| Operations | C failed load and scheduled monitor checks; full rehearsal incomplete. [Abandoned continuation](production-diagnostic-continuation-20261019.md) preserves failed preflight/admission and budget history. No subsequent native performance or monitoring pass. |

See the [owner decision packet](mvp-recommendation-20261019.md) for the proposed
scope and only the remaining work needed to make it reviewable for activation.
