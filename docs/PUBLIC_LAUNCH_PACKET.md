# Public launch preparation and owner decision packet

Owner update, 2026-10-19: C diagnostics are abandoned. See the current
[MVP preparation review](MVP_LAUNCH_PREPARATION.md) for the proposed narrower
release scope and open owner decisions. This historical packet is not an MVP
approval, and its scientific/security gates are not silently waived.


Updated 2026-10-13; historical 2026-10-04 scope preserved in source history. This packet authorizes no publication, public network exposure,
production activation, spending, account provisioning or recruitment. Native
acceptance and the canonical launch ledger determine readiness. Historical reports
retain their dated outcomes; they do not establish current service state.

## Decisions and missing inputs

| Decision/input | Supplier | Concrete requested action | Work that waits |
| --- | --- | --- | --- |
| Measurement contract adoption | Owner, after supervisor/auditor review | Approve or reject the separately versioned 0.6.0 contract with unchanged declared gates | Production cohort/default, final participant artifacts and score text |
| Production account/domain/OAuth | Owner | Use the existing VPS and origin `https://178.128.17.58`; register callback `https://178.128.17.58/auth/callback`; supply fresh scoped OAuth inputs privately | Real OAuth, TLS and DNS acceptance |
| Recovery storage and independent custody | Owner | Supply separate scoped production/staging repository configurations; retain recovery passwords independently off host | Actual off-host restore, retention/freshness and timer activation |
| Alert destination | Owner | Create Healthchecks service/recovery checks, verify recipient email, supply private ping endpoints and authorize acceptance delivery | External delivery/recovery acceptance and monitoring activation |
| Public activation/publication | Owner | Review exact commit/image/epoch identities and native evidence; approve activation and distribution channels explicitly | Public ports, published release/downloads |
| Pilot recruitment | Owner | Approve invitations and choose consenting participants | External observations and pilot results |

Missing credentials do not block disposable engineering or configuration parsing.
No secret value belongs in this packet, the ledger, a shell transcript or public
artifact. Use protected local operator records for private resource locations.

## Configuration and migration discipline

`deploy/production.env.example` lists every production Compose input. Copy it
outside the checkout, restrict it to 0600, and replace placeholders. Use fresh
secrets, a separately generated/audited epoch and costs, separate PostgreSQL/Caddy
volumes, and a production evaluator root disjoint from staging. Do not convert
0.5.0 evidence, change its locks, or reuse its epoch/reference costs for 0.6.0.
The checked-in production Compose remains a **0.5.0 preparation template**;
its presence is not approval of cooperative timing for public participants.
A future reviewed version-selection implementation must supply the adopted
production template before activation.

Run the read-only preflight without exposing environment contents:

```sh
python -m deploy.production_preflight --production-env "$PRODUCTION_ENV_FILE" \
  --staging-env "$STAGING_ENV_FILE"
```

The files use literal `KEY=value` entries, no shell interpolation, quoting or
surrounding value whitespace. Generate the database password using URL-unreserved
ASCII (`A-Z`, `a-z`, digits, `.`, `_`, `~`, `-`) because Compose embeds it in the
connection URL.
This gate checks placeholders, immutable image digests, selected staging reuse,
rootless socket shape and path isolation. It does not prove credential scope,
Trusted IP certificate, image provenance, epoch audit, host resources or approval. Keep
`docker compose config` output private because it contains interpolated secrets.

Fresh disposable/production setup uses the explicit `migrate` service once,
followed by schema verification and reviewed application startup. Recreating an
existing application must not trigger migrations. For application-only switches:

```sh
docker compose --env-file "$PRODUCTION_ENV_FILE" -f compose.production.yaml \
  -f deploy/compose.application-switch.yaml up -d --no-deps web coordinator
```

This overlay resets application dependencies. It does not restore prior service
states: stop/start exact existing container IDs directly for that purpose.
Never use `down -v`, restore the live database, or include database/proxy/worker
services in an application rollback. Load only retained reviewed application
images; changing tags without verifying IDs is insufficient.

## Disposable production rehearsal protocol

