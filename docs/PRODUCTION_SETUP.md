# Production preparation and session handoff

Updated 2026-10-16. The owner is ready to begin production preparation and wants
a guided walkthrough. This supersedes the earlier request to defer that setup.
The authoritative project plan remains [PLAN.md](PLAN.md).

Owner update, 2026-10-16: backup setup is deferred indefinitely. Do not resume
storage selection, backup provisioning or the credential-custody walkthrough
unless the owner reopens it. The existing production recovery acceptance gate
remains open. Next setup work is monitoring/email, followed by OAuth and private
production configuration. The next engineering experiment is worker bytecode
precompilation and its unchanged measurement gates.

## Current position

Production preparation is ready to begin; no storage provider, recovery custody,
Healthchecks account/recipients or fresh production OAuth inputs have been accepted
in this setup sequence. No production provisioning or public activation is claimed.
Use the existing VPS; no additional host purchase is assumed.

The owner has authorized native acceptance protocols on that VPS and a separate
review agent for the profiling checkpoint. Native source reviews, ownership
reconciliation and independent cleanup remain required. Public listeners, trusted
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

Read [PLAN.md](PLAN.md), this document and the current integration handoff. The next
owner-facing task is monitoring/email setup in step 2. Backup setup is indefinitely
deferred by owner decision.
First check for newer committed receipts or owner decisions; do not ask the owner
to repeat authorization already recorded here. Record each choice, scoped result
and remaining dependency without committing credentials. Commit validated
checkpoints and leave pushing/publication to the owner.
