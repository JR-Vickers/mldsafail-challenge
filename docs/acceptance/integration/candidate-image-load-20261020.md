# Candidate image loading — 2026-10-20

**0.5.0 preview; 0.6.0 ignored; C diagnostics abandoned; backups deferred.**
The owner explicitly authorized loading the two verified candidate archives into
the existing rootless Docker daemon and checking exact identities, without
starting or restarting services. This closes the selected-image-resolution blocker
from the [preparation report](production-preparation-20261019.md).
[Machine-readable receipt](candidate-image-load-20261020.json).

Reused the recorded deployment account/key and pinned ED25519 host identity with
strict SSH checking. Explicitly selected UID 1000's rootless socket; verified its
ownership, socket type, rootless daemon security mode and disk headroom. Held an
exclusive image-load lock. Before each sequential load, rehashed the exact retained
archive against session 1's SHA256 and read its amd64 manifest/configuration
binding. No archive was substituted, rebuilt or transferred.

| Role | Loaded and inspected index identity |
| --- | --- |
| Candidate web | `sha256:31383f86703dcc8b4ba4c36acd8933ed5bf306ee98fa129e50d4625dd4c12a4b` |
| Candidate coordinator | `sha256:b3f27a3b1b3d25d808f21ac56f2653dc5bd29f77dd9903acfd84969080c0d0a4` |

Both resolve by the exact index identity in the installation's existing daemon,
report Linux amd64 and carry source label
`1c9ca9eff3a1133aa8b508a35f6b174a587a4f01`. Separate platform manifest and
configuration digests are retained privately and match the verified archives.
No registry identity was invented. Before/after snapshots of all containers
match on container ID, image, status, start time and restart count. No container
was created, started, stopped or restarted by this operation. No deployment
symlink, Compose configuration, epoch, listener or notification was activated.
Loading can update imported image tags; this does not replace running containers.

The owner also explicitly accepted the documented missing original worker build
commit for this preview. The historical provenance gap remains factual; this
records acceptance of the limitation, not recovery of evidence or a rebuilt
worker. The owner confirmed the OAuth homepage `https://178.128.17.58` and callback
`https://178.128.17.58/auth/callback`. This closes the request for owner URL
confirmation; independent registration inspection and actual login/TLS acceptance
are not established by that confirmation.

The dated preparation candidate and original draft remain unchanged. A new private
image-resolution receipt records this result and the owner decisions. Configuration
preparation remains partial: full retained-trial secret/storage-isolation checks,
the production wrapper and exact reviewed operation packet, and a separately
authorized audited epoch/final cohort binding remain open. No epoch authorization
is inferred from permission to load images.

Validation: exact-image/archive and unchanged-container checks passed remotely.
Local documentation links and `git diff --check` passed. `make check` passed
1,184 tests with 15 skipped, plus 8 contract tests (12 existing warnings).
Private raw receipts and their SHA256 manifest remain owner-only. No code changed.
