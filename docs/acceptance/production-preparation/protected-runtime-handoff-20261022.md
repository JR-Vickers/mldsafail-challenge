# Paused handoff and delegation checkpoint — 2026-10-22

Implementation remains unfinished. This advances the [lifecycle checkpoint](protected-runtime-lifecycle-20261022.md), preserves its receipts and grants no live installation authority. The [machine record](protected-runtime-handoff-20261022.json) binds private evidence hashes.

The engine now binds a previous supervisor's actual unit, process/socket births,
generation, durable ownership and paused state. Active status must agree with its
validated durable journal, with no pending requests, transactions or live heavy
resources. It stops only the exact inspected supervisor. A complete synthetic
previous-supervisor proposal reaches exact commands without execution authority;
an actual supervisor handoff rehearsal is still required.

Heavy-unit staging precedes prerequisites, while supervisor-unit replacement now
follows release verification and atomic activation. Fresh loaded commands,
environment, working directory, reference files and acknowledged replacement
births are checked before enabling startup. Rollback follows those separate unit
transitions. Four original snapshots are immutable, including their companion
scheduling/container records. Privileged scheduling-file reads use bounded chunks,
stable file metadata and aggregate allocation limits. Authorization expiry during
preconditions leaves no mutation intent.

Observed cgroup ancestors now bind enabled subtree controllers and control-file
UID/GID/mode/write permissions as well as births, controllers and limits. Shared
ancestors must already enable required controllers. The new read-only collector
conservatively protects every observed ancestor; proposed dedicated paths have
no invented births. In the real disposable x86_64 Linux guest, the collector
observed the complete chain. An exclusively created inert heavy slice began with
empty subtree control; the existing dedicated-slice helper enabled cpu/memory/pids.
All observed shared ancestors remained unchanged, and the fixture unit and both
created slices were removed after identity checks. This is a prerequisite
primitive rehearsal, not complete installation or installed-native acceptance.

Focused Linux verification passed 160 tests. `make check` passed 1,751 tests,
46 skipped and all 8 contract checks. An earlier run rejected the new untracked
runtime script under the explicit inclusion policy; after adding it to the index,
the complete check passed. The initial resumed-guest SSH readiness attempt failed
before boot completed; both readiness attempts remain recorded. Incremental
independent review found no remaining concrete finding in these changes. Its
initial heavy-controller finding was retracted after checking the existing scoped
helper; it has not approved the complete plan or installation proposal.

The owned local guest remains running for continued rehearsal; its cgroup fixture
is cleaned. Full concrete installation/reconciliation/rollback, actual handoff,
all acceptance runners, watchdog integration and complete proposal review remain
unfinished. Missing [privileged VPS facts](../../PROTECTED_RUNTIME_OWNER_COLLECTION.md)
are a separate blocker. Budget remains $0 and version remains 0.5.0 preview.
No live VPS mutation, solver evaluation, production epoch, capacity measurement,
public listener, notification, publication or backup ran.
