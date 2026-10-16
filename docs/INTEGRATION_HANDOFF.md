# Canonical competition integration — 2026-10-13

`engineering/integration` starts at audited public-launch source
`6f60782cb7ddc7accc7cb325d1f0c8258082864b`. It incorporates main's package-build
fix, startup socket-retirement safeguards, bounded lifecycle diagnostics,
historical candidate-install tooling and precise cooperative clock wording.
Newer public-launch recovery, publication and candidate-runtime implementations
remain the basis. No push, merge into main, public activation or publication occurred.

## Production preparation update — 2026-10-16

The owner is ready to begin guided production setup, superseding the earlier
setup deferral. Follow [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md), beginning with
off-host storage and owner recovery-credential custody. Native acceptance on the
existing VPS is authorized; measurement and operational gates remain open.
Production activation, publication and recruitment remain separate decisions.

## Native continuation — 2026-10-15

SSH access resumed. Source `0215c9c539825c1492a9129f93c55923bd42d51e`
passed the [native startup matrix](acceptance/integration/native-startup-20261015.json),
all 13 accounting faults and the single predeclared six-invocation
[measurement investigation](acceptance/integration/measurement-investigation-20261015.json).
The original synthetic-interruption generation was terminally reconciled using
its unchanged authority; controller A's failed preflight and controller B's
successful cleanup are retained. Independent current checks covered 20 historical
driver generations and the new startup/fault/diagnostic domains and sockets.
Failed startup A/B attempts remain negative evidence. The native systemd job
interface correction was reviewed and tested before the successful fresh C run.

The diagnostic empty CPU median was 450,899 microseconds. Its three pairs are
observational only; G/L failures, the 30-pair requirement and all thresholds
remain unchanged. No performance correction, measurement adoption, default
activation, production change or publication occurred. The original integration
handoff below remains dated historical context; the updated ledger and dated
receipts govern current continuation status.

### Functional dispositions and final resource check

Frozen source `451943ae3d7cc511ed077ad79e27db256da75617` passed
[actual admitted-daemon retirement rejection and RPC loss/repair](acceptance/integration/native-rpc-20261015.json)
and [local synthetic encrypted recovery](acceptance/integration/native-encrypted-20261015.json).
The original RPC A run observed a real 201 response but failed its exception-class
handling; its failure and cleanup remain retained. Reviewed B corrected the
harness and observed actual 201/create and 204/start losses with exact daemon
repair and repeated cleanup. Encrypted recovery used the retained amd64 binaries,
a cleared inherited environment, six real fault/restore stages and a separate
fresh cleanup controller. It does not accept a full protected application set,
real off-host storage or owner key custody.

The [final disposition](acceptance/integration/native-resume-final-20261015.json)
records current absence for 41 driver generations and 28 encrypted fixture clients,
with both encrypted controller domains absent and the four protected container
identities unchanged. Evidence and daemon stores remain retained; no native
operation remains running. `make check` passed 968 tests with 13 skips and all eight
contract checks; focused ownership/RPC/encrypted/load checks also passed.

**Combined native acceptance remains incomplete.** The
[functional prerequisite packet](acceptance/integration/functional-prerequisites-20261015.json)
separates these remaining outcomes:

- Historical b042/c67/570 candidate installation: exact original archive/wheel
  not located in bounded approved retained locations; do not regenerate substitutes.
- Supported successor installation: wheel retained, complete locked native offline
  dependency inventory still unverified. Existing operator environments do not
  establish fresh installed import/dependency isolation.
- Rollback rehearsal: [independent source audit](acceptance/integration/baseline-independent-audit.json)
  withheld execution. The source repair now halts creator cancellation and all
  downstream Docker cleanup unless whole-daemon shutdown is positively proven and
  durably recorded; post-switch checks re-audit the sealed epoch inventory and
  accepted result/evidence. Focused tests and `make check` are recorded with the
  source checkpoint. Independent supervisor/auditor/protocol/callback reviews have
  not yet matched that checkpoint. Exact retained compose, backup and transitive
  recovery helpers were not found in bounded local inspection; no substitute was
  used, so native execution remains withheld.
- Full protected-set restoration, admitted-job interrupted/repeated activation,
  application failure matrix and two 300-second load phases: deferred with the
  fresh audited application fixture and source gate. The new disposable load
  adapter has source/tests only; the historical staging orchestrator was not invoked.
