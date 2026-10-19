# MLWE competition implementation and acceptance plan

Retention update, 2026-10-19: the owner adopted
[lean-launch retention](RETENTION_POLICY.md) and explicitly authorized immediate
cleanup. That policy supersedes blanket requirements below to retain complete
answered trials, duplicate source copies, old caches or every release. Historical
outcomes remain unchanged; retain compact records and targeted exceptions. Active
resources, one verified rollback and supporting scientific evidence stay protected.


Updated 2026-10-18. This is the current authoritative implementation plan.
The [pre-integration plan](archive/PLAN_PRE_INTEGRATION_20261013.md) preserves
historical 0.4.0 contracts and dated agendas. Frozen scientific requirements
remain in [PRIMITIVE_SELECTION_SPEC.md](PRIMITIVE_SELECTION_SPEC.md); this
consolidation changes supported interfaces, not profiles or score meaning.

## Start here: lean cleanup complete; diagnostics remain pending

The owner adopted [lean-launch retention](RETENTION_POLICY.md) on 2026-10-19
and authorized immediate cleanup. [The completed maintenance receipt](acceptance/integration/lean-launch-cleanup-20261019.md)
records 26.07 GiB recovered, leaving 31.40 GiB available. Old stopped image
stores, duplicate source copies and obsolete release artifacts were removed
with compact run records retained. The running deployment, one compatible
rollback, unresolved C failure evidence and supporting scientific data remain.
Live readiness and unchanged protected identities passed final verification.
The previous storage-floor blocker is resolved; no diagnostic generation,
private epoch or new rehearsal was started.

Source checkpoint `f194bfaa69baff0f47b6137215e02ea5b693d138` repairs load pacing
locally; native cadence/performance remain unvalidated. The separate synthetic
no-epoch diagnostic callback remains incomplete. Complete its instruments,
common fixture/token identity, actual legacy-source binding, budget/lifecycle
admission and exact independent source/protocol review before execution. Carry
forward the existing 900-second diagnostic debit; cleanup does not reset it.
The authorized aggregate allocation is 900 seconds already debited, one 300-second
initial preflight, and two 3,000-second generations. Each reserves its final
900 seconds for cleanup and independent verification; measurements end by second
2,100. Interrupted starts consume their slot; no retries or third generation.

Read [the updated handoff](PRODUCTION_DIAGNOSTICS_HANDOFF.md) and
[bounded diagnostic protocol](PRODUCTION_DIAGNOSTIC_PROTOCOL.md). C remains
terminal and cannot restart. Monitor/authentication causes remain unproven;
no speculative application fix was made. No fresh full-rehearsal approval is
requested or authorized. Backups and separate activation gates remain deferred.
Commits are local on `main`; nothing was pushed.

## 1. Objective

Build a reproducible optimization competition for tiny, repository-generated
MLWE bounded recovery instances motivated by lattice cryptography. A participant
inspects the baseline, states a falsifiable hypothesis, changes an algorithm,
checks correctness, measures resources, records evidence and retains improvements
under a predeclared decision rule. Failed and partial experiments survive code
reverts. No benchmark-specific answer caching, seed special cases or fabricated
resource measurements are permitted.

## 2. Safety boundary

Every executable experiment uses repository-controlled tiny synthetic instances
within the frozen MLWE profiles. Reject externally supplied keys/signatures,
arbitrary cryptographic targets, deployed systems, production ML-DSA parameters,
signature forgery and removal of instance restrictions. Replace out-of-scope
work with a bounded synthetic experiment or theoretical/resource estimation.
ML-DSA supplies mathematical motivation; these profiles are structural analogues
and cannot establish production hardness.

## 3. Current supported interface

