# Review of integration into main — 2026-10-16

## Resolution and owner-authorized integration

After this review, the owner explicitly requested the workflow fix and local
merge. OPERATIONS.md now documents dump-only behavior and directs actual restore
acceptance to the durable dedicated-daemon workflow. Historical rehearsal
preflight pins and manifest-checks the original restore-capable helper before
resource creation; a regression check rejects the current retired helper and
missing manifest binding. The exact historical helper is retained as a test
fixture. Full historical Compose/transitive-source acceptance remains open.

Focused checks passed (20 tests); `make check` passed with 970 tests, 13 skipped
and eight contract checks. A fresh `git fetch origin` confirmed local main and
origin/main both at `4602f45`. The earlier conditional recommendation is satisfied
for source integration; native acceptance and public activation remain separate.
The original review below is retained as dated evidence.

Reviewed local `main` at `4602f45` against `engineering/integration` at `c33f322`.
This is a source integration/readiness review, not production acceptance or an
exhaustive security audit of every new operator utility. No branches were merged,
pushed, deployed or activated during this review. Remote refs were not fetched;
the recommendation applies to these exact local tips.

## Recommendation

Prefer one history-preserving integration merge after resolving the backup
workflow inconsistency below. Avoid selecting hundreds of individual commits:
the branch already consolidates interdependent recovery, client ownership,
versioning, public development and acceptance evidence. Keep experimental 0.6.0
code disabled through its existing gates. Main may be the engineering baseline
while production acceptance remains open; document that distinction explicitly.

The current tip is not an unconditional merge approval. Correct or explicitly
retire the broken operator instructions/caller before handing over the final
merge candidate. Retain the historical source and failed evidence. Do not restore
the retired restore method merely to make an old command succeed.

## Finding: backup verification callers disagree with the helper [P2]

`deploy/backup_postgres.py:19` rejects `--verify-restore` before doing any work.
`docs/OPERATIONS.md:226` still instructs the operator to run that exact option,
and the following prose describes behavior that has been removed. Following the
current backup acceptance instructions exits with status 2 and performs no backup
or restore. Replace the instructions with the supported dedicated-daemon recovery
procedure and its prerequisites.

`scripts/baseline_production_rehearsal.py:480` also invokes the option from its
configured retained source. It therefore cannot complete against the current
helper. Historical sources that implement the option must be bound and inspected
explicitly; the native handoff already withholds that acceptance. Do not present
the rehearsal as runnable against an arbitrary current checkout. Resolve the
supported source/configuration combination or fence the unsupported combination
in preflight before provisioning resources.

Safely reproduced the parser failure with nonexistent input/output paths: status
2, explicit retirement error, no Docker operation or filesystem output creation.

## Merge mechanics and preservation

- Local graph: one commit unique to main, 338 unique to integration.
- Main's unique commit is `4602f45`, the worker package-build fix. Its final
  Dockerfile content is already preserved in integration.
- `git merge-tree --write-tree main HEAD` completes without conflict and produces
  tree `52d05d5acfd02b7b75e44222a3f87ebc32f4163d`, identical to integration's
  reviewed tree. A merge is not a fast-forward because the histories diverged.
- Actual tip-to-tip difference: 446 files, 47,092 additions, 2,650 deletions.
  There are 207 documentation/evidence files and 78 test files in that difference.
  Large receipt/archive changes account for much of its size.
- No tip-to-tip changes in `config/`, `src/mldsafail/benchmark_v050/`,
  `src/mldsafail/trusted/`, `src/mldsafail/benchmark/`, `uv.lock`, database
  migrations or `src/mldsafail/web/models.py`.

## Behavior changes a merge must communicate

- `mldsafail run`, `mldsafail-bench` and `make bench` now use ledger-backed public
  MLWE development; old 0.4.0 execution has explicit archival entrypoints.
- New 0.4.0 hosted submissions are rejected; historical rows/readers remain.
- Hosted startup now requires an explicit supported benchmark version and the
  appropriate audited epoch. Existing deployment configuration must be checked
  before switching application images.
- Production Compose needs explicit certificate/webroot paths; it is preparation,
  not an instruction to activate listeners on merge.
- Proposed 0.6.0 registration/adoption/default gates remain separate. Default
  hosted version stays 0.5.0; private candidate authority additionally requires
  explicit testing/rehearsal scope. Preparatory CLI options do not adopt it.

## Remaining acceptance work is not automatically a source merge blocker

Measurement G/L failures, missing exact native installation/reproduction artifacts,
source-bound rollback/helper review, full protected restoration, failure/load
acceptance, real off-host custody and email delivery remain open. They prevent
claiming production readiness. Keep the inactive code and honest dispositions
together rather than discarding failed evidence to simplify the merge.

The retained historical rollback release lacks the required production Compose
file. Baseline manifest validation currently hashes Compose and frozen benchmark
Python, not the complete imported backup/recovery dependency set. These are
explicitly unresolved native execution prerequisites, not newly passed gates.

## Validation and final integration procedure

`make check` passed during this review: 969 tests passed, 13 skipped, plus eight
MLWE contract checks. Skipped native/Docker coverage and historical native receipts
do not prove a fresh combined production deployment. No live operation was run.

After the finding is addressed, freeze/review that successor and run appropriate
focused checks plus `make check`. Recompute merge mechanics against the actual
main tip (including checking whether the remote has advanced), then hand the owner
the exact candidate and commands. A normal merge preserves source/evidence commit
identities. Leave pushing to the owner; no merge or publication is authorized by
this review itself. Do not delete historical branches/worktrees/artifacts as part
of consolidation.