- Scientific reproduction: original reviewed primitive-study worker and exact
  Python registry-base archive/provenance not found in the declared inventory;
  inventoried MLWE workers cannot substitute for them.

Before admitting rollback, obtain independent reviews of the frozen source and
exact dependency/configuration inventory, and recover/verify the exact historical
compose/backup/recovery helper bytes. Native execution remains withheld until those
gates pass. Then construct fresh reviewed application/recovery/load protocols. No
failed epoch may be replaced automatically. Measurement correction remains a
separate reviewed source checkpoint followed by the complete fault suite and at
least 30 sequential pairs.

## Preservation and branch disposition

[Refs and dispositions](acceptance/integration/refs.json) retain every original
branch/worktree. All audited tips matched the prior inventory before integration.
The [preservation manifest](acceptance/integration/preservation.json) binds a
verified standalone full-history bundle, original audit inventory and metadata-only
ignored-material/worktree inventory. Durable protected copies reside under ignored
`results/integration-preservation/20261013/`; initial copies remain in `/private/tmp`.
The [cleanup manifest](acceptance/integration/cleanup.json) is **retain everything**. No source worktree, failed/partial
evidence, rollback release or historical row was deleted. Local temporary build
and installation evidence is retained and must also survive any later cleanup.

## Ten checkpoint dispositions

| Checkpoint | Disposition and practical limit |
| --- | --- |
| 1. Inventory/preservation | Standalone bundle verified; audited refs unchanged; protected metadata inventory and cleanup manifest retained |
| 2. Package-build fix | Imported `4602f45`; local clean worker build, wheel inventory, installed import isolation and starter identity checked; architecture is local ARM64 |
| 3. Startup safeguards | Imported `881d897`; focused refused/live/replaced socket and interrupted publication tests pass; current VPS ownership/native proof deferred |
| 4. Measurement failures | Imported `8d80137`; G and L remain failed; three-pair diagnostic protocol ready, execution blocked by VPS access/ownership |
| 5. Participant installation | Imported `d8a3ec7`; exact retained historical candidate protocol/fixtures preserved; VPS native installation deferred; successor wheel locally tested, unpublished |
| 6. Evidence/docs | Precise cooperative scope imported selectively; dated reviews preserved; integration ledger validates with explicit historical scope and traceability limitation |
| 7. Retirement | Supported Python-only MLWE clone/run/submission; ledger-backed public development; new hosted 0.4.0 rejection; archival execution and all historical data/contracts retained |
| 8. Native combined acceptance | Deferred: documented SSH endpoint timed out twice; no remote operation acknowledged and current resources/ownership could not be inspected |
| 9. Adoption decision | Updated [packet](MEASUREMENT_ADOPTION_PACKET.md) includes G/L failures and diagnostic proposal; 0.6.0 routing/default remain inactive |
| 10. Production/recovery/email/pilot | IP HTTPS, inactive Certbot renewal/reload, Healthchecks adapter, custody and pilot packets prepared; owner inputs/activation and native rehearsal remain deferred |

The [integration ledger](acceptance/integration/launch-ledger.json) preserves
historical exact-source passes and failures. They do not establish combined-source
acceptance. The absent numbered historical checklist is a traceability limitation;
actual declared integration requirements remain the engineering criteria.

## Exact artifact and verification receipts

[Verification](acceptance/integration/verification.json) records source, artifact,
environment, commands, log hashes and limitations. Final code artifacts are built from
`26c5f2f4bc771b319ffccc2cdcb1c735eaab4176`. The wheel is byte-identical to the
tested `0375e1c5499fb173b80847fb7081fec5217bf88a` artifact; the corrected install
probe is at `e1061b2bd95fe165569103765422e773225909ee`. Frozen benchmark sources,
locks, safety profiles and score meaning were not changed. Operator/client
integration is separate from the inactive measurement contract.

Retain the first failed install probe (incorrect Python-to-JSON fixture shape),
the first source distribution containing a temporary source tar, the rejected
image with an incorrect full source label, and later corrected artifacts. None
is silently substituted into successful evidence. Local builds/installations
do not pass measurement, clean-build scientific reproduction or amd64 acceptance.

## Native continuation protocol