Participants submit a separate Python-only directory, at most 2 MB, containing
`solver.py` with `solve(public_instance)`. Start from
`examples/mlwe/primal-lll/solver.py`. The public input contains polynomial-ring
matrix `A`, target `t`, fixed dimensions/modulus/bounds and public instance identity.
Return complete bounded `s1` and `s2` satisfying `t = A*s1 + s2 (mod q)`, or `None`.
The evaluator independently verifies returned candidates.

`mldsafail clone` and submissions default to benchmark 0.5.0. Supported choices
exclude 0.4.0; new hosted 0.4.0 submissions are explicitly rejected. Historical
database rows, result readers, mathematical dependencies and rollback artifacts
remain preserved. [Unsupported archive tooling](archive/LEGACY_V040.md) retains
historical execution through explicit entrypoints.

`mldsafail run`, `mldsafail-bench` and `make bench BENCH_ARGS="..."` execute the
public MLWE development workflow, requiring solver/output paths, experiment ledger,
hypothesis, mechanism, parent revision and model. `mldsafail run --help` supplies
the exact arguments. The packaged runner is also available through the retained
`scripts/mlwe_pilot.py develop` compatibility entrypoint. A clean install needs
no source checkout to run the supported CLI. Actual evaluation requires the
frozen Python 3.12.10 interpreter and a compatible pinned Docker worker.

Hosted deployment configuration requires an explicit supported version. Frozen
0.5.0 remains the private compatibility default. Proposed 0.6.0 is inactive;
preparatory tooling and candidate rehearsal authority do not approve adoption
or default activation. Development Compose requires an audited MLWE epoch and
private evaluator root; historical seed setup is unsupported.

## 4. Experiment protocol and edit boundaries

1. Activate `.venv`, identify baseline/source/environment and record the hypothesis
   and comparison protocol before editing. Read [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md),
   [MLWE_LOCAL.md](MLWE_LOCAL.md) and [MLWE_PILOT.md](MLWE_PILOT.md).
2. Establish a public development baseline. The existing procedure evaluates
   50 fixed public cases, one warmup and three measured invocations each, and
   retains ledger metadata, source identity and resource/correctness outcomes.
3. Edit only the contestant Python workspace during solver experiments. Do not
   change trusted generator/verifier/scoring, profiles, locks, evaluator/worker,
   private epoch/reference costs or safety limits. Keep private evidence outside
   the contestant workspace and unavailable to the optimizer.
4. Run focused tests and public development comparisons against the retained
   baseline. Public development scores are diagnostic; never tune against private
   feedback. Preserve crashes, failures and partial evidence.
5. Freeze the candidate selected on public evidence, with its source digest and
   unchanged reference, before an authorized private evaluation. Predeclare
   sequential run order/repetitions on the same idle host and exact audited epoch.
6. Independently audit complete private evidence and apply the declared decision
   rule, anchored ties and uncertainty. Keep correct improvements within limits;
   revert regressing code while retaining all evidence. Commit sensible validated
   checkpoints; never push or merge into main automatically.

This integration is infrastructure work authorized by the consolidation plan;
its changes must not be mistaken for an ordinary contestant optimization.

## 5. Frozen 0.5.0 semantics

The private epoch fixes 100 ranked cases, 20 per each of five profile/eta cells,
with fresh private seeds/nonce and audited frozen reference costs. Cohorts bind
version, epoch, trusted source, interpreter/libraries/image and host environment.
Run sequentially on the same idle host; cross-cohort scores are not interchangeable.

Successful cases use the median of exactly three measured cooperative
`process_time` invocations, floored at one microsecond, divided by same-instance
reference cost. The clock includes parsing, contestant loading, lazy mathematical
imports, solving and verification; it excludes container startup, trusted adapter
imports before the clock and final serialization. This is a cooperative research
boundary, not hostile-code measurement integrity.

