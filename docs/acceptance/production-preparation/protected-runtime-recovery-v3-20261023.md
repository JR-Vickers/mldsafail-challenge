# Protocol-three recovery checkpoint — 2026-10-23

The requested complete installation proposal remains **unfinished**. This is a
component checkpoint from `30e6353`, implemented in `7b6f9a2`. It grants no VPS
installation, collector installation, native acceptance, epoch or launch authority.

New journals select protocol 3. Existing protocol-1 journals keep their historical
behavior; protocol-2 journals retain snapshot-only continuation and are never
upgraded. Protocol-3 substep receipts bind the exact parent intent, operation and
mutation intent as well as the existing proposal, resource, expected effect and
observed outcome. Classification rejects cross-bound receipts and duplicate
intents/outcomes. Snapshot continuation checks these bindings under protocol 3.

Protocol 3 additionally allows partial configuration continuation after separate
reconciliation and fresh execution authority. Every attempted configuration must
have an unchanged positive acknowledgement; unstarted files must remain absent.
Execution recomputes generated configuration hashes and skips acknowledged writes.
The immediate parent identity is bound and symlink ancestors are rejected.
Changed bytes, replaced or deleted files, moved/replaced parents, unacknowledged
writes and attempted-but-absent files cannot authorize replay. This does not add
continuation rights for Docker, dependencies, units or other external effects.

An independent review agent reproduced two issues during review: missing snapshot
binding checks and unchanged files reached through replaced parent symlinks. Both
were corrected and covered by negative regressions. Review is limited to this
component change; it does not approve the complete proposal. Exact reviewed file
hashes and verification dispositions are recorded in the accompanying
[machine record](protected-runtime-recovery-v3-20261023.json).

Focused recovery/substep regressions pass 52 tests. Final `make check` passes
1,924 tests with 58 skips, followed by all 8 frozen-contract checks. Skipped Linux
and PostgreSQL tests do not establish rehearsal acceptance. No release bundle or
complete installation proposal was regenerated; future proposal closure must bind
these changed sources and obtain its own exact-set review.

Read-only local inspection observed Darwin/arm64, an unreachable Docker Desktop
daemon and no running QEMU/Linux guest. The retained emulator was neither started
nor modified. Its previously recorded failure against the unchanged 0.8-second
helper deadline remains unresolved. No VPS action or administrator installation
occurred. Only pytest-owned temporary files were created for the tests; no retained
trial resources were deleted. There was no infrastructure purchase, evaluation,
capacity investigation, public listener, notification, publication or backup work.

| Gate | Disposition |
|---|---|
| Implementation | Partial. Protocol 3 receipt bindings and acknowledged configuration continuation added. Complete reusable fixture, remaining external-effect recovery/rollback work and 21 additional executable scenario mappings remain unfinished. |
| Rehearsal | Unpassed. Local synthetic/filesystem tests pass; no complete concrete installation, installed inspection, interruption recovery, control acceptance and rollback rehearsal. |
| Privileged host facts | Blocked. Successor administrator installation and complete scheduler/reference, at, other-owner daemon, UID/delegation and output-preservation evidence remain outstanding. No fixture result establishes actual-host facts. |
| Independent review | Scoped component review only. Complete frozen installation/rollback/acceptance set does not yet exist and has not passed review. |

The next operation remains independent engineering under the
[implementation plan](../../PROTECTED_RUNTIME_IMPLEMENTATION_PLAN.md): complete the
owned disposable fixture, durable external-effect recovery and rollback, and all
27 executable scenario paths, then freeze and review that exact set. Privileged
facts and native rehearsal are separate requirements. Epoch-policy replacement
remains a later launch dependency. Do not request protected-runtime installation
authority from this checkpoint.
