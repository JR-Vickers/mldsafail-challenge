# Retained 0.5.0 remote artifact verification — 2026-10-19

**0.5.0 preview; 0.6.0 ignored; C diagnostics abandoned; backups deferred.**

Item 1 is **partial**: all seven selected archives are verified remotely for
Linux amd64, but the frozen worker's original Git build commit remains
unsupported. The set is reusable as the retained archive set for subsequent
preparation, conditional on resolving that provenance gap before item 1 closes.
This is neither runtime rollback acceptance nor a valid production epoch.

Inspection started from Git `c84305c9f43b732ba3f30052872e33af86db51f5` with a
clean worktree. Historical receipts were preserved. Only local evidence and
these documentation updates were written; no remote service, deployment,
archive or diagnostic state was intentionally changed. No images were built,
loaded or run; no archives were transferred, environments extracted, evaluations
or epochs created, notifications sent, cleanup performed or publication made.

## Access and bounded inspection

Used the documented deployment account and SSH identity at the specified VPS,
with SSH configuration bypassed and only the recorded ED25519 key allowed.
Strict host verification used fingerprint
`SHA256:OtjIfXCrqewb9FTJ8jpU7Rq7aZL4P8P7U0dKZ8DoB5w`; it matched.
Connection attempts, remote commands and local waits had explicit time limits.
Existing remote Python, SHA256 and timeout tools were available.

At 12:45:52 UTC, load averages were 0.13/0.12/0.16, available memory was
1,377 MiB and disk had 32 GiB available. Full process inspection found no active
evaluation or maintenance; user systemd reported no jobs, and Docker listed only
the four long-running installation services. The idle coordinator was present.
The interrupted diagnostic upload was not used. All seven archives existed at
their recorded locations; no relocation search was necessary.

Archives were processed sequentially: full streaming SHA256, streaming tar/member
reads and hash/size checks on every saved OCI blob, then small metadata reads to
resolve the Linux amd64 descriptor closure and Docker manifest references.
No archive member was executed or written remotely. Raw receipts and exact paths
are retained in the new ignored integration-evidence directory for this session
(directory 0700, files 0600); the receipt manifest records their hashes.

## Artifact dispositions

Each row is **Verified remotely** for archive integrity and Linux amd64 content.
Expected and observed image-index identities and whole uncompressed archive
SHA256 values are equal in every row. Times below are UTC on 2026-10-19;
they mark the beginning of each sequential artifact inspection, not a runtime test.
Platform observations come from the actual image configuration, excluding
attestation configurations marked unknown/unknown.

| Role | Expected = observed saved-image index identity | Expected = observed tar SHA256 | Platform | Inspection time UTC | Disposition |
| --- | --- | --- | --- | --- | --- |
| Candidate web | `sha256:31383f86703dcc8b4ba4c36acd8933ed5bf306ee98fa129e50d4625dd4c12a4b` | `e02d119cabfab72f9e11eac248b087fe15beeb37a122e8e06feeb0970c2dc390` | linux/amd64 | 12:46:41 | Verified remotely |
| Candidate coordinator | `sha256:b3f27a3b1b3d25d808f21ac56f2653dc5bd29f77dd9903acfd84969080c0d0a4` | `e71474c16cc62529d1418fb587449833b58a3e603f0f0a29c5bbb2cacf5fd583` | linux/amd64 | 12:46:42 | Verified remotely |
| Compatible rollback web | `sha256:035956fde36b9131888ee8f29ab3178a143bce67dfb6419b16d30a76c31a7428` | `68e01b745177b9af16452a75e7d1eb8035467d4af2edc306b211c3021cdc50bf` | linux/amd64 | 12:46:43 | Verified remotely |
| Compatible rollback coordinator | `sha256:f1eed8b81d932b721950a0f15c6621c658b08e4ba437d2b4f4cbebfaf884f23e` | `758b42565f0017c5a5f01fdb1a32fce49c23cd0ea68fd162aa5b4d69a6c2becc` | linux/amd64 | 12:46:44 | Verified remotely |
| Caddy | `sha256:6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b` | `db888297a9dcb25f4ed8f93c6b855ce8fa3c15fce15450dd843134cdf79bd806` | linux/amd64 | 12:46:46 | Verified remotely |
| PostgreSQL | `sha256:639ab7ceb90e13123085b741fb31ef493fba25463002f6da665352e7b534b652` | `7afbae099cf728bd5ee01c933261d27f4687c1d4c1c8165980a73c50b9cc1270` | linux/amd64 | 12:46:46 | Verified remotely |
| Frozen MLWE worker | `sha256:6aaf71aa16e36631dec607f0726fb1e8d6f94954ce55a15a74ba4989777b5cfe` | `c259e98683e699000d46eb2da37dce4d8ae205c9349e349fc553e2c32c09b40c` | linux/amd64 | 12:46:47 | Verified remotely |