An ordinary failure in any measured invocation assigns the whole case the frozen
60-second penalty. Invalid candidates, including warmup candidates, make the run
ineligible. Five cell geometric means have equal weight; anchored 1% ties and the
frozen 2,000-draw profile/seed-cluster uncertainty procedure apply. Audit regenerates
instances and verifies candidates, identities and accounting; partial evidence
cannot rank. Private raw inputs/streams/candidates remain protected. Only reviewed
sanitized aggregate summaries and non-secret identities enter public artifacts.

## 6. Implemented engineering

The canonical development branch is `main` following the owner-authorized local
integration merge on 2026-10-16. The retained `engineering/integration` branch is based on audited public-launch
commit `6f60782cb7ddc7accc7cb325d1f0c8258082864b`. It selectively incorporates:

- `4602f45`: worker package-build starter preservation;
- `881d897`: endpoint preflight and failed-startup socket-retirement fencing;
- `8d80137`: bounded lifecycle attribution diagnostic;
- `d8a3ec7`: owned offline historical candidate-install protocol;
- `2b69ba3`: precise cooperative clock scope wording.

Newer public-launch recovery, publication and candidate-runtime implementations
remain authoritative. Supported historical defaults have been retired, with
archival execution and data intact. IP HTTPS and Healthchecks preparation are
implemented and inactive. [The handoff](INTEGRATION_HANDOFF.md) and
[integration ledger](acceptance/integration/launch-ledger.json) bind dispositions,
source/artifact identities, local checks and explicit limitations.

## 7. Scoped acceptance and preservation

All audited branch tips matched their prior inventory. A verified standalone
Git bundle, original inventory and metadata-only ignored/worktree inventory are
retained in protected ignored storage. Existing worktrees, successful/failed/partial
evidence and rollback artifacts were retained. Cleanup follows the lean-launch retention policy: retain a reviewable record
and remove eligible bulky trial artifacts after ownership checks. Each claimed milestone must name source, artifact,
environment, protocol and limitations.

Local focused tests, complete checks, wheel/import/starter verification and a clean
ARM64 worker build are scoped engineering evidence. A fresh installed CLI completed
all 50 public cases with 50 warmups and 150 measured successes and a required ledger.
They do not pass the separate native amd64, scientific reproduction, measurement,
production or external delivery gates. Historical native passes remain tied to
their original source/artifact; later integration changes need matching receipts.

At the initial 2026-10-13 integration, the existing VPS SSH endpoint timed out twice. Ownership
journals, live services and resource absence could not be inspected. No VPS mutation
or native acceptance was performed. The historical numbered checklist is absent;
this is a traceability limitation, not an invented gating requirement.

## 8. Measurement candidate and failed gates

The proposed 0.6.0 contract observes hierarchical cgroup-v2 CPU across the entire
exclusive worker lifecycle, including startup/imports/descendants and cleanup.
No startup subtraction, contestant timing trust, cost conversion or threshold
weakening is permitted. Missing accounting, surviving resources, partial invocation
sets and infrastructure failure yield no score. The whole-evaluation deadline is
1,200 seconds; ordinary case timeout/penalty remains 60 seconds.

Generations G and L completed 30 pairs and failed child CPU stability and empty
CPU overhead. G: CV 0.1164559302, empty median 395,795 microseconds. L: CV
0.0969114655, empty median 432,285.5 microseconds. Both exceeded limits of 0.05
and 250,000 microseconds; their empty wall p95 passed the five-second limit.
Historical cleanup was reported verified; those receipts prove no current absence.

The predeclared three-pair lifecycle diagnostic completed once on 2026-10-15 after
current ownership, ten-case startup and thirteen-fault accounting acceptance. Its
[packet](acceptance/integration/measurement-investigation-20261015.json) retains six
authoritative totals and sampled phase observations, with independently verified
cleanup and no accounting/window/threshold changes. It does not pass adoption. Any corrective
performance proposal needs a separately reviewed retained checkpoint before
execution, then the complete fault suite and at least 30 sequential pairs with
child CV ≤5%, empty median CPU ≤250,000 microseconds and empty wall p95 ≤5 seconds.
Fresh reference viability/audit/sealing and hosted version/evidence/cohort acceptance
remain required. [The adoption packet](MEASUREMENT_ADOPTION_PACKET.md) prepares
separate contract-adoption and production-default decisions; both remain deferred.

