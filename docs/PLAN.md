# MLWE competition implementation and acceptance plan

Retention update, 2026-10-19: the owner adopted
[lean-launch retention](RETENTION_POLICY.md) and explicitly authorized immediate
cleanup. That policy supersedes blanket requirements below to retain complete
answered trials, duplicate source copies, old caches or every release. Historical
outcomes remain unchanged; retain compact records and targeted exceptions. Active
resources, one verified rollback and supporting scientific evidence stay protected.


Updated 2026-10-21. This is the current authoritative implementation plan.
The [pre-integration plan](archive/PLAN_PRE_INTEGRATION_20261013.md) preserves
historical 0.4.0 contracts and dated agendas. Frozen scientific requirements
remain in [PRIMITIVE_SELECTION_SPEC.md](PRIMITIVE_SELECTION_SPEC.md); this
consolidation changes supported interfaces, not profiles or score meaning.

## Start here: prepare an MVP launch; diagnostic investigation abandoned

### Owner decision — capacity investigation cancelled, 2026-10-21

The budget is $0. The owner dropped the standalone capacity investigation,
including both a disposable second VPS and a smaller test sharing the production
VPS, because the shared-host substitute would not provide the intended isolation.
Do not provision a measurement host, run a capacity workload, or request host
selection, a measurement window or capacity-investigation execution approval.
The [capacity protocol](MAINTENANCE_CAPACITY_PROTOCOL.md) and v8–v10 packets are
retained historical preparation. No capacity measurements or certified sizing
conclusion resulted. Their dated investigation agendas are superseded by this
decision; retain their evidence and unresolved outcomes unchanged.

Continue no-cost maintenance, scheduling and dependency review and remaining MVP
preparation. Cancellation does not waive the existing production epoch operator's
capacity validator: its evidence requirement remains unsatisfied. Resolve that
requirement through an explicit reviewed execution-policy disposition before
requesting epoch approval; do not fabricate a receipt or silently bypass guards.
Separate native transport, fence and cleanup correctness checks, the audited
production epoch and the final participant journey remain launch requirements.
This decision authorizes no epoch, transfer, provisioning or VPS service change.

### Current implementation checkpoint — integrated locally; native acceptance pending

Production participant dispatch and v4 administrative roles now share the private
supervisor, native cgroup adapter and frozen-command router. Ownership survives
verified cleanup through database/operator commit acknowledgement. Systemd watchdog
and independent cleanup units, bounded output enforcement, generation-scoped replay,
control-specific v4 evidence validation and an offline deployment/recovery generator
are implemented. See [the runbook](SINGLE_WORKLOAD_DEPLOYMENT.md) for verification
scope and the immutable source packet. Historical v2/v3 capacity checks remain intact.

Native VPS acceptance has not run and requires separate owner authorization plus
current scheduling/service/delegation/socket/output-volume and compatible rollback
identities. Local Linux/PostgreSQL fixtures do not certify the installed VPS.
No deployment, epoch, capacity measurement or activation is authorized by this work.

### Current host preparation — bootstrap and installed acceptance remain separate

Local integration is complete at the source level. Versioned bootstrap preparation
now distinguishes proposed socket paths from installed births and validates
scheduling managers/accounts and rootless UID mappings. See the
[host-readiness record](acceptance/production-preparation/protected-runtime-readiness-20261021.md).
The read-only pinned-SSH collection succeeded; privileged scheduling visibility,
bounded persistent storage, installation/rollback command completion and full
native-control coverage still block an installation-ready proposal. No complete
bootstrap proposal is approved, and no installed acceptance is claimed.

First obtain owner-assisted privileged facts, then finish and independently review
the exact prerequisite/installation/restoration proposal. Installation requires its
own exact-byte authorization. Refresh observed socket/supervisor/cgroup/mount and
artifact identities after installation before seeking separate native-test authority.
Keep computation paused throughout. Proposed identities never certify installation.

Follow-up source checkpoint: [release and authority disposition](acceptance/production-preparation/protected-runtime-followup-20261021.md)
adds frozen-bundle verification, persistent inhibition proposal primitives,
all-account owner collection and exact single-use native case authority.
These helpers do not complete v3 installation/rollback or native coverage.
The [owner-console procedure](PROTECTED_RUNTIME_OWNER_COLLECTION.md) identifies
the outstanding privileged collection. Installation remains blocked; do not
request execution approval against incomplete source artifacts.

