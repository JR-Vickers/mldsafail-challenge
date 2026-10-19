# Diagnostic admission engineering — 2026-10-19

The requested investigation remains incomplete. No native generation was started,
no current host preflight was performed, and no full-rehearsal approval packet is
ready. This checkpoint closes two helper admission gaps; it does not implement
or approve the missing native controller/callback.

The protocol and PLAN now agree on the owner-authorized allocation: 900 seconds
already debited, one initial preflight of at most 300 seconds, and two generations
of at most 3,000 seconds, totaling 7,200 seconds. Each generation reserves its
final 900 seconds for cleanup and independent verification, ending measurements
by second 2,100. No timing ledger was initialized for the native investigation.

## Implemented

`scripts/production_diagnostic_state.py` provides a private locked budget journal
with exclusive, fsynced start and terminal records. Start intent precedes caller
provisioning. An interrupted slot remains consumed and charged at its full limit;
partial or ambiguous records fence further starts. Retries, skipped slots, a third
generation, in-place initialization, backwards time and boot changes fail closed.
Overruns retain their actual charge and prohibit advancement. The next generation
requires successful prior completion and a retained, start-bound independent
cleanup receipt whose bytes are checked again when reading history.

This journal is a control primitive: its caller must hold the host-wide operation
lock throughout native work and supply the actual kernel boot identity and
independent postflight. A receipt's assertions alone cannot prove process absence
or independent verification. No existing production lifecycle authority changes.

`scripts/production_diagnostic.py` now hashes actual regular artifacts, rejects
symlinked paths, detects file changes during hashing, and checks complete directory
inventories for missing/extra/changed inputs. Artifact admission checks source and
configuration inventories plus instrumentation, historical scheduler, cleanup
protocol, fixture and image archive bytes against the reviewed protocol. It also
requires the ordered complete phase schedule to fit the 2,100-second work window.
Legacy execution retains its exact 600-second outer ceiling; other phases require
headroom for transitions and termination.

Artifact hashing does not prove archive-to-image identity, fixture semantics,
complete imported closure, protected host identities or independent review. Those
checks remain requirements for the future native controller. Hash inputs again
before use and use immutable private copies while executing.

## Verification and review

Independent helper review found that an early journal version allowed a terminal
record to claim cleanup without a retained receipt. Exact record schemas and
receipt revalidation correct that defect. The reviewer reran **47 focused tests**
and found no remaining blocker within this helper scope. This review grants no
native admission. Tests cover interruption, consumed slots, retry refusal, cleanup
evidence changes, budget overrun, clock ambiguity, artifact changes and schedule
admission. PostgreSQL/native performance is not measured by these tests.

Final `make check` passed **1,144 tests with 13 skips**, followed by **eight
contract checks**. Existing warnings remain. `git diff --check` passed. No application,
authentication, deployed monitor, worker/evaluator or scientific score was changed.

## Unresolved findings and next required evidence

All native measurements remain unperformed: rendered monitor idle/loaded,
component timings, HTTP idle/loaded, historical scheduler and final corrected
load idle/loaded. Their causes/performance remain unresolved, not failed or passed
new measurements. No evidence-supported application/monitor fix can yet be selected.

Before generation one, implement and independently review the separate native
controller/callback, outer supervisor, identity-bound cleanup-only path, fresh
ownership/resource preflight, disposable deployment and instrumentation wiring,
canonical PostgreSQL fixture creation/export/restore, sequential frozen worker
workload, monitor/component/resource probes and full cancellation/quiescence.
Bind the actual imported closure, archive/image provenance and fixture validity.
Test those integrations and freeze the exact source before native admission.
The detailed task list in the earlier engineering receipt remains applicable.

Generation two requires independently verified baseline cleanup, findings and a
reviewed comparison proposal. Final corrected load acceptance and independent
cleanup remain mandatory. No third generation, private epoch, full rehearsal,
notification delivery, publication or activation is authorized by this checkpoint.

Native spending remains **$0** and the existing debit remains **900 seconds**.
No native fixture was created, no expiry clock started, and no deployment artifact
was accessed, removed or modified. Existing retention exceptions remain owned by
the repository owner with review date **2026-10-26**; no new bulky trial artifacts
were created. No new native cleanup or ownership receipt is claimed.