Record the source commit/tree, web/coordinator/worker digest identities, locks,
Compose hashes, private epoch ID, kernel/Docker identities, and test protocol
before execution. Use an isolated rootless environment, unique Compose project,
new evaluator root, new synthetic credentials and fresh volumes. Bind rehearsal
proxy to loopback only through a disposable override; public ports require the
owner gate. Do not use staging configuration, database, evidence or costs.

1. Start a fresh database, explicitly migrate, verify schema revision and prove
   all volumes/paths are separate from staging. Save protected baseline inventory.
2. Verify in-container readiness, authentication failures, secure session cookie,
   CSRF protection, OAuth success/revocation, expired token UI, trusted proxy/TLS
   behavior, security headers and rejection of operational paths through proxy.
   Real OAuth/TLS needs owner inputs; a synthetic session cannot pass that gate.
3. Submit one immutable approved synthetic solver with a recorded idempotency key.
   Check acquisition/source identity, serialized evaluation, independent audit,
   result/API identity, privacy and version/epoch leaderboard cohort. Lost submit
   responses must be reconciled by that key, without blind resubmission.
4. Take a quiescent protected backup, restore only to a new disposable database,
   and independently audit restored references, epoch and evidence. Record
   checksums, cleanup and timing. This is distinct from encrypted off-host restore.
5. Drain jobs, stop application writes, record DB/schema/result/leaderboard/epoch/
   worker identities, and switch only web/coordinator to exact retained prior
   application release. Assert no migrate container invocation, all identities
   unchanged, health/authentication correct, then switch forward and recheck.
6. Reconcile owned containers, journals and attempts; retain failures and protected
   evidence. Destroy only disposable resources after ownership verification.

Local parsing tests pass separately from these native gates. A successful staging
rollback is not automatically a production rehearsal; new cohort and production
configuration need their own evidence. Stop dependent acceptance after a failed
switch until exact rollback, cleanup and corrected release verification pass.

## Participant distribution and reproducibility

Freeze a reviewed clean commit before building artifacts. Record source/tree,
package version, benchmark version, worker architecture/image, installation
platform, wheel hash and source/starter hashes. Keep each release distinct.
Use `scripts/hosted_release.py` and `scripts/retain_release.py` only for their
supported frozen 0.5.0 format; they must gain separate reviewed 0.6.0 support
before recording that version. Retain checksums and artifacts locally, without
publishing them.

For the current participant 0.5.1 wheel, install into a new directory with
`sh scripts/install.sh RELEASE.whl VERIFIED_SHA256 NEW_DIRECTORY`. Verify
`mldsafail --help`, default `mldsafail clone NEW_WORKSPACE`, byte equality of the
installed MLWE starter with the approved source, `mldsafail run --help` metadata,
installed dependency/interpreter bindings and public fixture verification. The
successor `run`/`make bench` execute public MLWE development. The historical
0.5.1 smoke is retained under `scripts/archive/` for its exact older artifacts;
its clone/small-profile protocol must never be applied to the successor.
See [MLWE_LOCAL.md](MLWE_LOCAL.md) and [MLWE_PILOT.md](MLWE_PILOT.md).

Hosted 0.5.0 submission selects a Python-source directory exporting
`solve(public_instance)`, an immutable public GitHub commit, explicit server and
matching epoch. Use an idempotency key, preserve it until resolved, and use
status/logs/cancel for diagnosis. Approved 0.6.0 participant docs must describe
host accounting, independently audited evidence and distinct leaderboard cohorts;
never relabel existing 0.5.0 scores or claim production ML-DSA hardness.

Prepare downloadable source/wheel/checksums, frozen tiny public fixtures and
normalized public reproduction summaries. Exclude nonce/seeds/witnesses/raw
candidates, database dumps, credentials, raw host evidence and infrastructure
paths. Independently review the exact public archive before publication. Public
reproduction verifies identities and normalized correctness; timing equality
across architectures/hosts is not promised.

## External pilot protocol and observation form

Do not recruit until required launch gates, approved production/public activation,
and owner recruitment approval pass. Participant observations collected before
these decisions do not establish the public launch pilot gate.
Predeclare a small cohort of three consenting participants, at least one clean
installation without repository context, using the exact candidate artifacts and
one approved benchmark/epoch. Owner may revise cohort before observations begin;
never change success criteria after seeing results.

