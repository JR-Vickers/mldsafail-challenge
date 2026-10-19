# MVP public-launch preparation review

Owner-directed review, 2026-10-19. This is a preparation plan, not authorization
for native experiments, a new epoch, public listeners, publication or invitations.
The rehearsal-C diagnostic investigation is abandoned. Its outcome and budget
remain in the [continuation report](acceptance/integration/production-diagnostic-continuation-20261019.md).
The [canonical plan](PLAN.md) records the current owner decision.

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
| Scoring/version | 0.5.0 is the supported frozen private contract; timing is cooperative. 0.6.0 whole-worker accounting failed its gates and is unadopted. | Explicitly choose a 0.5.0 research preview with its timing limitations, or keep public scored competition gated on separately approved accounting. Do not claim tamper-resistant timing or silently adopt 0.6.0. |
| Operational acceptance | C passed application/cohort/rollback/forward and seven fault assertions, but failed loaded reads and monitoring; load pacing is uncertain. | Record the narrower MVP risk acceptance and a small functional launch check instead of requiring the abandoned root-cause investigation. Functional correctness/privacy evidence still applies only to its exact release. |
| Recovery | Compatible application rollback is retained. Off-host backup and independent recovery custody are not configured. | Keep setup deferred; decide explicitly whether launch may proceed with unresolved data-loss risk. Application rollback does not restore a lost database, epoch or evaluation evidence. |
| Monitoring | Test-check failure/recovery emails were confirmed historically. Permanent service check is paused; its lease monitor failed. | Choose a basic HTTPS availability check and verify its signal/recovery, or explicitly accept manual checks for the initial rollout. Do not label lease/worker monitoring healthy from HTTP readiness alone. |

Recommendation: prepare a small 0.5.0 research preview if the owner accepts its
cooperative scoring limitation, with the known loaded-read risk documented. Keep
0.6.0 work separate. This recommendation does not supply the owner decision or
silently change the existing public scoring requirements.

## Essential preparation, in order

1. **Select and freeze the release.** Inventory the intended application, worker
   and participant wheel/source/checksum artifacts and compatible rollback. Match
   retained build/install/scientific evidence to those identities. The running
   private deployment is not automatically the intended public release. Prefer
   verified retained artifacts; build only for an identified source/artifact gap.
2. **Finish production configuration.** Use the existing private OAuth inputs and
   draft secrets on VPS 178.128.17.58. Verify fresh production secrets, separate
   database/volumes/evaluator paths, supported version and exact image IDs.
   Production epoch/cohort binding is still pending; any required generation and
   audit needs a concrete separately authorized operation. Never reuse C by
   rewriting its ownership or treat the diagnostic fixture as launch data.
3. **Validate the public identity and login.** The prepared origin is
   `https://178.128.17.58` with callback `/auth/callback`. Under explicit activation
   authority, establish trusted HTTPS, certificate renewal/reload and real GitHub
   OAuth; check secure sessions, CSRF and token creation/revocation/expiry. OAuth
   fields are already supplied; live login/callback acceptance remains unverified.
4. **Check the participant journey once on the selected release.** Install the
   exact distribution in a clean environment, clone/run the starter, submit an
   immutable approved tiny-instance solver with an idempotency key, follow status,
   verify the independently audited result and correct leaderboard cohort, and
   check cancellation. Keep private inputs/credentials/evidence inaccessible and
   out of public artifacts. This is a scoped functional check, not another load
   investigation or authority to run a full rehearsal.
5. **Prepare operations for a small rollout.** Confirm basic availability checking
   or the explicit manual alternative, an incident contact/procedure, queue pause
   and application rollback instructions, current disk/RAM and worker isolation.
   Respect the deferred lease investigation and backup decision. Inventory the
   interrupted upload before removing eligible inactive files; it is not a runtime
   service and must never be executed as an approved release.
6. **Review and publish only the approved material.** Review wheel/source,
   checksums, quickstart, score meaning/limitations and sanitized examples. Remove
   secrets, private epochs, raw candidates/database dumps and operator evidence.
   Present the exact activation commands, release identities and remaining risks.
   Obtain distinct approval for public activation, publication and recruitment;
   begin with a small owner-approved cohort rather than an unbounded rollout.

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

The immediate next preparation task is a read-only local release/evidence inventory
and concrete 0.5.0-preview decision packet. That resolves the scoring/release scope
before provisioning or transferring another environment. Remaining questions about
new inputs should be asked only after inspecting the already supplied private setup.