## 9. Native continuation

Reuse the existing Linux VPS; no additional host purchase is assumed. SSH access
and original ownership reconciliation succeeded on 2026-10-15; inspect current
exact recorded authority and reconcile unresolved generations before
dependent provisioning. Validate short socket roots before provisioning. Serialize
evaluation, maintenance, load and diagnostics with isolated disposable databases,
daemon/worker/operator domains, synthetic credentials and private evidence paths.

Run endpoint/refused/live/replaced socket and interrupted-publication cleanup tests;
recovery RPC lost acknowledgements, protected-set and encrypted local restoration;
interrupted/repeated activation and independent cleanup; full schema/data/result/epoch
audits; migration-free application rollback and forward repair; clean-build reproduction;
idle/evaluation load; cancellation, invalid answer, timeout, crash, retry, exhaustion
and stale lease cases. Preserve every disposition and independent final cleanup.
Native protocols already specify source/helper/callback/artifact authority.

Existing private staging evidence access and live service changes require separately
authorized concrete operations. Unknown ownership fences stop dependent operations,
while unrelated engineering continues. Never infer absence from old reports or
manufacture a score to compensate for infrastructure failure.

## 10. Production, recovery, notifications and pilot

The [2026-10-16 disposable production receipt](acceptance/integration/production-rehearsal-20261016.md)
tracks service-only monitoring, immutable release/configuration, fresh audited epochs
and disposable rehearsal/cleanup separately. A failed its retry orchestration
deadline; B passed all seven fault assertions but failed monitor startup with
systemd `216/GROUP`. Both epochs passed their audits; both terminal cleanups and
scoped cache retirements passed independent verification with evidence retained.
Reviewed corrections address fixture Compose labels, monitor journal/phase races,
user-manager identity switching and owned-client output capture. Source `a06bf4a`
passed 1,068 tests (13 skipped) plus eight contract checks. Its three-invocation
native monitor canary and exact C prelaunch packet passed independent review.
C's fresh epoch, application/cohort/rollback/forward checks and all seven fault
assertions passed. Its evaluation load failed: 14/1,560 failed reads and p95
1.225 seconds (required less than one second). Scheduled monitoring separately
failed lease inspection. The recorded nominal 300-second duration does not establish
actual phase timing. Planned notification/recovery and missed-heartbeat tests were
not reached. Independent terminal cleanup/retention passed; protected staging is
unchanged and no disposable service or heartbeat remains. The owner confirmed the
unplanned DOWN email at the exact first negative receipt and paused the permanent
check. Full rehearsal remains incomplete. No automatic epoch replacement is
authorized. Backups stay indefinitely deferred, and successful service heartbeats
cannot imply production acceptance.
Reviewed diagnostic-only checkpoint `69cbd61` records sanitized inspection/request
errors and elapsed/pacing metrics without changing the frozen limits or C's result.
Focused checks passed 123 tests; `make check` passed 1,074 tests with 13 skips plus
eight contract checks. It has not been executed in another native rehearsal.

On 2026-10-16 the owner confirmed readiness to begin guided production preparation,
superseding the earlier setup deferral. The [production setup handoff](PRODUCTION_SETUP.md)
records the setup sequence; its historical monitoring/email agenda is superseded
by the diagnostics handoff above. The owner subsequently deferred backup
setup indefinitely; the production recovery acceptance gate remains open. Preparation can proceed alongside
measurement and native acceptance; public activation remains separately gated.

