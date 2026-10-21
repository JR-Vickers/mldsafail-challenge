# MVP public-launch preparation review

## Capacity investigation cancelled — 2026-10-21

The owner dropped the standalone capacity investigation under the $0 budget,
including a temporary second VPS and a smaller shared-production-host substitute.
Do not request capacity-host selection, a measurement window or investigation
approval. No capacity measurements or certified host size resulted. The v8–v10
packets and investigation instructions below are historical preparation; do not
execute them. See the [current owner decision](PLAN.md#owner-decision--capacity-investigation-cancelled-2026-10-21).

Continue no-cost maintenance/scheduling/dependency review and remaining MVP
preparation. The existing epoch operator's capacity-evidence guard remains
unsatisfied and in force; an explicit reviewed execution-policy disposition is
needed before epoch approval. Cancellation does not pass or bypass that guard.
Separate native transport/fence/cleanup correctness checks and the audited
production epoch remain required. No provisioning, transfer, service change or
epoch is authorized by this decision.

## Next phase — workload scheduling and host protection

Follow the [implementation agenda](PLAN.md#next-engineering-phase--single-workload-scheduling-and-host-protection):
complete and verify one-heavy-workload exclusion across evaluations and
administrative operations, resource-aware launch deferral, host resource bounds,
verified termination before releasing ownership, and bounded admission/queues.
Reuse existing claim, floor and admission logic; deployed compatibility remains
to be verified. Specifically close stale-lease recovery that can requeue before
old-worker termination is established. Preserve zero-pending maintenance rules.

Prepare the reviewed operational policy and epoch-validator changes replacing
the measured-capacity prerequisite. Keep current guards until the replacements
are implemented and verified. Preserve frozen worker limits and score semantics;
single-workload execution does not certify that one job fits the VPS. No capacity
experiment or paid infrastructure is planned. After the controls/policy and exact
maintenance/restoration packet are ready, seek separate execution approvals, then
complete the audited epoch, configuration, HTTPS/OAuth, participant journey,
minimum operations and owner rollout review in that order.

Owner-directed review, 2026-10-19. This is a preparation plan, not authorization
for native experiments, a new epoch, public listeners, publication or invitations.
The rehearsal-C diagnostic investigation is abandoned. Its outcome and budget
remain in the [continuation report](acceptance/integration/production-diagnostic-continuation-20261019.md).
The [canonical plan](PLAN.md) records the current owner decision.

## Retained-artifact review completed

The [local artifact inventory](acceptance/integration/mvp-artifact-inventory-20261019.md)
and [owner decision packet](acceptance/integration/mvp-recommendation-20261019.md)
recommend the retained 0.5.0 candidate/compatible rollback subject to current
remote identity verification and explicit preview approval. The candidate
coordinator and integration participant artifacts verify locally; other image
transfers are truncated. Participant wheel checksums conflict and the retained
sdist includes diagnostic tooling, so publication preparation remains open.
The packet lists the concrete remaining tasks and separates owner decisions from
engineering gaps. This completes the local inventory portion of step 1 below;
it does not freeze a production configuration or authorize any launch operation.

## Session 1 remote verification

The [2026-10-19 verification report](acceptance/integration/mvp-artifact-verification-20261019.md)
confirms all seven selected archive hashes, saved-image identities and complete
Linux amd64 content. Candidate/compatible rollback source labels and worker
release/trusted bindings match retained manifests. Item 1 is **partial**: the
worker export source is known, but its original Git build commit is unsupported.
Recover that original build/source binding or obtain an explicit owner resolution
of the documented provenance limitation before closing item 1. No remote state
was intentionally changed. Session 2 participant packaging can proceed independently.

## Session 2 participant release

The [participant release report](acceptance/integration/participant-release-20261019.md)
records the selected wheel, clean source distribution, deterministic download bundle
and fresh installation checks. Item 2 is complete locally. Session 3 may prepare
production configuration; original worker provenance and all later launch gates remain open.

## Session 3 production preparation

The [preparation report](acceptance/integration/production-preparation-20261019.md)
and [status](acceptance/integration/production-preparation-20261019.json) record a
new private candidate and explicit preparation-mode checks. Item 3 is partial:
the selected web/coordinator are not locally resolvable in the current rootless
daemon, and trial-secret/OAuth-registration/isolation checks remain incomplete.
The [epoch procedure](PRODUCTION_EPOCH_PROCEDURE.md) is a draft; no production
wrapper, epoch, deployment or activation was performed. Resolve the exact blocker
under separate authority; do not substitute or load images during preparation.

## Session 3 image-resolution follow-up — 2026-10-20

The owner-authorized [image loading receipt](acceptance/integration/candidate-image-load-20261020.md)
closes the candidate web/coordinator resolution blocker in the existing rootless
daemon; services were unchanged. The owner accepted the missing original worker
build-commit limitation for this preview and confirmed the OAuth homepage/callback.
Historical evidence is not relabeled. Secret/storage checks, production tooling,
audited epoch/final cohort binding and later live gates remain open.

## Session 3 configuration and operation preparation — 2026-10-20

The [current report](acceptance/integration/production-preparation-20261020.md)
records passing source-bound configuration preparation with only the future
audited epoch unresolved. Loaded images and the accepted worker-provenance
limitation remain settled; supplied OAuth values match and URLs are confirmed.
Secrets differ from active and executed retained trials; withdrawn unexecuted C
has bound nonexecution evidence. Host mounts, storage and Compose namespaces
reconcile. The [production procedure](PRODUCTION_EPOCH_PROCEDURE.md) now has a
separate tested executable wrapper and a versioned private review packet.
Item 3 remains **partial pending item 4**. Independent review, separate owner
authorization, fresh execution receipts and scheduling/cgroup prerequisites are
still required. No epoch, deployment or live-service change occurred.

## Fresh-agent starting point

Owner direction in the current session: prepare the **0.5.0 research preview**;
ignore experimental 0.6.0 for this launch. Do not reopen its measurements,
adoption or migration. This selects the preparation scope, not public activation
or a claim of tamper-resistant timing. Distribution 0.5.1 supports benchmark 0.5.0.
C diagnostics remain abandoned and backups remain indefinitely deferred.

Use the eight-item checklist below as the current launch backlog. The local
inventory, remote archive checks and participant packaging are complete; the owner
accepted the documented original-worker provenance limitation for this preview.
Read the linked inventory and recommendation before
choosing artifacts. Historical acceptance packets retain their original outcomes;
do not turn their obsolete agendas into additional automatic launch tasks.

## What the owner has decided

Stop investigating C's monitor inspection, authenticated-read latency and load
pacing. The observed aggregate read failures are considered acceptable for an MVP;
retain them as known operational risk rather than requiring another diagnostic
campaign. C remains a failed historical rehearsal and actual monitor reliability
remains unverified. All 14 failures targeted the 60 scheduled authenticated reads:
99.10% success overall, 76.67% on that route in the loaded sample. The recorded
nominal phase duration does not establish reliable production error rates.
No authentication, sandbox, privacy, correctness or scoring protection is waived.

Keep backups indefinitely deferred, as previously directed. Do not reopen storage
provisioning. No public activation, release publication, recruitment, 0.6.0 adoption
or new private/production epoch is approved by abandoning diagnostics.

## Decisions that determine the launch scope

| Decision | Existing evidence | Needed for MVP |
| --- | --- | --- |
| Scoring/version | Owner selected 0.5.0 preview preparation and directed that 0.6.0 be ignored for now. | Publish accurate cooperative-timing limitations in the final approved packet; no 0.6.0 work is a prerequisite for this release. |
| Operational acceptance | C passed application/cohort/rollback/forward and seven fault assertions, but failed loaded reads and monitoring; load pacing is uncertain. | Record the narrower MVP risk acceptance and a small functional launch check instead of requiring the abandoned root-cause investigation. Functional correctness/privacy evidence still applies only to its exact release. |
| Recovery | Compatible application rollback is retained. Off-host backup and independent recovery custody are not configured. | Keep setup deferred; decide explicitly whether launch may proceed with unresolved data-loss risk. Application rollback does not restore a lost database, epoch or evaluation evidence. |
| Monitoring | Test-check failure/recovery emails were confirmed historically. Permanent service check is paused; its lease monitor failed. | Choose a basic HTTPS availability check and verify its signal/recovery, or explicitly accept manual checks for the initial rollout. Do not label lease/worker monitoring healthy from HTTP readiness alone. |

The preparation scope is settled. Final activation still requires a concrete
owner-reviewed packet recording applicable acceptance evidence, minimum monitoring
and the continuing data-loss/recovery risk. No historical failure is relabeled.

## Eight remaining public-release items

Items 1 and 2 have their preparation evidence and owner provenance resolution;
item 3 is partial pending item 4. Later runtime/launch gates remain open.
Historical scoped passes do not complete outstanding production checks.

| Item | Work | Completion evidence |
| --- | --- | --- |
| 1. Verify retained release artifacts | Recheck candidate `1c9ca9e`, matching rollback `26c5f2f`, frozen 0.5.0 worker, database and proxy on the VPS; record the owner provenance decision. | [Remote archive checks passed](acceptance/integration/mvp-artifact-verification-20261019.md); [candidate images loaded and worker-provenance limitation accepted](acceptance/integration/candidate-image-load-20261020.md). Original build commit remains unknown; no runtime rollback acceptance is invented. |
| 2. Finish participant packaging | Resolve wheel/checksum conflict; prepare clean source excluding diagnostic/operator tooling; align starter and quickstart. | Complete locally: [release manifest and review](acceptance/integration/participant-release-20261019.md), clean source/bundle and fresh install/starter checks. Nothing published. |
| 3. Complete production configuration | Validate existing supplied OAuth inputs and private draft secrets, isolated database/volumes/evaluator paths, exact images, quotas and supported version. | [Preparation passed](acceptance/integration/production-preparation-20261020.md) with only the future audited epoch unresolved. Item 3 remains partial pending item 4; full mode refuses the preparation manifest. Supplied secrets are retained. |
| 4. Establish production benchmark | Prepare and, under separate authority, create one fresh 0.5.0 production epoch, independently audit/seal it and bind reference costs/cohort. | Next engineering phase: verify shared single-workload scheduling, host protection and termination-safe recovery, and implement a reviewed operational-policy replacement for the measured-capacity gate. A new final packet, root scheduler visibility, maintenance/transfer approval and separate epoch authority remain pending. Completion still requires actual viability and independent audit on the selected host/worker; no retries or staging/C epoch reuse. |
| 5. Validate HTTPS and authentication | Establish trusted TLS and renewal/reload; verify real GitHub callback/login, secure sessions, CSRF and token creation/revocation/expiry. | Actual selected-deployment receipts with secrets redacted; synthetic rehearsal authentication is insufficient. |
| 6. Complete participant journey | Clean install, starter/public validation, immutable tiny solver submission with idempotency key, status, audited result, correct leaderboard cohort and cancellation. | One end-to-end receipt on the final package/application/worker/production cohort. No new load campaign or full C rehearsal. |
| 7. Finish minimum operations | Choose verified basic availability monitoring or explicit manual responsibility/cadence; prepare incident contact, queue pause, exact rollback/forward steps and refresh resources/isolation checks. | Chosen monitoring/procedure verified, image-bound recovery instructions and current resource receipt; backup deferral/data-loss risk recorded. HTTP readiness does not prove lease health. |
| 8. Review and execute approved rollout | Assemble exact release identities, evidence, limitations and activation/publication/small-cohort commands; obtain applicable owner approval before executing. | Concrete go/no-go record, approved live checks and publication/recruitment scope. Owner handles pushes/publication; no unsolicited invitations. |

## Suggested agent sessions

| Session | Items / deliverable |
| --- | --- |
| 1. Retained artifacts | Item 1; current availability/identity report, explicit gaps; no builds/evaluations. |
| 2. Participant release | Item 2; reviewed, checksummed local release and clean-install evidence. |
| 3. Production preparation | Items 3–4: complete single-workload/host-protection controls, reviewed capacity-policy replacement and exact maintenance/restoration packet; no epoch creation. |
| 4. Production benchmark | Item 4 after authorization; audited epoch/reference/cohort or preserved failed attempt with blocker. |
| 5. Deployment and operations | Items 5 and 7 under applicable authority; TLS/authentication and minimum operations evidence. |
| 6. Participant validation and launch packet | Items 6 and 8; final functional receipt and owner-reviewable rollout packet, followed only by approved execution. |

Sessions 1 and 2 are independent work packages. Later sessions proceed in order;
resolve identified artifact gaps before production execution. These are handoffs
between sessions, not an instruction to spawn parallel agents.

Each handoff records exact commits/artifacts/configuration identities, checks and
failures, remaining gaps, next authorized scope and concrete procedures. Keep
sensitive paths/evidence private, run relevant checks plus `make check`, and commit
validated checkpoints without pushing. Start every handoff with the settled scope:
**0.5.0 preview; 0.6.0 ignored; C diagnostics abandoned; backups deferred**.

## Completed work to reuse

- Existing VPS and console-verified SSH identity; recent read-only protected
  inventory/resource checks. Refresh only what the concrete launch operation needs.
- Supplied OAuth fields, private draft production configuration, Healthchecks
  account/check preparation and historical test-email delivery evidence.
- Retained immutable candidate/compatible rollback artifacts, public development
  workflow and scoped application/fault/rollback results from C. Match exact
  identities before relying on them; no blanket new combined-pass claim.
- Local pacing correction and diagnostic helpers/tests. These need not be deployed
  or expanded to launch the MVP; they establish no new native performance claim.

## Explicitly outside this preparation review

No resumed C diagnostics, extra load campaign, 0.6.0 adoption/performance campaign,
new backup provider walkthrough, extra VPS purchase, automatic epoch creation or
repeat of the full rehearsal. Historical scientific thresholds and failures remain
unchanged. The old launch ledger and dated packets retain their original stricter
scope; before executing an MVP launch, bind an explicitly approved narrower packet
instead of falsifying those gates as passed.

The immediate next work is the [production epoch review and maintenance
preparation](acceptance/integration/production-epoch-review-20261020.md), followed by
one separately authorized creation, independent audit and final configuration.
Sessions 1 and 2 already have their recorded local dispositions above. Inspect already supplied private setup before
asking for new inputs. The inactive partial diagnostic upload is a separate
maintenance item requiring current ownership/inactivity checks, not permission
to resume diagnostics or an automatic launch blocker.

Maintenance preparation update (2026-10-20): the [new proposal assessment](acceptance/integration/maintenance-proposal-20261020.md) separates v2 proposal and execution states. Local collector/source review is complete; privileged classification, safe drain, compatible capacity evidence, delegation and concrete restoration remain blockers. No maintenance/transfer approval is requested yet.

Maintenance feasibility update (2026-10-20): [v6 host-feasibility disposition](acceptance/integration/maintenance-feasibility-20261020.md) records read-only host RAM/cgroup and deployed-source/queue inspection. Capacity remains unresolved; the coordinator is restarting and deployed checkout admission/claim sources lack the reviewed mutex. Scheduling/reference closure and delegation remain incomplete. The [separate control proposal](acceptance/integration/maintenance-control-proposal-20261020.md) requires its own authorization; no control was implemented/acquired. Item 4 remains blocked, with no maintenance/transfer approval requested. Historical receipts stay unchanged.

Maintenance prerequisite decision update (2026-10-20): the [v7 owner decision request](acceptance/integration/maintenance-decisions-20261020.md) expands retained capacity searches, inspects system/user unit states and external sources read-only, and binds recursive scheduling and relative transfer dependency gaps. Compatible simultaneous demand/headroom, complete triggerability/reference closure, production delegation and a compatible fence remain unresolved. Item 4 stays blocked; the private v7 proposal is nontransferable and rejects execution. Owner decisions concern a separate capacity-investigation protocol and maintenance-control engineering, plus missing scheduling evidence. No maintenance, transfer, probe, resize or epoch approval is requested. Historical outcomes remain unchanged.


Maintenance prerequisite engineering update (2026-10-20): [v8 disposition](acceptance/integration/maintenance-prerequisites-v8-20261020.md) prepares a [bounded capacity protocol](MAINTENANCE_CAPACITY_PROTOCOL.md) and a separate local zero-pending fence with guarded epoch integration. Item 4 remains blocked: no compatible capacity measurements, complete scheduling/transfer closure, approved delegation or production supervisor/transport exists. The private v8 proposal remains nontransferable and rejects execution. Read-only valid template-instance and cgroup inspection ran; no probe, epoch, transfer, provisioning or VPS service change ran. Historical outcomes remain unchanged.
