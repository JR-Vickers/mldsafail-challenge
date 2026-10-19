# MVP public-launch preparation review

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

## Fresh-agent starting point

Owner direction in the current session: prepare the **0.5.0 research preview**;
ignore experimental 0.6.0 for this launch. Do not reopen its measurements,
adoption or migration. This selects the preparation scope, not public activation
or a claim of tamper-resistant timing. Distribution 0.5.1 supports benchmark 0.5.0.
C diagnostics remain abandoned and backups remain indefinitely deferred.

Use the eight-item checklist below as the current launch backlog. The local
inventory and remote archive checks are complete; resolve the documented worker
provenance gap or proceed with independent local participant packaging. Read the linked inventory and recommendation before
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

Item 2 is complete locally; the other seven items remain open or partial.
Historical scoped passes do not complete outstanding production checks.

| Item | Work | Completion evidence |
| --- | --- | --- |
| 1. Verify retained release artifacts | Recheck candidate `1c9ca9e`, matching rollback `26c5f2f`, frozen 0.5.0 worker, database and proxy on the VPS; recover worker provenance. | Partial: [remote archive checks passed](acceptance/integration/mvp-artifact-verification-20261019.md); original worker Git build provenance remains unresolved. No silent replacement. |
| 2. Finish participant packaging | Resolve wheel/checksum conflict; prepare clean source excluding diagnostic/operator tooling; align starter and quickstart. | Complete locally: [release manifest and review](acceptance/integration/participant-release-20261019.md), clean source/bundle and fresh install/starter checks. Nothing published. |
| 3. Complete production configuration | Validate existing supplied OAuth inputs and private draft secrets, isolated database/volumes/evaluator paths, exact images, quotas and supported version. | Private source-bound preflight passes with no placeholders or unintended staging reuse. Do not request already supplied secrets again. |
| 4. Establish production benchmark | Prepare and, under separate authority, create one fresh 0.5.0 production epoch, independently audit/seal it and bind reference costs/cohort. | Viability and audit pass on the exact selected host/worker; no staging/C epoch reuse or automatic replacement after failure. |
| 5. Validate HTTPS and authentication | Establish trusted TLS and renewal/reload; verify real GitHub callback/login, secure sessions, CSRF and token creation/revocation/expiry. | Actual selected-deployment receipts with secrets redacted; synthetic rehearsal authentication is insufficient. |
| 6. Complete participant journey | Clean install, starter/public validation, immutable tiny solver submission with idempotency key, status, audited result, correct leaderboard cohort and cancellation. | One end-to-end receipt on the final package/application/worker/production cohort. No new load campaign or full C rehearsal. |
| 7. Finish minimum operations | Choose verified basic availability monitoring or explicit manual responsibility/cadence; prepare incident contact, queue pause, exact rollback/forward steps and refresh resources/isolation checks. | Chosen monitoring/procedure verified, image-bound recovery instructions and current resource receipt; backup deferral/data-loss risk recorded. HTTP readiness does not prove lease health. |
| 8. Review and execute approved rollout | Assemble exact release identities, evidence, limitations and activation/publication/small-cohort commands; obtain applicable owner approval before executing. | Concrete go/no-go record, approved live checks and publication/recruitment scope. Owner handles pushes/publication; no unsolicited invitations. |

## Suggested agent sessions

| Session | Items / deliverable |
| --- | --- |
| 1. Retained artifacts | Item 1; current availability/identity report, explicit gaps; no builds/evaluations. |
| 2. Participant release | Item 2; reviewed, checksummed local release and clean-install evidence. |
| 3. Production preparation | Item 3 and item 4 procedure preparation; reviewable private configuration and exact proposed epoch operation, without creating it. |
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

The immediate next work packages are sessions 1 and 2 above. The local inventory
and recommendation are complete. Inspect already supplied private setup before
asking for new inputs. The inactive partial diagnostic upload is a separate
maintenance item requiring current ownership/inactivity checks, not permission
to resume diagnostics or an automatic launch blocker.
