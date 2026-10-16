# Proposed 0.6.0 integration protocol — inactive

This is a concrete implementation and verification packet, **not contract
adoption, evaluator activation or a production-default approval**. Native host
accounting source is retained separately at `d9b2f69761b5c1bee355b5db53f3e37ce8432c9f`.
The preparation branch does not modify that source, frozen benchmark/evaluator
files, locks, schema, current epochs or reference costs.

## Prepared code and compatibility

`mldsafail.benchmark_versions` implements explicit version selection, a trusted
backend registry with no cross-version fallback, full-cohort identity, and a
public projection excluding private paths/nonces/seeds. A 0.6.0 registration
requires supervisor review, auditor review, complete native faults, the unchanged
native paired gate, and contract adoption. These are operator-accepted decisions;
Python flags and schema validation do not independently establish those gates.
An installed worker/readiness receipt must supply the real backend registration.

The isolated API patch permits explicit `benchmark_version=0.6.0` submissions and
`GET /api/v1/leaderboard?benchmark_version=0.6.0` only with that registration.
Omitted versions retain the existing configured default. Submission metadata and
leaderboards use separate version/epoch/evaluator/hidden-suite/worker identities.
The CLI patch adds explicit 0.6.0 submit/clone selection, keeps its 0.5.0 default,
and uses the same Python-only `solve(public_instance)` source interface. Existing
0.4.0 and 0.5.0 behavior is covered by regression tests. A reused idempotency key
with a different version/cohort remains a 409 conflict; lost responses are
reconciled by repeating the original request/key, never by blind new submission.

These adapters are **not a complete 0.6.0 evaluation backend**. No backend is
registered by shipped configuration. In particular, do not set the existing
coordinator's version to 0.6.0: its historical fallback is not a 0.6.0 route.
Provision a separate reviewed version-aware coordinator entrypoint with the
registry before enabling the API registration. Do not deploy this preparation
branch as a compatible frozen-staging application replacement.

`research.mlwe_v060_preparation.epochs` creates private draft epochs with a fresh
32-byte nonce, version-separated held-out seed derivation, the same five tiny
challenge cells and 20 seeds per profile. Shared profile/seed clusters across eta
are preserved for the unchanged bootstrap. Drafts are never ready/sealed and
contain no reference costs. Existing epoch IDs must be checked against the
operator's complete epoch registry. No 0.5.0 epoch or cost table is converted.
The reference-table validator rejects legacy seconds/plain tables and binds
version, method, units, cohort, epoch-manifest digest, reference source and worker.
Digest fields establish compatibility/identity, not independent audit truth.

Inspect the disabled protocol without executing any worker:

```sh
python -m research.mlwe_v060_preparation --benchmark-version 0.6.0
```

## Dependency-ordered implementation after native acceptance

1. **Freeze the accounting gate.** Accept two independent reviews and the complete
   native fault suite on the retained source/image/host accounting parent. Then
   run the predeclared 30 sequential empty/CPU pairs once. Preserve failed and
   partial receipts. CV <=0.05, empty CPU median <=250,000 microseconds and empty
   wall nearest-rank p95 <=5 seconds remain unchanged. A failure creates repair
   work; it does not justify a favorable replacement measurement.
2. **Adopt the contract independently of production activation.** Bind the signed
   operator packet to source/image/gate receipt digests. Approve the proposed
   0.6.0 contract and evidence schema without changing scoring thresholds or
   retained 0.5.0 results. Production default/public exposure remain separate
   owner decisions even after this packet passes.
3. **Build separately identified artifacts.** Add a new `benchmark_v060` namespace,
   separately fingerprinted worker/participant artifacts and a new coordinator
   entrypoint. Preserve every frozen `benchmark_v050` and existing evaluator
   file. Copy/reuse only reviewed mathematical/source-validation semantics;
   never reuse timing, epoch seals, costs or ranking evidence. OCI labels bind
   version/source/method; installed wheel/worker smoke tests verify those labels.
4. **Implement the native backend before registry activation.** Extend trusted
   host registration to snapshot approved contestant source, restricted public
   fixed-profile inputs and declared case/repetition identities. The private
   supervisor never accepts arbitrary Docker arguments or participant host paths.
   Keep one warmup plus exactly three measured invocations without replacements.
   Audit every measured generation against immutable ownership/source/input/
   counter/termination/output records. Any invalid candidate makes the run
   ineligible; ordinary failures penalize the entire case at 60 seconds;
   infrastructure evidence/cleanup failures use bounded attempts/backoff and
   produce no rankable result. The registry must invoke this distinct backend;
   missing/unknown versions fail closed rather than invoke historical code.
5. **Finish fresh private epochs.** Use new protected evaluator roots, epoch IDs,
   nonces and separately identified worker/source artifacts. Run the unchanged
   tiny-profile viability/reference-family procedure under native accounting.
   Retain all failed gates; never replace failed seeds automatically. Publish
   native microsecond reference costs only after complete independent epoch
   audit and source-bound receipts. Seal the 0.6.0 manifest/reference/audit chain
   in a new schema. Bootstrap/geometry/anchored ties remain unchanged.
6. **Wire the hosted result boundary.** Add a separately versioned 0.6.0 signed
   envelope/auditor and persist only its verified public projection using existing
   MLWE score/cohort columns where sufficient. Keep raw private evidence in its
   separate namespace. Validate epoch/environment/method/source/artifact identity
   before publishing. Compute evaluator fingerprints over the entire environment
   and measurement contract, so existing DB cohort columns cannot conflate two
   hosts. A schema change, if found necessary, requires separate review and
   explicit migration handling; do not silently alter the frozen staging schema.
