# Diagnostic engineering checkpoint — 2026-10-19

**The requested diagnostic investigation is incomplete. No native generation is
admitted by this checkpoint.** The storage blocker was resolved by the separate
[lean-launch cleanup](lean-launch-cleanup-20261019.md). There is still no complete,
independently reviewed native diagnostic callback/controller. The previous private
draft remains reference material and must not be executed. Full-rehearsal approval
is not ready; do not generate an epoch or prepare an affirmative approval packet.

## Implemented and locally verified

Source checkpoints `12e9a20` and `db1c581` introduce separate diagnostic helpers.
They do not change the application, deployed monitor, production rehearsal,
authentication parameters, worker/evaluator bytes, profiles, scoring or limits.

- `scripts/production_diagnostic.py` validates the new protocol, preserving the
  existing 900-second debit, 300-second preflight, two 3,000-second generations,
  final 900-second cleanup reserves, zero additional spending and no retry/reset.
  It checks the exact ordered 50 cases from `mldsafail.development.public_cases`,
  immutable image/archive identifiers and required configuration/source digests.
  These are pure validation primitives, not proof that supplied artifacts or
  current host ownership have been independently inspected.
- `scripts/production_diagnostic_fixture.py` creates a synthetic user, ordinary
  scoped token using the unchanged hasher, running submission and unexpired lease.
  Its canonical private serialization preserves IDs, hash, timestamps and expiry.
  Restoration refuses expiry, altered bytes, epoch-bearing submissions, unexpected
  scientific rows and unowned core IDs; it rolls back failed replacement. Normal
  authenticated-read rate state is cleared on restoration. Fixture creation is
  deliberately single-use against an empty database; a failure after token
  creation committed is terminal setup failure, never implicit recreation.
- `scripts/production_diagnostic_instrumentation.py` supplies opt-in web-worker
  timing wrappers for authentication, hash verification, connection acquisition,
  queries (including failed queries) and commit. It retains normal verification,
  dummy verification, revocation, scope and expiry behavior. Request records have
  generated correlation IDs, approved routes/statuses and timing fields only.
  Sink errors retain an in-process failure flag; the future controller must
  observe that flag and stop the phase. Nothing installs these helpers into the
  running deployment or retained images.
- `scripts/production_diagnostic_probes.py` provides the 120-request/60-second
  alternating comparison with ten threads, two-second HTTP timeout, independent
  observation, absolute scheduling, 100 ms lateness rejection, partial records
  and bounded draining. The separate legacy experiment executes hash-checked
  historical scheduler bytes, with measured dispatch, queue, HTTP and ownership
  timing. Hashing and compilation use the same buffer. The legacy function still
  requires an owned outer process enforcing its 600-second ceiling.

Independent helper review reproduced and found three defects during engineering:
slow publication could admit late HTTP dispatch; the legacy loader read source
again after hashing; a secondary evidence-error callback could escape teardown.
All were corrected. Final re-review found no remaining helper-only blocking defect
and independently ran **33 focused tests**. This review explicitly **does not
approve native admission**. Tests use local synthetic databases and mocked HTTP;
there is no PostgreSQL/native performance claim.

## Required work before generation one

The following remain unimplemented or unverified; these are engineering tasks,
not a request for the owner to reauthorize the already authorized investigation:

1. Complete the separate native callback/controller using owned processes,
   isolated-daemon provisioning and existing cleanup barriers. Preserve the
   production rehearsal's independent fresh-epoch contract.
2. Bind the complete actual source/import/configuration inventory, images,
   archive checksums, fixture, workload, instrumentation, deadlines and cleanup
   protocol to an independently reviewed private generation packet. Digest syntax
   validation alone is insufficient. Freeze and hash the actual legacy source.
3. Implement durable locked budget-start/terminal records covering setup, imports,
   probes and cleanup, and an independent outer deadline/termination path. A
   partial generation consumes its generation; do not retry or reset the debit.
4. Perform the fresh <=300-second ownership/jobs/protected-identity/resource
   preflight under serialization. Old cleanup receipts cannot establish current
   absence. Keep the 5 GiB floor and existing RAM requirements.
5. Install fresh domains, short sockets, a separate PostgreSQL volume, synthetic
   credentials and loopback listeners with dispatch disabled and delivery paused.
   Export the one canonical fixture once, then restore it before comparable
   phases and generation two; its fixed 24-hour expiry must cover both.
6. Add cancellable sequential worker dispatch and separate lifecycle/worker/
   observer client and evidence journals. Restart the exact public sequence at
   zero each loaded phase; retain its completed prefix and unfinished invocation.
7. Add the actual rendered monitor's three idle/three loaded invocations,
   component overhead/import/connection/identical lease-query probes, query/parse/
   timeout failure classification, read-only database-wait observation and
   one-second resource sampling. The current ten-second monitor command timeout
   and full-mode backup requirements remain unchanged.
8. Integrate comparison, legacy and final harnesses with fixture restoration,
   instrumentation enable/disable, monitor stop, live durable publication,
   cancellation/quiescence and independently verified cleanup. Cover interrupted
   setup/export, registry isolation, ownership loss, stale observers, outer
   ceilings, remaining-budget exhaustion and protected-identity preservation.

After generation-one cleanup and independent verification, classify measured
findings and declare a falsifiable mechanism/metric before any component fix.
Rebuild only affected application images if evidence warrants it, preserving
native amd64/Python 3.12.10/lock provenance. Freeze and independently review the
second generation. Repeat comparisons with the identical fixture/workload, then
run the existing corrected harness idle and loaded with heavy instrumentation
and monitoring stopped: 1,500 anonymous plus 60 authenticated requests over 300
seconds each, ten threads, two-second timeout, valid observation/pacing, all
requests complete, zero read/floor failures, p95 <1 second and p99 <2 seconds.
No third generation, automatic retry, private epoch or full rehearsal is included.

## Findings, budget and cleanup disposition

| Question | Current evidence | Disposition |
|---|---|---|
| Original monitor lease-inspection failure | Historical C receipts only | Cause unresolved; no monitor change |
| Original authenticated-read failures | Historical C receipts only | Cause unresolved; no authentication change |
| Existing corrected load harness on VPS | Local tests, no new native phases | Performance unvalidated |
| New diagnostic helper defects | Local reproductions and regression tests | Corrected locally; no native improvement claim |

This checkpoint performed **zero native operations**, started **zero diagnostic
generations**, built **zero images**, delivered **zero notifications**, created
**zero private epochs**, and incurred **$0 additional spending**. The conservative
prior debit remains **900 seconds**; 6,300 aggregate seconds remain, reserved as
300 + 3,000 + 3,000. No fresh ownership/resource receipt or new native cleanup
receipt is claimed. Existing protected installation/rollback and retained trial
artifacts were not accessed or changed. Existing retention exceptions still have
their 2026-10-26 review date. Nothing was pushed.

The canonical fixture created in tests is ephemeral synthetic test data, not the
private native fixture for either generation. No fixture expiry clock has been
started for the requested VPS investigation.

## Final local validation

After helper review, the HTTP comparison also gained the same explicit
`read_only_health=True` admission requirement used by the corrected production
load harness; an unreviewed callback fails before observer or request startup.
Final focused tests: **34 passed**. Final `make check`: **1,131 passed, 13 skipped**,
plus **eight contract checks passed**. Existing warnings remain. The independent
review ran the preceding 33-test helper checkpoint; this final opt-in delta is
covered locally and grants no native authority.

Private compact engineering records are retained under
`results/production-diagnostics/20261019/` (helper review and final check log).
These are local engineering records, not native cleanup/performance receipts.
