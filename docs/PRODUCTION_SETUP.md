# Production preparation and session handoff

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

Owner update, 2026-10-19: the rehearsal-C diagnostic investigation is abandoned.
Do not resume its preflights, transfers, generations or corrective research.
Current launch preparation is in [MVP_LAUNCH_PREPARATION.md](MVP_LAUNCH_PREPARATION.md)
and [PLAN.md](PLAN.md). Historical failures, 1,255-second charges and partial-upload
retention remain unchanged; this does not authorize activation or a new epoch.
The dated material below is historical.


Updated 2026-10-18. The owner began production preparation, superseding the earlier
request to defer setup. The disposable rehearsal is now terminal; the owner ended
the session and deferred diagnostics to a new one. Start with the
[diagnostics handoff](PRODUCTION_DIAGNOSTICS_HANDOFF.md).
The authoritative project plan remains [PLAN.md](PLAN.md).

Owner update, 2026-10-16: backup setup is deferred indefinitely. Do not resume
storage selection, backup provisioning or the credential-custody walkthrough
unless the owner reopens it. The existing production recovery acceptance gate
remains open. Current engineering work is inspection/load/pacing diagnosis;
measurement and later OAuth/public setup remain separate gates.

## Current position

The owner created a Healthchecks notification-test check and confirmed both actual
missed-heartbeat failure and recovery emails on 2026-10-16. The permanent service
check URL is saved and validated privately. It was connected only to disposable
rehearsal C after dry inspection. Scheduled checks then reported lease-inspection
failure; the owner's DOWN email matches the first failure at 10:01:28 UTC on
2026-10-18. C later failed evaluation load. Its monitor and temporary services are
stopped and cleanup/retention independently verified; the owner confirmed pausing
the permanent check. The planned notification/recovery tests were not reached.
The earlier disposable notification-test check is distinct from that permanent
check; its pause was requested but not independently recorded.
Fresh production OAuth fields are populated and privately stored; live OAuth
login and registration configuration have not been independently verified.
A private draft production environment has fresh database/session secrets and
the supplied OAuth fields. Immutable release/rollback images are retained and
verified; production epoch/cohort binding remains pending its own fresh activation
epoch. The draft is not deployable. Credentials and detailed progress
receipts live outside Git in the owner's private configuration directory.

The host monitor now supports explicit service scope with backups deferred;
default full scope retains mandatory backup freshness checks. Do not fabricate
backup freshness or treat a service heartbeat as production-readiness acceptance.
No storage provider or recovery custody has been configured. No production
provisioning or public activation is claimed.
Use the existing VPS; no additional host purchase is assumed.

Earlier owner-authorized native protocols do not authorize another epoch or a
restart of terminal C. Native source reviews, ownership reconciliation and
independent cleanup remain required for any later concrete protocol. Public listeners, trusted
certificate issuance, publication, recruitment, measurement-contract adoption and
default activation still require their applicable evidence and separate decisions.

## Work sequence

1. **Off-host backups and owner credential custody — indefinitely deferred.** Walk the owner
   through choosing storage and supplying narrowly scoped access. Keep production
   storage/repository credentials separate from staging. Establish independently
   retained recovery credentials and repository/configuration identifiers outside
   the VPS. Do not put secrets in Git, public artifacts or conversation text.
   Demonstrate encrypted upload, independent download/restore, full database/schema/
   epoch/evidence audit, retention/freshness and disposable cleanup. A configured
   bucket, successful upload or local synthetic restore alone does not pass.
2. **Monitoring and email delivery.** Guide account/check creation, recipient
   selection and private endpoint configuration using [HEALTHCHECKS.md](HEALTHCHECKS.md).
   Plan actual failure/recovery and missed-heartbeat delivery tests with the owner.
   Service cadence: five minutes with ten-minute grace; recovery cadence: daily
   with four-hour grace. Backup success follows verified restore/audit and cleanup.
3. **Production identity and configuration.** Prepare fresh production GitHub OAuth
   inputs, secrets and separate database/evaluator/recovery state. Follow
   [IP_PRODUCTION.md](IP_PRODUCTION.md) for the prepared IP HTTPS origin and OAuth
   callback. Bind exact release, image, configuration and rollback identities before
   deployment. Public CA issuance/listeners remain a later explicit decision.
4. **Private production rehearsal.** Exercise the reviewed configuration with fresh
   secrets, synthetic data, separate disposable state and loopback bindings. Verify
   submission-to-result behavior, isolation, recovery, rollback, monitoring and
   capacity. Preserve failures and independently verify cleanup.
5. **Launch review.** Review completed measurement, reference, hosted and operational
   acceptance evidence and the exact release/configuration packet. Obtain separate
   owner decisions for contract/default changes, public activation, publication and
   recruitment. Preparation alone does not approve launch.

Use the existing recovery and incident procedures in [OPERATIONS.md](OPERATIONS.md)
and [INTEGRATION_HANDOFF.md](INTEGRATION_HANDOFF.md); this checklist does not replace
their artifact, ownership, review or acceptance requirements.

## Engineering that can proceed alongside setup

- Prepare and independently review a build-time bytecode candidate motivated by
  the [native profile](acceptance/integration/worker-profile-result-20261016.md).
  Run the full fault suite and at least 30 sequential pairs under unchanged gates;
  reference and hosted acceptance follow a passing measurement result.
- Resolve historical Compose/helper mismatches and missing installation/reproduction
  artifacts; complete source review and outstanding native rollback, restoration,
  activation, failure and load acceptance. Existing scoped passes do not establish
  combined acceptance.

Serialize native diagnostics, evaluations, maintenance and rehearsals on the host.
Production preparation can advance while those gates remain open.

## Resume in a new session

Start with the [dated disposable rehearsal receipt](acceptance/integration/production-rehearsal-20261016.md)
and [diagnostics handoff](PRODUCTION_DIAGNOSTICS_HANDOFF.md), then consult the
[protocol](PRODUCTION_REHEARSAL.md). The owner selected compatible rollback
source `26c5f2f` after exact `4602f45` proved evaluator-incompatible. Monitoring
scopes and native release artifacts are implemented; do not repeat completed builds
or silently replace a failed fresh epoch. Historical acceptance remains separate.

Read [PLAN.md](PLAN.md), this document and the current integration handoff. The next
engineering task is diagnosis of C's inspection/load failures and pacing uncertainty;
completed monitoring implementation, retained builds and audited epochs are not
pending setup tasks. Another full rehearsal requires a reviewed concrete continuation
and explicit additional-epoch authority. Account inputs for
Healthchecks and OAuth have been supplied locally; request more only for a concrete
missing requirement. Backup setup is indefinitely deferred by owner decision.
First check for newer committed receipts or owner decisions; do not ask the owner
to repeat authorization already recorded here. Record each choice, scoped result
and remaining dependency without committing credentials. Commit validated
checkpoints and leave pushing/publication to the owner.