The prepared production origin is `https://178.128.17.58`, with GitHub callback
`https://178.128.17.58/auth/callback`. [IP production](IP_PRODUCTION.md) describes
Certbot 5.4+ webroot IP issuance, the shortlived certificate profile, read-only
Caddy certificate mounts, challenge-only bootstrap and inactive renewal/reload
units. Secure cookies and trusted TLS verification remain required. Private
rehearsal uses new secrets, separate database/evaluator state and loopback bindings.
Public listener/CA issuance and OAuth acceptance wait for owner activation/inputs.

Encrypted off-host recovery acceptance requires owner-supplied scoped storage and
independently retained recovery credentials. Upload alone is insufficient: restore,
database/schema/epoch/evidence audit, retention/freshness and cleanup must pass.
Existing local synthetic evidence does not establish owner custody or off-host proof.

[Healthchecks setup](HEALTHCHECKS.md) prepares fixed failure/recovery and regular
heartbeat signals: five-minute service period with ten-minute grace, daily recovery
with four-hour grace. Backup success follows upload, restore/audit and cleanup.
Endpoints remain private; local retries/failure/recovery tests do not establish real
email or missed-heartbeat delivery. Account setup, recipients and actual delivery
authorization remain owner inputs.

The release/rollback/incident packet and three-participant pilot protocol are in
[INTEGRATION_HANDOFF.md](INTEGRATION_HANDOFF.md). Artifacts remain unpublished.
Recruitment and public activation are deferred until applicable gates and explicit
owner decisions. Pilot usability observations cannot adopt a measurement contract.

## 21. Development plan

1. Local baseline cleanup ordering and full post-switch epoch/result audits were repaired in source checkpoint `063ab091480df5cd3eda564bedfb31edc303371e`; ledger and disposition updates were committed as `09245fc`. Focused lifecycle/baseline/reproduction tests passed, and `make check` passed with 969 tests, 13 skipped, plus 8 MLWE contract checks. Native rollback acceptance remains deferred pending independent review and exact retained compose/backup/recovery helper inspection; no native operation was run. Exact installation/reproduction prerequisites also remain unresolved; see [current handoff](INTEGRATION_HANDOFF.md). Scoped startup, faults, bounded diagnostics, RPC loss and local encrypted recovery passed; combined acceptance remains incomplete.
2. Review a separately frozen corrective performance proposal; the single diagnostic completed and G/L failures remain unchanged. The [2026-10-16 in-container profile](acceptance/integration/worker-profile-result-20261016.md) completed its control and instrumented probes and found missing bytecode caches plus repeated source compilation, motivating an independently reviewed build-time bytecode proposal. These observations do not pass measurement acceptance. The owner authorized native acceptance on the existing VPS and is ready to begin guided [production preparation](PRODUCTION_SETUP.md). Exact-source reviews and ownership checks remain prerequisites.
3. Produce passing exact-source measurement/reference/hosted proof before asking
   for contract adoption, followed separately by any default activation decision.
4. Accept owner-supplied off-host custody and email delivery, privately rehearse
   production and review the exact release/configuration/rollback identities.
5. Obtain separate approval for public listeners, publication and recruitment.

Before every engineering handoff, run relevant focused tests and `make check`.
Record unavailable environments and inputs as deferrals, preserve unsuccessful
attempts, commit checkpoints, and leave publication to the repository owner.

### Diagnostic engineering checkpoint, 2026-10-19

The separate no-epoch diagnostic controller/callback and local verification are
complete at checkpoints `a29c553` and `544dead`. Independent source review passed;
`make check` passed with 1,170 tests, 14 skipped, plus eight contract checks.
The sole fresh native preflight failed strict SSH host identity verification
before remote execution. Neither generation started. The durable ledger charges
933 seconds including the existing debit and fences continuation after failed
preflight. Monitor/authentication/legacy causes and native pacing remain unresolved.
The [final findings report](acceptance/integration/production-diagnostic-findings-20261019.md)
records required identity evidence, unchanged fixture expiry, independent cleanup
and retention. No full-rehearsal approval packet is warranted.
