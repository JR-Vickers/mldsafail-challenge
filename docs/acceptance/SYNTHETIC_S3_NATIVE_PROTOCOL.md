# Isolated native HTTPS S3/restic protocol

This gate creates only synthetic data, repository passwords, S3 credentials, TLS keys, and an isolated local MinIO repository. It never copies existing epoch evidence or contacts actual owner storage. It does not establish real off-host storage, owner-held recovery password custody, audited PostgreSQL restoration, timer activation, or public launch approval.

The fixture runs pinned native Linux ARM64 restic 0.17.3, with its compressed archive checked against the official release SHA256SUMS. MinIO is cross-built from exact official release `RELEASE.2025-04-22T22-12-26Z` source commit `0d7408fc9969caf07de6a8c3a84f9fbb10a6739e`, because the official binary archive returned HTTP410. The artifact manifest binds the source archive, Go dependency lock, toolchain/target, and native binary hashes. No purchase or owner credential is required. The pinned binaries and manifest must be retained privately and copied to a fresh disposable VM.

Use the dedicated operator cgroup delegation described in [the operator-client protocol](OWNED_CLIENT_NATIVE_PROTOCOL.md), separate from benchmark accounting. Every restic/curl/openssl client and the local server uses durable gated cgroup ownership. The server binds only guest loopback; the QEMU VM exposes only task-owned loopback SSH. Native evidence binds source commit, script/helper hashes, kernel, Python, architecture, binary hashes and actual version output.

Predeclare these stages before launching the fixture:

1. Generate a synthetic local CA/server certificate and enforce its trust. Initialize a new HTTPS S3 repository and create exactly three tiny synthetic snapshots.
2. Run a full encrypted repository check. Reject incorrect recovery password, incorrect S3 secret, and an untrusted server certificate. Preserve bounded private rejection output.
3. Add exactly 64 MiB of deterministic synthetic data, then interrupt a real backup only after a new encrypted pack has been published while the native restic process remains live. Stop its exact cgroup, prove exit, remove only this repository's stale lock, check, retry, and restore byte-identical data.
4. Apply keep-last-one retention only after a successful synthetic restore; require one snapshot and another full check.
5. Download one encrypted pack through authenticated HTTPS, preserve its original bytes, replace it with one flipped byte, require full-check rejection, restore the original through HTTPS, and require full-check success.
6. Independently cancel all client domains and the server domain, prove removal and preserve cleanup receipts. Stop the owned VM. Verify original power-loss disk and firmware hashes are unchanged.

Use a fresh mode-0700 evidence parent and retained clean source:

```sh
python -m deploy.qemu_owned_client_acceptance \
  --base PRIVATE_RETAINED_POWERLOSS_VM \
  --output FRESH_PRIVATE_VM_DIRECTORY \
  --source CLEAN_RETAINED_SOURCE \
  --gate synthetic-s3 --artifacts PINNED_SYNTHETIC_ARTIFACT_DIRECTORY
```

The generic Linux fixture can also run inside an isolated delegated native unit:

```sh
python -m deploy.native_synthetic_s3 --output FRESH_PRIVATE_OUTPUT --artifacts PINNED_SYNTHETIC_ARTIFACT_DIRECTORY
python -m deploy.native_synthetic_s3 --output EXISTING_PRIVATE_OUTPUT --cleanup
```

Cleanup attempts clients and server independently. Each retry writes a new receipt; failed evidence and the original pack remain private. Do not run conflicting native work until cleanup is complete. A changed binary/source requires fresh evidence. Performance thresholds and benchmark scoring are unaffected by this operational fixture.

The [official restic S3/TLS documentation](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html) describes HTTPS S3 and custom certificate trust; the [restic CLI source documentation](https://github.com/restic/restic/blob/master/doc/manual_rest.rst) records `RESTIC_CACERT`. This fixture uses certificate validation and never `--insecure-tls`.