7. **Install isolated version-specific workers and activate explicit selection.**
   Claim only matching-version jobs; preserve admission, fencing, cancellation,
   stale leases and cleanup policy. Load the accepted cohort/epoch/worker readiness
   receipt into the registry. Rehearse API -> source snapshot -> native evaluation
   -> independent audit -> version-specific leaderboard in disposable databases
   and separate roots. Include mismatch, invalid-answer, timeout, cancel, crash,
   contamination and cleanup retries. Prove 0.5.0 jobs/results are unchanged and
   neither version appears in the other's leaderboard or reference table.
8. **Complete participant and release acceptance.** Build installation/scaffold/
   submission smoke artifacts, version-correct scoring/CPU-method documentation,
   checksums and sanitized audit packets. Review the complete source/image/epoch
   packet independently. Actual publication, production activation/default
   selection, public exposure and pilot recruitment require their owner inputs.

## Test and evidence acceptance

`tests/test_v060_preparation.py` covers disabled/version-gated dispatch, no fallback,
unchanged CLI defaults, API selection/idempotency, cohort/privacy isolation, fresh
100-case private drafts and rejection of old/cross-cohort reference tables.
Those tests use synthetic registrations and receipts, not real adoption approvals
or native costs. Run focused tests and `make check` for each source checkpoint.
The native accounting branch stays frozen during this preparatory work.

Actual full integration remains incomplete until steps 1–8 have their declared
source-bound evidence. Local adapters, schema compatibility, draft epochs and
configuration do not complete native or public-launch gates.

Execution reference admission now additionally requires a separately signed
`mldsafail.v060-reference-authority.v1` envelope. Draft cost-table validation
remains available for preparation, but complete evaluation refuses it without
an independent authority binding the exact table digest, complete native
reference audit, full primitive viability, and sealed epoch. The reference
operator's private key is separate from contestant-result signing; this code
neither provisions it nor asserts those gates passed. All currently prepared
`ready: false` reference receipts remain inadmissible for execution.

Complete evaluation runs under a fixed 1,200-second platform timer in a
separately owned native main-thread executor. Expiry interrupts blocking
measurement into durable infrastructure-failure cleanup and prohibits signing
or publishing an authoritative result; cleanup can remain fenced after the
measurement deadline. The sixty-second ordinary timeout, exactly three
measured invocations, and whole-case scoring policy remain unchanged. A thread
or an executor with an existing process timer fails closed before evaluation.
Native deadline/interruption acceptance remains required.

The private native candidate acceptance entry point is `python -m research.mlwe_v060_preparation.native_acceptance --config PRIVATE_DRIVER.json`, executed in the actual delegated operator unit after the source-bound accounting fault and 30-pair gates pass. Its generic owned-driver configuration pins the callback module SHA256 and independent callback review packet. Beside the fresh `state_root`, provide private `v060-protocol.json` with schema `mldsafail.v060-native-protocol.v1`, `prerequisites` (private accepted receipt path), `forbidden_epoch_ids`, and `postgres_artifact` containing exactly `image`, `image_archive`, and `image_archive_sha256` for a separately retained PostgreSQL image. The accepted prerequisite receipt uses `mldsafail.v060-native-prerequisites.v1`, exact `supervisor_source_sha256`, `worker_image`, `worker_context_sha256`, and `worker_source_commit`, strict true `native_faults_passed`, `native_pairs_passed`, `supervisor_review_passed`, `auditor_review_passed`, and nonempty `evidence_refs`; constructing a receipt does not supply native acceptance.

Before the accounting gates, run `python -m scripts.native_v060_worker_preparation --config PRIVATE_OWNED_DRIVER.json` in its reviewed delegated operator activation. This build-only callback retains the minimal labeled 0.6 worker context, immutable image ID and fsynced read-only Docker export; its artifact receipt requires the outer driver cleanup to pass and claims no epoch, native accounting acceptance or adoption. Use that exact image/archive for the full fault suite and thirty pairs. Preserve generation G's failed frozen-worker experiment.

After those exact-artifact gates pass, the candidate callback reuses `config.image`, recomputes its clean context identity, rejects any prerequisite source/image/context mismatch, generates a fresh 100-case tiny epoch, executes one warmup plus exactly three measured invocations per case under the unchanged 60-second ordinary limit and 1200-second complete reference ceiling, then independently re-reads all 300 generation records. It recomputes dispositions/costs and the unchanged 90% per-cell viability floor before writing a separate isolated epoch seal and signed reference authority. Draft tables remain inadmissible. A second fresh owned daemon hosts disposable loopback PostgreSQL outside the measured CPU parent; the actual HTTP CLI, API admission, serialized coordinator, signed full evaluation, leaderboard separation, and preserved 0.5 default are exercised there. Both daemon contexts stay inside the same operator activation and independently retire through positive whole-domain barriers. Failures retain private diagnostics and never provide replacement scores.

`CandidateRehearsalAuthority` is distinct from contract adoption. It binds the accepted prerequisite packet, fresh epoch, retained source, worker image, and cohort; it requires explicit `private_rehearsal=True` in backend/coordinator/registration, and the API accepts its registry only with `TESTING=True` and `V060_PRIVATE_CANDIDATE_REHEARSAL=True`. It cannot select a default, even with a default-approval flag. This executable rehearsal cannot activate any deployed or production registry. Actual contract adoption and default/public activation remain separate decisions.
