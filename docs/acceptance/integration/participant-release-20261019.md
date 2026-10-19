# Participant release preparation — 2026-10-19

**0.5.0 preview; 0.6.0 ignored; C diagnostics abandoned; backups deferred.**
Item 2 is complete for a local unpublished distribution 0.5.1 supporting benchmark
0.5.0. No publication, remote contact, image operation, solver execution, evaluator
invocation, epoch, submission, notification or deployment change occurred.

Started at `7ba89cb5ec06ba6f3df09ef550dc9ad32eb455d6` with a clean worktree.
The selected wheel was rehashed against the retained final-package/install
receipts and compared byte-for-byte with the earlier tested wheel. The deployment
checksum now selects it. The other same-version dist wheel (`da4033bd…`), both
historical source distributions and historical receipts remain unchanged and are
excluded from this release. No application, dependency, entry point, benchmark,
CLI or contestant behavior was modified.

Machine-readable [release manifest](participant-release-20261019.json).

## Frozen identities and handoff manifest

Wheel source: `26c5f2f4bc771b319ffccc2cdcb1c735eaab4176`.
Packaging/documentation source: `8fd91c3545ac4555bd83c9a7f1751f8e2b778852`,
tree `dd28edbbf49f1e44905ffb9891ce2a263c05bc9d`.
Later source-export guard changes enforce the outside-checkout build context;
they do not relabel these frozen artifacts.

| Artifact | SHA256 |
| --- | --- |
| Selected mldsafail_challenge-0.5.1-py3-none-any.whl | `ed002b7b2440efdf99936a9eb81df3010fa5d1b3f77c25b7e546eb15f7d62194` |
| Clean mldsafail_challenge-0.5.1.tar.gz | `0ff3e1761efdf1bdc13ba6242763953c02327c60304f3f47cf05c7f35875c851` |
| Sdist-derived wheel (verification only) | `489b586fc51c43f2c4aa2c319799c16004af0c93039bc36a95727faa632a7d82` |
| participant-download-candidate.tar.gz | `cc8029e28b1846df6fd53debefb0d1f7f70bad82fed2f63440fbbbbe2263feac` |
| Embedded, distributed and freshly cloned starter | `4d8df806feb996e35f7d99db71d8aa86154c3901dde786edccc4d3f80b207ed7` |

The bundle's SOURCE.json distinguishes wheel source and documentation source;
SHA256SUMS binds its wheel, installer, starter, README, contract presentation,
six public fixtures and source manifest. Its whole-archive hash is above. The
clean sdist has a separate SOURCE.json recording every selected historical source
hash and packaging overlays. Artifacts and private receipts are retained in a
new ignored owner-only evidence directory; build/install contexts are fresh and
outside the checkout. No old artifact was overwritten or hardlinked.

## Archive and build review

The source exporter reads Git objects from the selected historical revision.
Its explicit allowlist includes the complete `src/mldsafail/` package, original
build metadata, primal-LLL starter and selected participant documentation.
README, sdist allowlist, provenance and documentation link presentation are
identified overlays, not historical source. Existing package modules remain to
reproduce the wheel; this does not adopt experimental contracts.

Reviewed all 115 source archive members: regular files only, unique safe relative
paths, no links, credentials, private configuration/evidence, research results,
Git metadata, environments, caches, nested archives or external operator and
diagnostic payloads. Package files match the selected wheel byte-for-byte.
Documentation local links to omitted context are rendered as text. The download
archive uses the existing deterministic builder and passed its documentation-link
checks. Its checksums and selected wheel bytes verify; two builds from identical
frozen inputs produced identical archives.

Normal isolated PEP 517 builds produced the clean sdist and its derived wheel.
Both wheels' complete RECORD entries verify. Package payload paths/bytes,
metadata headers (including all dependencies), entry points and starter resources
match. Only METADATA's README-derived body and corresponding RECORD bytes differ.
The rebuilt wheel is **not** byte-identical to the selected wheel and is not a
replacement release selection.

Failed/partial attempts remain private: the first export expected a nonexistent
historical LICENSE; in-checkout builds let Hatch inject a parent `.gitignore`
despite target exclusions. Final builds used an outside-checkout context, and
the helper now requires that context. Those earlier archives are excluded.

## Installation and validation

Selected and sdist-derived wheels both passed the existing smoke helper in fresh
outside-checkout environments, with PYTHONPATH/PYTHONHOME/VIRTUAL_ENV overrides
removed for child commands and user site disabled. Both record Python 3.12.10,
macOS 15.7.7 ARM64, version 0.5.1 and imports inside their new environments.
CLI help, default MLWE clone, approved starter identity, public-development
metadata help and synthetic fixture verification passed. Dependency freeze logs
are retained separately for both installations. No primal-LLL solve was invoked.
Local ARM64 installation establishes neither native amd64 compatibility nor timing
acceptance. Docker and a compatible reviewed worker remain evaluation prerequisites.

Focused download/install tests: **6 passed**. Repository checks and documentation
links passed (17 local references); archive credential-pattern scanning passed.
`git diff --check` passed. `make check` passed **1,176 tests, 15 skipped**,
plus **8 contract tests** (12 warnings). An initial `make check` under umask 077 had
one unrelated recovery-directory expectation failure (1,175 passed, 15 skipped);
the normal-mask rerun is the acceptance result. Failed logs are preserved.

## Session 3 boundary

Use the exact manifest above for production-configuration preparation only.
The original frozen worker Git build provenance remains unresolved; item 1 stays
partial. Bundle manifest flags continue to record no publication approval and no
native reproduction acceptance; this local review supplies archive evidence only.
All later configuration, epoch, HTTPS/OAuth, participant journey, operations and
owner activation/publication gates remain open. Nothing was pushed or published.
