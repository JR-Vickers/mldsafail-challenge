# Supervisor startup and partial rollback checkpoint — 2026-10-22

Implementation remains unfinished. This advances the [offline image checkpoint](protected-runtime-images-20261022.md)
and preserves its historical record. It grants no live installation authority.
Evidence hashes appear in the [machine record](protected-runtime-lifecycle-20261022.json).

The generated v3 supervisor unit now requires an enable file inside the exclusively
created release directory. The engine creates this file only after atomic release
selection and fresh complete release verification. Computational allow files stay
absent. Rollback stops the acknowledged supervisor and removes only its exact
acknowledged enable file. Independent installed inspection checks that file's
proposal-bound contents, private ownership/mode and journalled birth. Startup
observations bind the actual manager PID, process birth, socket birth, UID,
placement and supervisor generation. Install mutations recheck release identity
and reject parent symlinks.

A disposable systemd rehearsal established that an absent condition prevented
both startup and cleanup commands. Creating the fixture-only enable file allowed
the inert service to start. A second retained-active fixture recorded
ConditionResult=yes and ActiveState=active; its unit and marker were removed.
The first oneshot fixture reported ConditionResult=no after its enabled commands
had run; that final query is not used as positive-condition evidence. Both raw
records remain retained. These are local Linux controls, not installed-native
acceptance.

Rollback now explicitly retains or establishes scheduling/container inhibition,
checks unresolved installation mutations before touching resources, follows the
latest acknowledged activation/unit transitions and skips selection/unit changes
that never occurred. It does not stop an uninstalled supervisor. Never-started
cleanup rejects unexpected runtime journals and unacknowledged cgroup resources.
Original unit restoration requires acknowledged identity before deletion, including
an identical-byte replacement test. Existing units recover their saved bytes,
mode, UID and GID. Final authorization expiry withholds phase completion while
preserving acknowledged outcomes. Synthetic interruption coverage now includes
every rollback boundary; concrete primitive tests check untouched selection,
unknown resource preservation, marker replacement and metadata restoration.

Focused Linux verification passed 167 tests; `make check` passed 1,713 tests,
46 skipped and all 8 contract checks. A preceding Linux test transfer omitted
non-Python preparation inputs and failed one missing-Dockerfile check; its raw
attempt is retained. The corrected transfer includes the preparation manifest's
complete input closure. No source expectation was weakened for either transfer.
Incremental independent review confirmed the marker, identity, restoration and
expiry corrections, without approving the complete source or proposal.

The existing protected-supervisor handoff remains an explicit execution blocker.
The complete concrete backend, partial installation recovery and full rollback
have not passed as one workflow. Complete acceptance coverage and native watchdog
integration remain unfinished. These are implementation gaps, separately from
missing privileged VPS observations described in the [owner-console procedure](../../PROTECTED_RUNTIME_OWNER_COLLECTION.md).
A local PostgreSQL 17.5 image is bound and retained for upcoming disposable schema
and transaction fixtures; this checkpoint did not start its container or database.
The full proposal needs regeneration and independent review after remaining work.
Compact guest records were collected, fixture containers/units/mounts were checked
absent, and the guest powered off gracefully. QEMU exited with status 0 and was
reaped; the driver reported its expected guest-exit assertion. The inactive VM
is retained for the next installation rehearsal under the existing temporary
retention exception, due for review by 2026-10-29.
Budget remains $0, benchmark remains 0.5.0 preview, and no live VPS installation,
solver evaluation, production epoch, capacity measurement, public listener,
notification, publication or backup ran.
