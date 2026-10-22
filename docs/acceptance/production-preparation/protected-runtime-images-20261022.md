# Offline images and scheduling bindings — 2026-10-22

This is an implementation checkpoint, not installation approval. Implementation,
complete concrete engine rehearsal, privileged VPS facts and full independent
review remain unfinished. Budget remains $0; benchmark remains 0.5.0 preview.
Historical receipts remain unchanged. Compact evidence hashes and the current
fixture retention exception appear in the [machine record](protected-runtime-images-20261022.json).

The offline release now binds both actual locally built Linux x86_64 images in a
validated OCI archive. Blob closure, configuration identities, architecture,
compressed layers and uncompressed diff IDs are checked. The frozen archive strips
all tags without changing image IDs. A cold selected-image import with networking
disabled restored both image identities and configurations, with no container or
unrelated tag changes. This used the owned fixture daemon; it is not a fresh-daemon
installation receipt. The complete coordinator image also passed correct-owner
and wrong-UID inert socket probes, with verified container/socket cleanup.

A second fresh final-path offline package installation passed using CPython
3.12.10, uv 0.13.1 and all 35 unchanged-lock runtime wheels. All 21 selected
entrypoint modules imported. Verification compared 1,757 installed dependency
files and the complete interpreter/installer trees; imports changed neither the
source bundle nor installed bytes. Image archive bindings were actual; private
configuration bindings remained explicitly synthetic. This receipt does not
certify a complete installed runtime. Later source fixes require a new binding.

Private configuration contracts now bind supervisor/native/controller edges and
observed signing-key bytes, mode and birth. Public release records retain only
private-artifact roles, hashes and sizes. Owner-qualified scheduling identifiers
separate system and user units with matching names. Fresh manager census, complete
unit-name closure, fragment/drop-in/environment references and original settings
must match the preparation record. Loaded execution commands remain bound after
inhibition; only strict terminal process-accounting fields may change.

Independent review found and prompted fixes for the packet's shorter expiry,
pre-activation scheduling drift, output-directory authorization replay and loaded
command drift after inhibition. The native watchdog now binds the permanent claim
journal's identity. Fresh scheduling, file, manager/container and retained-service
observations run immediately before activation. Rollback preflight follows the
latest acknowledged pointer and unit transition.

Review also found unresolved partial-install rollback and existing-supervisor
handoff work. Execution now explicitly blocks an existing protected supervisor
rather than allowing its restart to select an incomplete release during unit
replacement. That blocker is unfinished implementation, not a missing VPS fact.
The complete concrete installation and rollback path has not passed. Six inert
native cases have implementations, but required coverage and watchdog integration
remain incomplete; no native VPS receipt has been created.

Focused local regression tests and `make check` passed: 1,680 tests, 46 skipped,
and all 8 contract checks. The Linux test transfer initially omitted
the unchanged lockfile: 129 tests passed and one fixture-input test failed. After
including the lockfile, the affected Linux selection passed 89 tests, including
the native watchdog replay test. The failed attempt remains retained. The local
VM filesystem expanded to its explicitly owned 20 GiB disk and has sufficient
headroom for another rehearsal while preserving the 5 GiB admission floor. The
proposed output filesystem remains capped at 1 GiB.

Privileged host facts still require fresh complete scheduling owners and recursive
references, cron/at dispositions, container births and restart settings, cgroup
ancestry/controllers/delegation/effective limits, persistent output storage or an
exclusive allocation proposal, rootless mappings, compatible rollback and current
memory/disk admission. Use the existing [owner-console procedure](../../PROTECTED_RUNTIME_OWNER_COLLECTION.md).
No live installation authorization is requested. No VPS mutation, solver run,
production epoch, capacity measurement, public listener, notification, publication
or backup ran in this phase.