Current implementation progress: [mutation and termination evidence](acceptance/production-preparation/protected-runtime-mutation-evidence-20261022.md) records durable prerequisite substeps, failed-command/descendant evidence and independently measured cgroup cleanup. Fresh read-only VPS collection succeeded; privileged scheduling, delegation, UID and storage facts remain missing. Full installation recovery, complete fixture/acceptance runners and complete frozen-proposal approval remain unfinished. The earlier [installation checkpoint](acceptance/production-preparation/protected-runtime-proposal-checkpoint-20261022.md) and [paused handoff checkpoint](acceptance/production-preparation/protected-runtime-handoff-20261022.md) retain their original scope and outcomes.

The [next development phase](PROTECTED_RUNTIME_IMPLEMENTATION_PLAN.md) sequences
v3 integration, complete offline releases, recoverable installation/rollback,
installed verification and full control coverage. Its exit is an independently
reviewed installation proposal; VPS installation and native tests retain separate
authorization gates.

### Source requirements — single-workload scheduling and host protection

Owner direction, 2026-10-21: use the existing VPS and $0 budget to prevent
workloads piling up through queuing, exclusive execution and resource controls.
This replaces the capacity-investigation workstream; it does not claim measured
capacity or authorize deployment. Complete the following before epoch execution:

- Enforce one heavy workload at a time across participant evaluations and
  administrative epoch/reference operations. Preserve zero-pending maintenance
  admission and scheduling exclusion; queued participant work is not permission
  to enter maintenance. Cover alternate coordinators and restart owners.
- Check host and effective ancestor resources before launch; leave accepted work
  queued when resources are insufficient. Bound CPU, memory, PIDs, disk and output
  consumption while reserving resources for retained web/database/proxy services.
- Verify owned processes and containers have terminated before releasing workload
  ownership. Lease expiry alone must not permit a replacement workload to overlap
  the old one; ambiguous ownership or failed cleanup blocks subsequent launches.
- Verify submission-rate and queue bounds, returning bounded admission failures
  when full. Reuse existing admission controls rather than adding duplicate queues.

Current source already serializes evaluation claims under a database transaction
lock, checks resource floors and bounds admission. These are source observations,
not certification of the deployed release. The protected runtime floor is 1 GiB available
memory and 5 GiB free disk; it is not a reservation for the next workload. Expired
leases now remain blocked unless an explicit reconciler verifies termination.
Legacy expired jobs must not be reset to queued. Complete administrative-operation
exclusion, production routing and deployed compatibility before claiming host-wide
single-workload enforcement.

Prepare a concrete operational policy and corresponding epoch-validator changes
that replace the measured-capacity prerequisite, with explicit disclosure of
unmeasured capacity. Until reviewed replacements are implemented and verified,
the current capacity guard remains in force. Do not manufacture a passing
measurement or add an unconditional bypass. Keep frozen 0.5.0 worker limits and
score semantics: serialization prevents overlap but does not establish that a
single workload fits. Record insufficient-resource failures honestly.

Acceptance must cover competing coordinators, participant/admin contention,
low resources, queue saturation, expired leases with surviving workers, restart
interference and failed cleanup. Verify source and deployed identities separately;
refresh execution evidence only for the concrete approved operation.

The launch sequence is now: complete and verify these controls and the reviewed
policy; prepare exact maintenance/transfer/restoration commands; obtain separate
approvals for one production epoch and independent audit; finish production
configuration; verify HTTPS/OAuth and one participant journey; finish minimum
operations and present the owner rollout packet. Existing artifact and packaging
evidence is reused. No replacement capacity experiment, paid infrastructure or
benchmark-semantic change is part of this phase.


Owner decision, 2026-10-19: abandon the rehearsal-C monitor/authentication/pacing
investigation and review the remaining public-launch work. Do not resume its
preflights, transfers, measurements, diagnostic generations or corrective research.
Retain failed evidence and completed source checkpoints. Abandonment does not
turn rehearsal C or the interrupted artifact admission into a pass.