All **121** saved blobs hashed correctly. Application archives have respectively
16/19/16/19 blobs, Caddy 12, PostgreSQL 21 and worker 18. All tar streams were
readable. Each expected index blob is present and selected by `index.json`.
Every Docker `manifest.json` config/layer reference reconciles with the saved
blob descriptors. The complete amd64 manifest/config/layer closures pass hash
and descriptor-size checks.

Caddy's multi-platform index also names 12 absent non-amd64/associated-attestation
descriptors; PostgreSQL's names eight. These are retained upstream index entries,
not missing Linux amd64 layers. Their amd64 closures are complete; the archives
are not verified as portable archives for every platform named in those indexes.
Application and worker descriptors have no missing references.

The recorded identities above are **OCI image-index digests**, not image
configuration digests. Application/worker indexes are local saved identities;
no registry digest is invented. PostgreSQL/Caddy indexes agree with the existing
Compose registry pins and running service references. The separate configurations
are recorded below to prevent conflating the two identity types.

| Role | Observed configuration SHA256 |
| --- | --- |
| Candidate web | `e8495aa1f0eb53c12233235524ec6f77def0c208b27c0e29ded83a728b1c0dfd` |
| Candidate coordinator | `9cf7170dcf90a1d1bb57e582bd103b995aaeb4c1f14d2c098225906c1d94272b` |
| Compatible rollback web | `f02fab3349288995ad92789b7bd20c8c8b08564fb0a92d395f265a3d91a96d09` |
| Compatible rollback coordinator | `8e5f5de6e8dcf205a3716e6375acae97228a8802856471984c67626883a2e159` |
| Caddy | `2d8b1708bf8008935c0e2a9b6564f7f080cf9a73af3b27718f286230449b7101` |
| PostgreSQL | `248efd5e58cd743f2a0e0daec8ea4649e5580145ec2a12e2345bc710d4a77201` |
| Frozen MLWE worker | `c44f70ecdac90fb2d2afadcc907d756b6e6a1be784eced7311682e5779000414` |

## Provenance and compatibility

Candidate web/coordinator configs have `org.mldsafail.source` equal to
`1c9ca9eff3a1133aa8b508a35f6b174a587a4f01`. Compatible rollback configs
have that label equal to `26c5f2f4bc771b319ffccc2cdcb1c735eaab4176`.
These agree with the retained artifact index, release/rollback manifests and
B/C build reports. Local record hashes were rechecked against the ignored
inventory. The proposed preview pair remains separate from the installation
source `6b332cdb051a9da5651a2fc1e1e1bac0f7df0acf` and installation rollback
`b4d212da3109b7716eb41553986848e377fb5b3d`. The current symlink resolves
to the latter retained checkout; running application image IDs match the separate
installation recorded by cleanup. No symlink or deployment was switched.