Each participant should install, identify benchmark/version, clone the starter,
run public development validation, submit their immutable source, follow status,
inspect their correctly scoped leaderboard entry, and cancel a deliberately
pending submission. No solver optimization or private-score target is required.
Use only tiny generated instances and approved source. Record first-attempt
completion, elapsed active time, documentation ambiguity, observed API errors,
retry/idempotency reconciliation, expected versus observed score interpretation,
and privacy concerns. Keep consent/contact information out of committed records.

Copy this form per pseudonymous participant:

| Field | Observation |
| --- | --- |
| Participant alias / consent confirmed | pending |
| Artifact commit/wheel SHA-256 / platform | pending |
| Benchmark version / approved epoch alias | pending |
| Clean install and starter validation | pending |
| Submission key alias / terminal status / independent audit | pending |
| Leaderboard cohort and score understood | pending |
| Cancellation and retry behavior | pending |
| Active minutes / first-attempt completion | pending |
| Errors, confusing instructions, privacy finding | pending |
| Evidence reference / observer / date | pending |

Pilot success requires all three to complete installation, public validation,
submission-to-audited-result and correct cohort interpretation without operator
code edits; zero lost/duplicate accepted submissions, zero private evidence leaks,
and cancellation within the existing declared bound. Document usability failures
and fix/retest affected steps with fresh evidence. A failed observation remains
part of the packet. Participant-dependent results stay pending until obtained.

## Go/no-go record and publication sequence

The final owner packet must include canonical ledger validation, exact retained
source/image/artifact identities, supervisor/auditor signoffs, native accounting
and stability gates, seven staging scenarios, live rollback/forward, recovery/
monitoring/load results, disposable production rehearsal, public archive review,
incident runbooks, current service state and outstanding blockers. No open gate
may be inferred passed from local tests or owner silence.

Record separately: contract decision, production default, production activation,
release publication and recruitment. Owner signs each applicable decision with
scope/date/identities. On approval, operator verifies a fresh protected backup,
idle queue, rollback identities and maintenance journal; performs the approved
production activation; validates HTTPS/OAuth/health/submission; then owner publishes
checksummed artifacts and approved docs. Pause recruitment on failed health,
accounting, privacy, recovery or cancellation gates. Incident response preserves
private evidence, drains/pauses evaluation, rolls applications back without
migrations, and records a reviewed forward repair before reactivation.


## Owner-review recruitment draft (never sent by this task)

After activation and recruitment approval, the owner may adapt this invitation:

> We are inviting three consenting participants to try a small synthetic MLWE
> optimization benchmark. The task is to install the reviewed package, validate
> the starter locally, submit an immutable solver revision, inspect its audited
> result and test cancellation. This does not involve real keys or signatures.
> Participation is voluntary; please confirm consent before we record usability
> observations. We will identify observations with an alias and exclude contact
> details and private evidence from public reports. Approved download/server links
> and the exact benchmark/epoch will be supplied only after launch approval.

Record owner review, approved links/artifact hashes and recruitment authorization
before delivery. The agent sends no invitations or external messages.


## Integration update

The integration branch retains newer recovery/publication/runtime implementations
and the dated source reviews. Startup-retirement safeguards and the three-pair
diagnostic are imported; combined local tests pass. Native acceptance for this
combined source is deferred after two SSH timeouts; no current resource absence
or staging health is inferred. Historical G and L measurement failures remain
failed. See [the integration handoff](INTEGRATION_HANDOFF.md),
[IP HTTPS configuration](IP_PRODUCTION.md) and [Healthchecks setup](HEALTHCHECKS.md).
The absent numbered historical checklist is a traceability limitation; the
integration ledger does not invent missing requirements or block independent work
on their mapping. Production/default adoption, off-host custody, email delivery,
public activation, publication and three-participant recruitment remain deferred.


2026-10-20 maintenance update: [v8 prerequisites](acceptance/integration/maintenance-prerequisites-v8-20261020.md) and [capacity protocol](MAINTENANCE_CAPACITY_PROTOCOL.md) add local control engineering and protocol preparation. Item 4 remains blocked; the proposal is nontransferable and cannot execute. Epoch mutations require a live reviewed maintenance fence; no production adapter or maintenance window is approved. Historical results remain unchanged.
