# Production preparation — 2026-10-19

**0.5.0 preview; 0.6.0 ignored; C diagnostics abandoned; backups deferred.**
Item 3 is **partial and blocked**. Preparation did not pass independently; item 4
has an [interface-bound procedure draft](../../PRODUCTION_EPOCH_PROCEDURE.md),
not an executable reviewed operation packet. [Machine-readable status](production-preparation-20261019.json).

Started at `cb4c2561477f4ed16247293c199b3f23d54b2812` with a clean worktree.
Read the current launch checklist, retention policy, artifact and participant
reports. Historical receipts and original private drafts remain unchanged.
A new versioned candidate in the owner's existing private configuration directory
uses 0700/0600 permissions. Its environment omits the epoch ID entirely; a separate
private manifest records that dependency and additional blockers. No activation
symlink was changed. Private receipt hashes remain private.

Bounded SSH reused the recorded account/key and session 1's pinned ED25519 host
file with strict verification. Remote commands only inspected directories,
container/image/volume metadata and selected image references; no remote files
were written. The current rootless daemon resolves the frozen worker, Caddy and
PostgreSQL indexes. Exact selected candidate web/coordinator indexes both fail
`docker image inspect`. They remain verified archives from session 1; archives
are not locally resolvable image references. No images were loaded, substituted,
built or run. Investigation stopped at this blocker; no alternate daemon search
or worker-provenance recovery occurred.

Reused the supplied OAuth file and draft database/session secrets. Structural
OAuth checks and equality with the supplied file pass; existing progress records
report field preparation, not independently verified GitHub registration/login.
Database/session values meet the length and separation checks against each other
and active container environment. Separation from every retained rehearsal secret
is not established, so no complete secret-reuse acceptance is claimed. No secret
was printed or regenerated. No secret-derived hash appears in this report.

The candidate retains the selected HTTPS origin/callback, benchmark and quotas
1/2/10. The fingerprint comes from reviewed worker evidence. The proposed suite
label names version 0.5.0, and worker class uses the coordinator's source default;
these labels do not establish an audited cohort. Production evaluator/TLS/ACME
paths do not yet exist on the host and their inspected resolutions show no
symlinks. Active mounts/volume inventory was retained privately. Complete trial
mount/volume alias reconciliation and database namespace acceptance remain open;
no production resource was provisioned.

Preflight now has an explicit preparation mode: only an absent future epoch ID
may bypass a required-value check. It requires a private preparation manifest,
checks selected source/rollback/image/version/quota bindings and private ownership,
symlinks, hardlinks and permissions, and rejects open preparation blockers.
Its success message explicitly retains the epoch dependency; ordinary validation
still requires an epoch. A preparation manifest cannot pass full validation.
The private candidate remains failing on missing local images and open blockers.
No expanded Compose configuration or configuration values are emitted.

Focused tests cover preparation/full differences, immutable and wrong artifacts,
wrong versions/quotas, secrets, storage overlap, private files and fixed diagnostics.
The existing rehearsal purpose-guard tests remain unchanged. Synthetic Compose
rendering is tested without creating resources; no rendering acceptance is claimed
for the blocked epoch-free candidate. Production-wrapper mocks cannot be claimed:
that separate wrapper has not been implemented. The runbook explicitly records
this remaining work rather than relaxing the rehearsal guard.

No solver/evaluator/epoch, deployment, listener/OAuth activation, notification,
image change or publication occurred. No public API, schema, scoring, contestant
contract or application behavior changed. Worker build provenance, live OAuth/TLS,
future audited epoch and later operational/activation gates remain open.

Validation: **37 focused tests passed**, including synthetic Compose rendering;
**14 documentation links** checked; `git diff --check` passed. Final `make check`
passed **1,184 tests, 15 skipped**, plus **8 contract tests** (12 existing warnings).
All inspection/configuration receipts remain in owner-only private storage.