The owner considers the observed aggregate read failures acceptable for an MVP.
Record the scope accurately: 14 failures among 1,560 reads is 99.10% aggregate
success, but all 14 failures were on `/api/v1/me`. The historical schedule includes
60 authenticated requests, implying 46/60 (76.67%) authenticated-read success in
that loaded sample. This is neither a production uptime estimate nor a submission
success rate. Pacing fidelity and monitor failure causes remain unresolved.
The route breakdown is recorded here for informed launch review; it does not
reopen the abandoned investigation or assume a broader waiver of other gates.

The immediate work is the [MVP launch preparation review](MVP_LAUNCH_PREPARATION.md).
The owner selected 0.5.0 preview preparation and directed that 0.6.0 be ignored
for this release. Follow the [eight-item checklist and six-session handoff map](MVP_LAUNCH_PREPARATION.md#eight-remaining-public-release-items):
review exact retained artifacts and rollback,
validate real HTTPS/OAuth and the participant submission flow, decide basic
monitoring and deferred recovery risk, then present the concrete activation packet.
The previous full diagnostic/rehearsal sequence is not an automatic prerequisite
for this owner-directed MVP review. Any replacement acceptance scope must be
explicit; unresolved historical gates remain failed or deferred.

Production OAuth inputs and private draft secrets were already supplied; validate
the existing inputs rather than asking for them again. Backups remain indefinitely
deferred; do not restart storage selection or custody setup. Public activation,
CA issuance/listeners, publication, recruitment, measurement adoption and creation
of a production epoch still require their distinct applicable decisions.

Production preparation, 2026-10-20: the [loaded-image/owner-decision receipt](acceptance/integration/candidate-image-load-20261020.md)
records resolved candidate images, the accepted original-worker provenance limitation
and confirmed OAuth URLs. The [current preparation report](acceptance/integration/production-preparation-20261020.md)
records passing source-bound configuration preparation and tested separate
production epoch tooling. Item 3 remains **partial pending item 4**: the actual
audited epoch and final cohort do not exist. The next operation is independent review, maintenance preparation, then one separately
authorized production epoch. The earlier private packet is preserved as a historical
preparation candidate. [Current review](acceptance/integration/production-epoch-review-20261020.md)
found execution-critical gaps; the corrected operator requires a new packet.
[Root scheduling evidence has since been collected and retrieved](acceptance/integration/scheduling-collection-review-20261020.md),
with transfer and raw-section hashes verified. Scheduling-path and referenced-script
classification, maintenance dispositions, a complete evidence-bound receipt,
verified delegation and scoped maintenance/transfer approvals remain unresolved.
Scheduling exclusion is not yet verified. No epoch,
deployment, listener, OAuth login or notification occurred.

Use the documented VPS `178.128.17.58` and deployment SSH identity. The pinned
console fingerprint and recent host inventory are in the [continuation report](acceptance/integration/production-diagnostic-continuation-20261019.md).
Diagnostic charges remain 1,255 seconds, including a 55-second initial-preflight
overrun; neither generation started. The interrupted private source upload at
`/home/mldsafail/.mlf-diag-20261019` remains a maintenance cleanup item, with no
absence/deletion claim. Cleanup requires current ownership/inactivity checks and
must not restart measurements. Preserve the current installation, compatible
rollback and scientific evidence under [lean-launch retention](RETENTION_POLICY.md).

All historical sections below retain their dated outcomes. Nothing is pushed,
published, activated or sent to participants by this planning change.

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

## 21. Current development plan

The current backlog is the [eight public-release items](MVP_LAUNCH_PREPARATION.md#eight-remaining-public-release-items),
with [six suggested agent sessions](MVP_LAUNCH_PREPARATION.md#suggested-agent-sessions).
Use these as the fresh-agent entry point; 0.6.0 is outside this release scope.

1. Verify retained release artifacts on the VPS against the completed local inventory.
2. Finish participant packaging, checksums, clean source, starter and quickstart.
3. Complete private production configuration using already supplied inputs.
4. Prepare and execute the separately authorized fresh 0.5.0 epoch/audit/cohort operation.
5. Validate trusted HTTPS/renewal and real OAuth/session/token behavior.
6. Complete one selected-release participant submission/audit/leaderboard/cancellation flow.
7. Finish minimum monitoring/manual checks, incident response and exact rollback steps;
   record deferred backups and launch data-loss risk.
8. Present the exact go/no-go and rollout packet; activate, publish and recruit only
   within applicable explicit owner approval.

Keep abandoned diagnostic evidence and budget history unchanged. The inactive
partial upload is separate maintenance, requiring ownership/inactivity checks;
it does not reopen diagnostics or require a full rehearsal. Historical gates
remain recorded with their original disposition. The final preview packet must
state the applicable acceptance scope rather than silently waiving failed gates.

Before every engineering handoff, run relevant focused tests and `make check`.
Record unavailable environments and inputs as deferrals, preserve unsuccessful
attempts, commit checkpoints, and leave publication to the repository owner.

### Diagnostic engineering checkpoint, 2026-10-19

The separate no-epoch diagnostic controller/callback and local verification are
complete at checkpoints `a29c553` and `544dead`. Independent source review passed;
`make check` passed with 1,170 tests, 14 skipped, plus eight contract checks.
The sole fresh native preflight failed strict SSH host identity verification
before remote execution. Neither generation started. The durable ledger charges
965 seconds including the existing debit and fences continuation after failed
preflight. Monitor/authentication/legacy causes and native pacing remain unresolved.
The [final findings report](acceptance/integration/production-diagnostic-findings-20261019.md)
records required identity evidence, unchanged fixture expiry, independent cleanup
and retention. No full-rehearsal approval packet is warranted.


### Verified-VPS diagnostic continuation, 2026-10-19

The correct 178.128.17.58 console fingerprint and read-only host snapshot passed.
Source `8351bab` adds independently reviewed operational evaluation fencing;
make check passed 1,175 tests/15 skipped plus 8 contract checks, with 3 separate
real PostgreSQL guard tests. Artifact admission then timed out. The agent's
initial-preflight interval totals 355 seconds against 300 (55-second overrun);
aggregate charge is 1,255. Neither generation started. The partial remote source
root remains a targeted retained exception, not verified cleanup. No application
cause or native performance gain is established. The [current findings](acceptance/integration/production-diagnostic-continuation-20261019.md)
record actual charges, original fixture expiry and next required evidence. Stop
native work pending an explicitly revised bounded continuation; no ledger reset,
fixture renewal, third generation or full rehearsal is admitted.

Maintenance preparation update (2026-10-20): the [new proposal assessment](acceptance/integration/maintenance-proposal-20261020.md) separates v2 proposal and execution states. Local collector/source review is complete; privileged classification, safe drain, compatible capacity evidence, delegation and concrete restoration remain blockers. No maintenance/transfer approval is requested yet.


Maintenance inspection update (2026-10-20): see the [v2 inspection and blocked v3
proposal](acceptance/integration/maintenance-inspection-v2-20261020.md). New v3
execution requires a v2 evidence-bound scheduling review; historical approvals
are unchanged. The owner-console collection and private retrieval are complete;
the [partial scheduling review](acceptance/integration/scheduling-collection-review-20261020.md)
records 353 path entries, verified raw-section hashes and 310 regular-file hashes
rechecked without drift. Root and application-account crontabs are absent; the
inspected at service, command and spool locations are absent. Host-check and
database-backup timers are enabled and active; their settings were preserved.
All-path/reference classification, maintenance dispositions and a complete reviewed
receipt remain pending. The pasted collector has one extra trailing newline, so
a subsequent exact-source collection must bind the reviewed external script paths
before satisfying the current execution validator. Deployed fence compatibility,
compatible capacity and inspected delegation also remain required. Scheduling
exclusion remains unverified. No maintenance, operation-bundle transfer or epoch
execution is authorized by preparation.

Maintenance feasibility update (2026-10-20): [v6 host-feasibility disposition](acceptance/integration/maintenance-feasibility-20261020.md) records read-only host RAM/cgroup and deployed-source/queue inspection. Capacity remains unresolved; the coordinator is restarting and deployed checkout admission/claim sources lack the reviewed mutex. Scheduling/reference closure and delegation remain incomplete. The [separate control proposal](acceptance/integration/maintenance-control-proposal-20261020.md) requires its own authorization; no control was implemented/acquired. Item 4 remains blocked, with no maintenance/transfer approval requested. Historical receipts stay unchanged.

Maintenance prerequisite decision update (2026-10-20): the [v7 owner decision request](acceptance/integration/maintenance-decisions-20261020.md) expands retained capacity searches, inspects system/user unit states and external sources read-only, and binds recursive scheduling and relative transfer dependency gaps. Compatible simultaneous demand/headroom, complete triggerability/reference closure, production delegation and a compatible fence remain unresolved. Item 4 stays blocked; the private v7 proposal is nontransferable and rejects execution. Owner decisions concern a separate capacity-investigation protocol and maintenance-control engineering, plus missing scheduling evidence. No maintenance, transfer, probe, resize or epoch approval is requested. Historical outcomes remain unchanged.


Maintenance prerequisite engineering update (2026-10-20): [v8 disposition](acceptance/integration/maintenance-prerequisites-v8-20261020.md) prepares a [bounded capacity protocol](MAINTENANCE_CAPACITY_PROTOCOL.md) and a separate local zero-pending fence with guarded epoch integration. Item 4 remains blocked: no compatible capacity measurements, complete scheduling/transfer closure, approved delegation or production supervisor/transport exists. The private v8 proposal remains nontransferable and rejects execution. Read-only valid template-instance and cgroup inspection ran; no probe, epoch, transfer, provisioning or VPS service change ran. Historical outcomes remain unchanged.

2026-10-20 capacity preparation: [v9 engineering disposition](acceptance/integration/maintenance-prerequisites-v9-20261020.md)
adds local sampler, SQL helper protocol, supervisor/investigation contracts and
exclusive offline packet tooling. Item 4 remains blocked. Production adapters,
Linux acceptance, complete scheduling/transfer dependencies and an owner-bound
isolated host/window remain unresolved. No capacity workload, provisioning,
service mutation, transfer or epoch ran; no execution approval is requested.

2026-10-20 blocker follow-up: [v10 engineering and evidence](acceptance/integration/maintenance-prerequisites-v10-20261020.md)
adds the frozen worker lifecycle router, continuous bounded phase monitoring,
raw replay checks, native action adapters, crash cleanup and dependency relocation
tooling. Read-only service/runtime inspection and a bounded emulated worker-image
control smoke ran; no evaluation or capacity workload ran. Native end-to-end
acceptance, owner-only scheduling/runtime evidence, installed delegation and an
owner-bound host/window remain gates. The private v10 proposal remains blocked,
nontransferable and unauthorized; no capacity execution approval is requested.

Historical predecessor — 2026-10-21 local scheduling engineering: [implementation and blocked deployment
review](SINGLE_WORKLOAD_DEPLOYMENT.md) adds a durable host-gate library, conservative
resource policy, cleanup-gated stale-lease recovery and v4 policy-evidence checks.
Production coordinator/admin transport, native cgroup controls, socket service,
matching release and native acceptance remain unfinished; no host-wide enforcement
or launch readiness is claimed. The production epoch entrypoint continues to
reject v4, and historical v2/v3 capacity requirements remain unchanged. No
benchmark, epoch, transfer, provisioning or service change ran.


Historical predecessor — 2026-10-21 ownership lifecycle checkpoint: the [single-workload runbook](SINGLE_WORKLOAD_DEPLOYMENT.md#ownership-and-result-transaction-checkpoint-2026-10-21)
records ownership-scoped mutations, separate postflight/commit/release, bounded
generation-scoped replay and monitoring during blocked launch I/O. This is a
partial engineering checkpoint, not completion of production integration. The
native runtime, dispatcher/admin routing, enforced output bounds, independent
cleanup and executable deployment/recovery packet remain implementation work;
v4 execution remains disabled. Native acceptance additionally lacks separate
owner authorization and inspected host prerequisites. Historical receipts are
unchanged.


Historical predecessor — 2026-10-21 runnable control checkpoint: private supervisor/client/cleanup commands
and separate bounded monitor/control helper channels are available. A native
runtime helper, systemd abnormal-exit cleanup and production routing are still
missing; the [entrypoint runbook](SINGLE_WORKLOAD_DEPLOYMENT.md#runnable-control-entrypoints-checkpoint-2026-10-21)
records the exact current boundary. No native installation or acceptance ran.