The existing VPS is `178.128.17.58`, documented in `OPERATIONS.md`; the SSH key
is the documented local identity. Restore reachable access without assuming old
cleanup reports prove absence. Inspect exact generation ownership journals,
process birth identities, short socket roots, daemon/worker/operator parents and
unfinished operations. Reconcile using the original recorded authority. An
unresolved fence blocks dependent provisioning; do not delete by path or name.

Freeze the complete current source and aggregate helper/callback digests before
each operation. Serialize all tests against evaluation, maintenance and load.
Use separate disposable database, evaluator root, daemon domains, fresh synthetic
credentials and protected evidence paths. No live service changes or existing
private staging evidence access are authorized by this packet.

After cleanup proof, execute the imported startup-negative tests, predeclared
three-pair diagnostic and historical candidate-install protocol for their named
artifacts. Then run scoped recovery RPC lost acknowledgements, protected-set/local
encrypted restoration, interrupted/repeated activation, schema/data and epoch
audits, migration-free rollback/forward repair, reproduction, idle/evaluation
load and the cancellation/invalid/timeout/crash/retry/exhaustion/stale-lease matrix.
Existing checked-in native protocols specify their exact authority and callbacks.
Record success, failure, partial execution and independent final cleanup separately.
Infrastructure failure, incomplete accounting or surviving resources yields no score.

## Recovery custody, release and incident preparation

Use the existing encrypted recovery assembly/upload/restore/audit workflow from
`OPERATIONS.md`. Production storage and repository credentials must be separate
from staging. The owner supplies scoped off-host storage and independently retains
the recovery password plus repository/configuration identifiers off host. A host-only
credential copy cannot satisfy disaster recovery. Keep signing/authentication
inputs and protected manifests out of participant/public artifacts. Accept only
after independent encrypted download/restore, database/schema/evidence/epoch audit,
retention/freshness checks and disposable cleanup; backup notification follows all
of these. Neither configured storage nor a local synthetic restore passes this gate.

The release remains unpublished. Retain source bundle, wheel/sdist hashes, exact
application/worker images, locks, compatible rollback artifacts, migration schema
identity, evaluator/epoch audit and deployment configuration hashes. Application
rollback switches only web/coordinator with the application-switch overlay,
never migrates or restores the live database, and preserves worker/epoch/result
identity. If a receipt is incomplete, stop dependent rollout and preserve it.

Incident handling: freeze admissions/evaluations through the reviewed maintenance
path, retain journals and protected evidence, reconcile exact ownership, restore
service using compatible retained application images, verify readiness/auth/cohort
and data identity, then forward-repair. Never manufacture a score to clear a queue
or erase an infrastructure failure. Healthchecks failure/recovery delivery does
not authorize service mutations. Public activation still requires owner review.

## Three-participant external pilot protocol

Recruitment remains deferred. After applicable launch gates and owner authorization,
invite three consenting participants; freeze release/checksums, supported interface,
cohort and evaluation protocol first. Each installs in a fresh environment, clones
the approved starter, records a public baseline with required metadata, makes one
ordinary algorithm change and submits a public full commit. Track installation,
documentation friction, baseline correctness, independent submission audit,
version/cohort identity, cancellation/status behavior and retained failure evidence.
Keep private evaluator inputs unavailable and never tune against hidden feedback.

Use a predeclared small sequential schedule on the same idle host; report outcomes
for all three, including non-completion. Collect participant consent and feedback
without publishing credentials or private evidence. The pilot establishes usability
and operational observations; it does not adopt a measurement contract, claim
production cryptographic hardness or relax any correctness/accounting gate.

## Remaining owner inputs

- Identify exact original candidate/reproduction artifact locations and a complete verified native offline dependency wheelhouse; see the dated prerequisite packet. SSH was restored and ownership reconciled on 2026-10-15.
- Review a completed measurement packet later; contract adoption and default
  activation are separate decisions and remain deferred after G/L failures.
- Supply fresh production GitHub OAuth inputs for the selected IP callback.
- Supply scoped off-host storage and independently retain recovery credentials.
- Create Healthchecks checks, verify email recipients and authorize real delivery
  and missed-heartbeat tests; see [setup](HEALTHCHECKS.md).
- Review native receipts and exact release/configuration before public listeners,
  trusted certificate issuance, production activation or publication.
- Authorize recruitment only after applicable gates; no additional VPS is assumed.
