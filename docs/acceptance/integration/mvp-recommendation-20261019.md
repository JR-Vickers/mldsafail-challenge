# MVP owner decision packet — 2026-10-19

Recommend preparing a **small MLWE 0.5.0 research preview**, using candidate
`1c9ca9eff3a1133aa8b508a35f6b174a587a4f01`, compatible application rollback
`26c5f2f4bc771b319ffccc2cdcb1c735eaab4176` and frozen amd64 worker
`sha256:6aaf71aa16e36631dec607f0726fb1e8d6f94954ce55a15a74ba4989777b5cfe`.
This set has useful exact-artifact scientific/application evidence, but is **not
ready for activation or publication**. Prefer reuse after current remote identity
checks. No rebuild is indicated for application runtime changes; complete local
archives are missing for most images. Do not replace missing artifacts with the
running private installation or rebuild without recording that change of identity.

The [inventory](mvp-artifact-inventory-20261019.md) contains full image/checksum
identities, local verification and evidence limits. Reuse the integration-tested
0.5.1 wheel (`ed002b7b…`), subject to final release review; reconcile its conflicting
publication checksum. The retained sdist contains diagnostic tooling and requires
a separate minimal source-package preparation. The distribution version does not
change the frozen 0.5.0 benchmark. No 0.6.0 adoption is recommended by this packet.

## Decisions for the owner

| Decision | Recommendation and consequence |
| --- | --- |
| Public scoring scope | Explicitly approve a cooperative-timing 0.5.0 research preview, with honest score limitations. In-container clock-scoped CPU is not tamper-resistant whole-worker accounting. Existing stricter public scoring gates remain open unless an approved preview scope explicitly resolves them. |
| Known operational risk | Carry forward the owner's acceptance of C's authenticated-read failures; do not turn C into a passing rehearsal. All 14 failures affected 60 scheduled authenticated reads: 76.67% success on that loaded route, 99.10% overall. Pacing and nominal duration do not establish production error rates. Diagnostics remain abandoned. |
| Monitoring | Choose a basic HTTPS check with verified failure/recovery signal, or explicitly accept manual availability checks with a named operator and cadence. Lease/worker monitor reliability remains unverified; the permanent check was paused. Historical unplanned DOWN delivery does not prove planned recovery delivery. |
| Data-loss/recovery risk | Keep backups deferred as directed. Explicitly decide whether the preview may launch without off-host backup or independent recovery custody. Application rollback cannot recover a lost database, private epoch or evidence. |
| Execution/publication scope | Approve exact later operations separately: any production epoch, public listeners/CA issuance, activation, publication and small-cohort invitations. This packet supplies none of those approvals. |

No authentication, privacy, sandbox, correctness or scoring validation is waived.
The retained failed/incomplete outcomes, diagnostic budget and original fixture
expiry remain unchanged. No further load investigation is proposed.

## Remaining engineering work, in dependency order

Each row is a concrete gap, not a request to repeat the full rehearsal.

| Task / reason | Required environment or authority | Completion evidence |
| --- | --- | --- |
| Reverify the selected candidate/rollback, worker, database and proxy artifacts against inventory hashes; recover original worker build/source-label provenance. Historical paths and partial downloads cannot prove present availability. | Later scoped read-only VPS inventory, private release/retention records; no evaluation needed. | Current exact archive checksums, reachable OCI descriptors/blobs, labels, platform and full source identity; explicit missing/mismatch disposition. If anything is absent, return a concrete replacement proposal rather than silently substituting. |
| Prepare the participant publication set: selected tested wheel plus matching checksum, minimal reviewed source and starter/quickstart. Existing checksum points to another wheel; retained sdist includes diagnostics. | Local release-packaging work, outside this inventory step; builds only for this identified packaging gap. | Exact hashes/source revision, archive allowlist and sensitive-data review, clean installation and starter checks for the final artifacts; preserve original receipts and failures. |
| Bind a production configuration to the exact selected images and authorized production cohort. Draft OAuth/secrets records are not a complete deployment configuration. | Private VPS configuration review; separately authorized fresh production epoch and audit if approved. | Fresh database/session secrets, supplied OAuth inputs validated privately, independent database/volumes/evaluator paths, benchmark 0.5.0, worker class/fingerprint/suite/epoch binding, quotas, exact image IDs and source-bound preflight. No placeholders, staging/C reuse or diagnostic fixture launch data. |
| Verify trusted HTTPS, renewal/reload, real GitHub login/callback, secure sessions/CSRF and token creation/revocation/expiry. Rehearsal synthetic authentication does not cover them. | Selected deployment with explicit public listener/CA and OAuth activation authority. | TLS chain/hostname and renewal/reload receipt, actual callback/login/session/token checks with credentials redacted. See [production setup](../../PRODUCTION_SETUP.md) and [IP TLS](../../IP_PRODUCTION.md). |
| Complete one scoped participant journey on the final artifacts/cohort: install, starter, immutable tiny solver submission with idempotency key, status, independently audited result, leaderboard cohort and cancellation. | Clean participant environment and selected production deployment; authorized scientific operation and isolated private evidence. | Artifact/install identities and end-to-end receipt, audit/cohort checks, cancellation disposition; preserve failures. This is one functional check, not a fresh load campaign or full rehearsal. |
| Prepare minimum operations: chosen availability signal/manual procedure, incident contact, queue pause and exact application rollback/forward instructions; refresh disk/RAM/isolation checks. | Owner monitoring choice plus selected host configuration; notification tests only under later explicit authority. | Verified chosen signal/recovery or recorded manual cadence/responsibility, source/image-bound switch commands and resource receipt. Record deferred backups and unreliable lease monitoring explicitly. |
| Assemble final exact activation/publication/small-rollout commands around the verified set. Resolve any artifact/configuration gaps before asking for execution approval. | Local packet preparation after preceding evidence; separate owner decisions above. | Sanitized final packet with exact identities, required environment, approved preview score meaning, remaining risks, rollback/stop steps and distinct approvals. Owner handles publication/push. |

Production requirements are enumerated in
[the environment template](../../../deploy/production.env.example),
[Compose](../../../compose.production.yaml) and
[preflight](../../../deploy/production_preflight.py). Private draft configuration
and supplied OAuth inputs are recorded on the VPS but currently unverified;
a complete launch-bound configuration and production epoch are **missing**.
This local inventory intentionally did not read secret values or invent their
checksums. Local production templates and scientific locks are unchanged from
the candidate. The template's registry-digest placeholders must be reconciled with
retained local image IDs by the actual preflight; do not invent registry digests.

## Boundaries and verification

This recommendation introduces no API, schema, behavior, scoring or safety change.
It leaves cleanup, transfers, builds, evaluation, epoch creation, remote checks,
HTTPS/OAuth activation, notifications, publication and recruitment for later scope.
The running installation and its own rollback remain protected. Scientific data,
unresolved-failure evidence and retention exceptions remain governed by
[retention policy](../../RETENTION_POLICY.md).

Local verification: retained source-manifest members and participant artifact hashes
match; candidate coordinator OCI archive verifies; four compressed image transfers
fail EOF checks and are explicitly excluded. Source/runtime comparisons support
reuse, while main's operator changes need operation-specific review. Documentation
links passed (41 local references); `git diff --check` passed. `make check` passed
**1,175 tests, 15 skipped**, plus **eight MLWE contract checks**. The run emitted
12 warnings; environment-dependent skipped checks establish no new native acceptance.
