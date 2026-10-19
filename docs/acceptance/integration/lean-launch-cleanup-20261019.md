# Lean-launch cleanup — 2026-10-19

The owner selected lean-launch retention and explicitly authorized immediate
cleanup, superseding earlier blanket preservation requirements. Policy checkpoint
`e600be7` updates AGENTS.md and the current requirement documents; see
[RETENTION_POLICY.md](../../RETENTION_POLICY.md). Historical acceptance outcomes
and their original manifests were not rewritten.

## Completed cleanup

All selected removals completed without deletion failures:

| Removed | Count |
|---|---:|
| Stopped trial image-store groups (image/rootfs/containerd/buildkit subtrees) | 24 |
| Clean engineering source copies | 20 |
| Obsolete image archives and unpacked release sources | 16 |
| Clean obsolete release checkouts | 5 |
| Duplicate historical Git bundles | 5 |

Each operation recorded exact paths and identities before deletion. Trial stores
required terminal journals, absent recorded process births/cgroups and sockets,
inactive units, ownership checks and per-store operation locks. Mapped removal
used the original rootless UID/GID mapping; it did not invoke Docker pruning or
mutate the shared live daemon. All Docker volumes, container logs, original
journals/configuration and scientific evidence outside the image-layer allowlist
were preserved. Retired store markers prohibit restart.

Source copies were checked clean, their commits verified in the owner's local
repository, their tree/index identities recorded, and ignored noncache data
excluded. Deletion unlinked files without changing shared file content or file
modes. Duplicate source history remains available locally. Current installation
paths and active mounts were excluded.

| Disk observation | Bytes | Approx. GiB |
|---|---:|---:|
| Available before maintenance | 5,726,605,312 | 5.33 |
| Available at final audit | 33,715,126,272 | 31.40 |
| Recovered | **27,988,520,960** | **26.07** |

This resolves the previous diagnostic disk-floor blocker. It does not implement
the still-incomplete diagnostic callback or establish monitor/authentication
causes, native load performance or rehearsal acceptance.

## What remains

The running application uses source `6b332cdb051a9da5651a2fc1e1e1bac0f7df0acf`.
Its release packet and the existing `/srv/mldsafail/current` target
`/srv/mldsafail/releases/b4d212d` remain unchanged. The retained rollback is
`b4d212da3109b7716eb41553986848e377fb5b3d` with its image archive and required
frozen worker archive. Verification checked current artifact checksums, reachable
OCI image identities and all 80 referenced blobs across current/rollback/worker
archives, matching benchmark/configuration/dependency/trusted/worker identities
and matching frozen evaluator/benchmark source hashes. This was archive and
compatibility verification; no new runtime rollback was performed.

Named retention exceptions are private and reviewed by 2026-10-26:

- C's unresolved monitor/authentication failures retain their original logs,
  raw request evidence, configuration and offline PostgreSQL volume.
- The next diagnostic retains its unchanged candidate/matching rollback,
  worker/database/proxy archives and frozen source/context inventories.
- Scientific and measurement evidence supporting retained results—including
  failed G/L outcomes—stays separate from disposable infrastructure caches.
  Review scientific relevance explicitly before removing any such evidence.

The shared live Docker store was not pruned. Small original run records and
compact source packages remain; the policy does not require deleting every small
file merely because its surrounding environment has been retired.

## Verification and retained records

The final audit passed: all seven existing running/stopped container identities,
images, process IDs and start times unchanged; current symlink unchanged;
private readiness returned HTTP 200; nine retained C receipt entries (eight
unique paths) unchanged; C socket absent; delivery disabled; no user jobs;
all 24 selected layer sets absent; original trial journals unchanged and all
recorded volumes preserved. Available RAM was 1,455,661,056 bytes. No new
evaluation, private epoch, image build, notification or production activation
was performed. No spending was incurred.

Private evidence is under `results/lean-launch-cleanup/20261019/` locally and
`/home/mldsafail/.mlf-lean-launch-cleanup-20261019/` on the VPS. The portable native
cleanup record is **43,348 bytes**, replacing none of the necessary scientific or
unresolved-failure data. Its verified copy exists locally. It is a maintenance
record, not off-host recovery acceptance or backup setup.

| Artifact | SHA256 |
|---|---|
| Exact native `final-audit.json` (local `final-audit-native.json`) | `7251bb1f105aa0df2edd7c5c8299695cab5b1bb6dbfe6da3f97acf56205bdc90` |
| `compact-cleanup-records.tar.gz` | `3052b778e9484365e8fdcd85df51b654d3c2f369fe7d144b2839756bc09de014` |

Early archive-verifier preflights assumed config IDs where these saved images
use OCI index identities. A follow-up descriptor parser also needed to distinguish
image configuration objects from descriptors. Those negative preflights are
retained privately; obsolete-release deletion was gated until the corrected
reachable-blob verification passed. No release was deleted on those failed
preflights. All final removal reports have empty failure lists.

Focused cache-retirement/offline-volume tests: **14 passed**. `make check` at the
policy checkpoint: **1,097 passed, 13 skipped**, plus **eight contract tests
passed**. No executable repository code or benchmark semantics changed.

Cleanup is separately authorized maintenance. It does not consume diagnostic
generations or reset their existing conservative 900-second debit. No diagnostic
callback was run. Fresh diagnostic protocols and the eventual full rehearsal
still need their applicable source/protocol review and approval. Backups and
all separate launch/measurement gates remain deferred. Commits remain local;
nothing was pushed.