Candidate and rollback source archives were re-read against all manifest-listed
files: **2,442** and **2,394** respectively, with no missing files or mismatches.
Both full Git objects remain available. Required source/configuration records,
including retained private rehearsal configuration archives, are available locally;
these are historical inputs, not an approved production configuration.
[Operations rollback instructions](../../OPERATIONS.md#failure-handling-and-application-only-rollback)
and [C rollback/forward evidence](production-rehearsal-20261016.md) remain available.
The old incompatible `4602f45` rollback is excluded; its failed compatibility
receipt must not be mistaken for the matching `26c5f2f` release.

Both selected manifests bind the same worker ID and trusted fingerprint:
`b6f92231843fcb90695669108f0cc02d747ae0614eb9b3d25cddae602e092eee`.
That fingerprint matches the worker's actual `org.mldsafail.trusted` label.
Both sources/manifests agree on:

| Binding | SHA256 / requirement |
| --- | --- |
| `uv.lock` | `58d4165666f7461539ed348cf696a00524c0f356b7d23f874c2e4e2bb5cea329` |
| amd64 worker dependency lock | `35890cf7c5ed544124dc4cc86269009f11d029a5388d1627b6899e986650c1f0` |
| Worker release label | `8277211b511294c1f130bf7895b07559e6c06e0ba11afe3a9778d3754b0b5045` |
| Interpreter | Sources select Python 3.12; package requires >=3.12; all five Python image configs record 3.12.10, matching application build reports. |

Recomputing the hosted worker release identity from each selected manifest's
trusted fingerprint, worker lock, Dockerfile hash, version and platform produces
the actual worker release label above. This establishes the declared source-input
binding, not an independent rebuild or fresh installed-dependency execution check.

The worker export receipt binds its exact index and tar hash, with historical
cleanup verified. The export operator receipt names source
`280c3b1bfa3f7fd7414c6472414ef7f1af60b9e7`; **this is export tooling source,
not proof of original worker build source**. The archive contains BuildKit SLSA
provenance for its amd64 manifest: build interval 2026-09-30 14:56:21–14:57:50 UTC,
builder platform linux/arm64, target linux/amd64, Python 3.12.10 Bookworm base
`sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db`.
Its local-context provenance does not name a Git commit, and its completeness
flags for request/resolved dependencies are false. There is no worker source-commit
label. Do not assign candidate, rollback or export-tooling commit to this build.

Caddy config identifies version v2.11.4 and its upstream repository; the amd64
index annotations name upstream revision `fba2853501d36e8a72f946ac8cb7ff64d07e48f2`.
PostgreSQL config identifies 17.11; its amd64 index annotations name upstream
revision `2603e26e245e558218728ee14e0a42dcb020dc7f`. These are observed upstream
metadata, not independently rebuilt source attestations. They are additional
provenance evidence beyond the inventory's immutable index/archive pins.

## Gaps and next session

No selected archive is missing or mismatched. Original worker Git build provenance
is still unresolved. Before closing item 1, recover a retained original build log
or source/context manifest that binds this exact image to its original source;
if no such record survives, document that limitation for an explicit owner
resolution. Neither matching labels nor the export-tooling commit closes it.
No rebuild, replacement, relabeling or repair was attempted.

Session 2 may proceed with the independent participant package work: resolve the
wheel/checksum conflict, prepare a reviewed clean source distribution and validate
the starter/clean install. Use the inventory's exact integration-tested package
identities; this verification does not resolve those packaging gaps. Production
execution still requires artifact provenance resolution and the later approved
configuration/epoch/authentication/operations gates. Archive integrity proves
neither a runtime rollback nor host/interpreter/reference/cohort production binding.

Validation: `make check` passed (**1,175 passed, 15 skipped**, then **8 contract
tests passed**). Documentation links and `git diff --check` were checked locally.
No public API, schema, scoring or application behavior changed.

## Bounded provenance recovery follow-up

The owner requested a recovery attempt, stopping if trouble arose. A read-only
follow-up listed the retained release locations and checked local build-history
references. No direct original-worker Git binding was recovered. Reading older
retained release manifests exceeded the 35-second local SSH deadline (the remote
command also had a 20-second limit). Captured partial manifest output was not
saved before the timeout, so none is counted as evidence. No retry or wider
investigation followed, and no remote state was intentionally changed.

The provenance recovery is skipped for now under that instruction. Item 1 remains
partial; this does not invalidate the seven verified archives or establish an
original build commit. The owner has not been treated as accepting the missing
provenance for production execution. Session 2 remains independent.
