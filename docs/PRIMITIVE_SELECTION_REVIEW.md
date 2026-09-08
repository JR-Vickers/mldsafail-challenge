# Agent Lattice-Cryptography Review Packet

## Review status

- Review agent/model and session identifier: Codex / GPT-6 family description; exact runtime build not exposed; `/root/primitive_review`
- Reviewed commits: initial `c60e1d069b97006aa22793921e9a2c5a64100edf`, repaired `9ad9423f7325b73383d250eb48353c3bd816da40`; source/configuration digests below
- Review scope: mathematical definitions, code, adversarial synthetic probes, raw development evidence; limitations below
- Review dates: 2026-09-07 and 2026-09-08
- Current decision: repaired development accepted for freeze conditional on two-clean-build reproduction; final selection approval withheld pending held-out evidence
- Fresh validation nonce: pending; do not create one before the harness and
  solver configuration are frozen for review

An agent conducts this specialist review and may approve the next primitive
after completing the review and held-out validation. External human specialist
approval is optional. Label the outcome as an agent review, not human expert
certification. Passing repository tests alone does not constitute approval.

## Review procedure and required evidence

1. Begin a dedicated review session and record the agent/model and exact revision.
   Independently inspect the materials below rather than adopting the existing
   recommendation as a conclusion.
2. Answer every blocking review question with code references, mathematical
   reasoning, relevant primary-source citations, and reproducible checks where
   applicable. Actively probe shortcuts, especially direct modular solving of
   the planted MSIS construction, using only repository-generated synthetic
   instances within the existing safety boundary.
3. Log findings, severity, evidence, and proposed resolutions. Check fixes and
   rerun affected development experiments before closing blocking findings.
   Reconcile the narrative recommendation with the raw-data-generated report.
4. Once blocking findings are resolved, record the frozen implementation and
   configuration revision/digests. Only then generate a fresh random nonce
   (for example, 32 random bytes encoded as hex). Record its creation time and
   freeze reference; do not choose it by inspecting derived seeds or outcomes.
5. Rebuild the container and run the validation cohort with 20 seeds per profile
   using that nonce. Preserve all results, audit the records, regenerate the
   report, and evaluate the held-out evidence against the existing decision rule.
6. Record a dated approval or withholding decision with supporting evidence and
   limitations. If implementation/configuration changes are needed after
   validation, preserve the failed evidence and use a new freeze and fresh nonce.

This packet assigns the review; its pending fields do not represent completed
review or authorization to claim validation has already occurred.

## Materials

- Definitions and canonical contracts: `research/primitive_selection/models.py`
  and `research/primitive_selection/schemas/`
- Ring arithmetic and generators: `ring.py` and `generator.py`
- MLWE/MSIS embeddings and BKZ provenance: `embedding.py`
- Independent verification: `verify.py`
- fpylll adapters and strategy parameters: `solvers.py`
- Process isolation, limits, measurements, and seed derivation: `worker.py` and
  `runner.py`
- Raw development results: `results/development.jsonl`
- Reproducible generated analysis: `results/REPORT.md`
- Proposed decision and limitations: `docs/PRIMITIVE_SELECTION.md`

The container development data identify their exact harness revision as
`b33f229338695fcccfba415245058deb772a5a8f` and include a source digest in every
record. Later report/documentation commits do not rewrite that provenance.

## Blocking review questions

1. Are the coefficient embeddings consistent with multiplication in
   `Z_q[x]/(x^n+1)` and with the stated MLWE/MSIS relations?
2. Does the MSIS generator's primitive planted relation, whose last polynomial
   is one, create a trivial shortcut or bias that should disqualify the track?
3. Are the independent verifier checks sufficient, especially exact
   unimodularity and basis provenance?
4. Do LLL, fixed BKZ, progressive BKZ, CVP, and restart strategies represent
   materially different enough families for the decision rule?
5. Are the dimension/difficulty caps scientifically defensible given the
   recorded pre-freeze 60-second failures?
6. Are root-Hermite factor, verified relation norms, CPU time, and peak RSS
   interpreted correctly without collapsing the tracks into one score?
7. Is the provisional fallback rubric defensible, and should any track be
   disqualified before held-out validation?

## Finding log

| ID | Severity | Finding | Resolution commit | Experiments rerun | Reviewer disposition |
|---|---|---|---|---|---|
| F01 | blocking | Public seed reconstructs MLWE/MSIS answers | 9ad9423 | complete v2 development | repair accepted; held-out boundary check pending |
| F02 | blocking | Planted MSIS reduces to square modular solve | 9ad9423 exclusion | adversarial and v2 direct baselines | planted distribution disqualified |
| F03 | blocking | MSIS success lacks norm-bound correctness gate | 9ad9423 | complete v2 development | repair accepted |
| F04 | blocking | Audit trusts incomplete/unverified cohorts | 9ad9423 | strict full-cohort audit | repair accepted; held-out audit pending |
| F05 | blocking | Useful difficulty and solver coverage unestablished | 9ad9423 | 960-case v2 development | development gates pass; validation pending |
| F06 | blocking | Kernel-share denominator omits runtime | 9ad9423 | historical and v2 recomputation | correction accepted; BKZ gates failed |
| F07 | high | BKZ first-vector objective has trivial structural floor | 9ad9423 exclusion | historical and v2 comparator evidence | current objective disqualified |
| F08 | high | Resource/failure categories and intervals ambiguous | 9ad9423 | tests and complete v2 audit | repair accepted; clean-build reproduction pending |
| F09 | medium | Stale summary and eligibility-free fallback scores | 9ad9423 | report/conclusion reproduction | development narrative accepted |
| F10 | medium | Standard-parameter/distribution claims need scope | 9ad9423 | primary specification and 2026 errata | structural-analogue scope accepted |

A blocking finding is resolved only after the reviewer accepts the change and
all affected development/validation experiments have been rerun. Any such
change invalidates a previously supplied validation nonce.

## Review finding details: v1 revision

This is an **agent review**, not human expert certification. The initial review
was performed on 2026-09-07 by the dedicated session `/root/primitive_review`.
The session identifies itself as Codex, with a GPT-6 family description supplied
by its instructions; an exact runtime model build identifier is not exposed.
No exact model identifier, independent human expertise, or validation approval
is inferred from that description.

The reviewed starting revision is
`c60e1d069b97006aa22793921e9a2c5a64100edf`. Its top-level research Python source
digest, using the historical runner's filename/NUL/content algorithm, is
`72544022985f8eda01e9fc2d05746c1ec4ce77a3b44a93bcdf17dd5c84b1274f`.
Relevant SHA-256 inputs are:

| Input | SHA-256 |
|---|---|
| `constants.py` | `c06812a9594bc6cd33011dfc2f62d287fa235911128b46a6f8df3a1f847b0b6d` |
| `solvers.py` | `04471acde7c275865f87b9529a7617499bc8c87589793a1ac64f6fdf2835b16e` |
| `requirements.txt` | `cd48847318bc58dc9768199b6c6bdc39348848bcec5ceac88ff45bec91880e90` |
| `Dockerfile` | `ab9d7df8f1d963abf470609e1cef726dca395dd8de8b5af7bd4c543df336a5b1` |
| `schemas/instance-v1.schema.json` | `64a443540b5c056048bc25e5d2fa4b53162ee1538049ec7c02e5483e4f17567e` |
| `schemas/result-v1.schema.json` | `0ff77bdd1f614542c8b987f4b45ec80673f9a9d25caf783c19b267f981ef4ad1` |

The historical 780-record file has SHA-256
`ed6107793f54a0578c7a9d802119152c59ede1171f9dc2a39a178a22c25f250e`.
Its records retain harness revision `b33f229338695fcccfba415245058deb772a5a8f`
and source digest
`747181075905c955a3fb72fa2925c6c8d7368a09175ac958760d2c6b63e26877`.
Those are the original measurement provenance, not the later review revision.
Review probes are additional development diagnostics; they do not replace that
cohort or constitute held-out evidence.

### Reproducible adversarial evidence

Run the following from the repository root with the repository environment:

```sh
source .venv/bin/activate
python research/primitive_selection/review/adversarial_v1.py > /tmp/adversarial-v1-rerun.json
```

The probe explicitly loads the reviewed Git revision into a temporary package,
so future generator repairs do not silently change the experiment. It accepts
no third-party instance, key, signature, or practical parameter input. The
retained output is
[`adversarial-v1.json`](../research/primitive_selection/review/adversarial-v1.json).
Creation time and CPU timings will differ on rerun; instance IDs, recovered
answers, verification results, and counts must match.

| Profile | Cases (10 seeds x 2 eta) | Direct modular exact recovery | Singular matrices declined | Seed reconstruction MLWE / MSIS | `q*unit` accepted by v1 verifier |
|---|---:|---:|---:|---:|---:|
| small | 20 | 20 | 0 | 20 / 20 | 20 |
| medium | 20 | 18 | 2 | 20 / 20 | 20 |
| large | 20 | 18 | 2 | 20 / 20 | 20 |

Direct modular CPU medians were approximately 0.000097, 0.00153, and 0.0252
seconds on this review host. These single diagnostic timings are not paired
benchmark comparisons and have no uncertainty estimate. Exact answer recovery,
which is deterministic, establishes the shortcut without any timing claim.

The same script exhaustively compares 625 degree-2 polynomial products and
coefficient-matrix actions modulo 5 against an independent expanded-polynomial
reduction. It also checks the Bareiss determinant against the permutation
formula on all 19,683 ternary 3-by-3 matrices. All pass.

### F01 — blocking: public generation seed reconstructs answers

`models._base` puts `seed` into every public instance, and `generator._rng`
derives matrix and witness streams from public version, track, profile, seed,
and purpose labels. Omitting named `planted_*` fields does not create an answer
boundary. Calling the repository generator with public metadata reconstructs
both MLWE short vectors and the MSIS relation on all 120 generated development
instances. The existing boundary test checks field names, not recoverability.

Required remedy: a new public schema without generation seeds or equivalent
reconstruction metadata; evaluator-only generation records and witnesses;
strict public-field allowlists; tests for metadata replay; and explicit
cooperative-code restrictions on evaluator files, environment, known-seed
lookup, and regeneration. A public matrix-only stream could be safe if
independent of witness generation, but disclosing the shared seed is not.
Public development seeds and published result files still permit lookup by
instance ID, so a seedless interface alone is not a hostile-code sandbox.
Fresh validation randomness must remain evaluator-side during execution.

Disposition: **open for repaired candidate**. V1 is ineligible. Prior results
remain valid observations of those specific adapters, not evidence that the
public problem requires those adapters.

### F02 — blocking for v1 MSIS: noiseless square modular recovery

Write the generator's matrix as `A = [B | c]` and planted vector as `(w, 1)`.
The current profiles have `columns - 1 = rows`, so `B` is square over the ring,
and the public column is exactly `c = -B*w`. Its coefficient embedding yields
an ordinary square linear system `C(B)*vec(w) = -vec(c) mod q`. Invert it modulo
q and center the residues. Since every planted coefficient lies in `[-eta,eta]`
and `2*eta < q`, the centered answer is exactly the witness whenever invertible.
The probe reads only A, dimensions, and q for this step. No generator seed,
planted witness, lattice reduction, or enumeration is needed.

The 56/60 recoveries establish a broad distribution shortcut. Four singular
cases were explicitly declined; they are not measured failures of modular
recovery with a nullspace search. Fixing a witness component to a primitive unit
ensures primitivity but does not ensure hardness. Replacing 1 by another known
unit or hiding the generation seed does not remove the noiseless equation.

Required remedy: **disqualify this distribution**, or replace it with a new,
reviewed distribution and rerun development. A possible independent MSIS study
would sample uniform A and impose fixed meaningful norm bounds; feasibility and
baseline difficulty would have to be measured. A secret-dependent planted norm
is not an independently calibrated threshold. The reviewer does not approve an
untested replacement merely because it resembles the standard definition.

Disposition: **v1 planted MSIS disqualified before scoring**. The old 95-point
rubric score and within-five-point tie rule cannot confer eligibility.

### F03 — blocking for a short-relation challenge: bounds are not enforced

`verify_msis` accepts every nonzero integral modular relation. Its result has
`meets_target`, but the worker's success flag uses only `verified`, and the
infinity-norm target is never enforced. Thus `q` times a coordinate unit passes
all 60 development instances while exceeding both intended shortness targets.
This is a valid lattice relation but not a successful short-relation solution.

Required remedy: version the meaning of success; explicitly require both public
norm bounds at the correctness gate, retain recomputed quality separately, and
reject zero, malformed, out-of-bound, and incorrect candidates. Historical
success flags must not be retrospectively reinterpreted as the stronger gate.

Disposition: **open for any retained MSIS comparator or proposed challenge**.
Disqualifying the primitive addresses selection, while correcting the
comparator prevents misleading new measurements.

### F04 — blocking: cohort audit does not establish scientific integrity

The v1 auditor validates a few fields, three repetitions, CPU median, one output
digest, and coarse seed membership. It accepts an arbitrary one-record
"development cohort" (the existing test intentionally does this), unknown
solver combinations, duplicates, missing cases, inconsistent revisions/config,
wrong input digests, invented success/quality, and validation seeds not actually
derived from the recorded nonce. It never regenerates the instance or verifies
the stored candidate. The runner retains records in memory until completion,
replaces existing output files, and loses interrupted case evidence.

Required remedy: a versioned unique run manifest and complete case matrix;
exclusive creation and append-preserved partial evidence; finalized-cohort
marker; configuration/revision/dependency/input/output provenance checks;
independent candidate verification and quality recomputation; all aggregate
checks; and intentional rejection tests for every listed tampering class.
Archival v1 audits must use the v1 generator/verifier and identify their weaker
historical shortness definition explicitly.

Disposition: **open** pending audited repaired development and validation runs.

### F05 — blocking: no demonstrated eligible difficulty/solver portfolio

Every unsuccessful v1 cohort case has a declared dimension, difficulty, or
exhaustive-search cap. There are 380 verified cases and 400 declared caps, not
400 measured algorithmic failures. The earlier 60-second pilot observations
motivating caps are mentioned in prose; this cohort contains no timed-out
measurements of those pilots. Caps can responsibly protect the machine, but
cannot substitute for studying useful difficulty.

MSIS has one applicable profile and the same reduction-plus-enumeration
architecture under three schedules. MLWE has primal CVP with LLL/BKZ kernel
variants, plus coefficient-guessing residual CVP on small; exhaustive solving is
valid only on the evaluator fixture. LLL and BKZ, or fixed/progressive/restarted
BKZ, are useful strategy comparisons but not automatically unrelated complete
solver families. CVP enumeration is a different search operation from Babai
nearest-plane. A hybrid with explicit guessing adds a meaningful combinatorial
tradeoff when measured and applicable, even if it shares its residual kernel.
The backend documents these operations separately. [fpylll module reference](https://fpylll.readthedocs.io/en/latest/modules.html).

Required remedy: development-only profile calibration within the existing
safety ceilings; direct modular and simple-search comparators; a reference that
solves at least two predeclared useful levels; and two demonstrably applicable
approaches with recorded runtime/success or quality tradeoffs. Freeze numeric
eligibility before scoring, then apply it unchanged to validation. A small
exhaustive starter can be useful, provided its simple solver receives credit
and a separate level offers demonstrated headroom beyond that search cap.

Disposition: **open**. No candidate is selected from v1. MLWE is the most direct
candidate to reevaluate after F01 because its error term removes the specific
noiseless MSIS inversion argument; that is a research priority, not approval.

### F06 — blocking: reduction-share gate uses an incomplete denominator

The generated report computes reduction divided by the sum of its three named
phases. This excludes uninstrumented work and verifier CPU, although the paired
runtime comparisons use complete worker CPU. The following recalculation uses
the same raw cases and shows why phase dominance is not complete-solver
dominance:

| Solver | Median reduction / phase sum | Median reduction / complete worker CPU |
|---|---:|---:|
| MLWE primal BKZ | 90.93% | 54.85% |
| MLWE hybrid BDD | 85.91% | 62.67% |
| MSIS progressive BKZ | 94.20% | 69.64% |
| MSIS restart BKZ | 92.16% | 71.01% |

Required remedy: preserve the 70% gate and define its denominator explicitly as
all complete-solver CPU, with verification separately identified if moved out
of that interval. Report both phase ratios and complete-runtime ratios with
clear labels. The existing evidence does not meet the multiple-family 70%
complete-runtime claim.

The second gate is independently unsatisfied: generated paired substitutions
show -6.7% small MLWE, -3.7% medium MLWE, and -41.0% small MSIS median gains.
These are slowdowns, and no two-size 20% gain is established. Large reduction
share is only opportunity for an optimization; it is not evidence that a more
expensive reduction improves the entire solver.

Disposition: **BKZ selection gate failed visibly**. A documented denominator
correction is required before freeze; neither numeric threshold is waived.

### F07 — high: derived-basis first-vector quality has a trivial floor

The MLWE Kannan embedding contains an explicit row with one error coordinate
and one equation coordinate equal to 1. Its squared norm is 2 for every input.
All 120 successful MLWE-derived BKZ records have first-vector squared norm 2.
The first-vector objective on this embedding therefore rewards recovering a
fixed structural short vector, unrelated to recovering the planted bounded
solution. RHF below 1 is mathematically possible for an anisotropic lattice;
it is not invalid arithmetic, but no generic random-lattice hardness or
recovery-quality inference follows from that value.

Required remedy: reject this basis-quality objective as the organizing
challenge, or independently justify and remeasure a different embedding and
quality functional. Retain it as a clearly labeled research comparator if
helpful. Do not compare RHF across dimensions/determinants/source embeddings as
one primitive score.

Disposition: **current BKZ objective disqualified for selection**, in addition
to its failed gain gate. Arithmetic provenance verification remains valuable.

### F08 — high: resource and failure evidence requires explicit semantics

The 60-second parent timeout and 2-GiB address-space setting are appropriate
research caps, not cryptographic security estimates. V1 treats signals 9 and 11
as memory failures without evidence that either came from memory exhaustion.
A segmentation fault is a crash unless independently attributed. Worker CPU
starts after Python imports; peak RSS includes interpreter/backend state; phase
CPU, worker CPU, and parent elapsed wall time cover different intervals.
`RLIMIT_AS` failure is silently tolerated. Warm-up output is discarded.

Required remedy: separate cap, timeout, explicit memory exhaustion, crash,
invalid candidate, and no-solution statuses; preserve warm-up evidence; verify
resource limits in the target Linux container; test parent timeout behavior and
failure aggregation; and document startup/timing/cooperative instrumentation
assumptions. A process limit is not proof that hostile solver code cannot read
files, disable limits, spawn descendants, or falsify timing fields.

Disposition: **open for measurement freeze**. Do not reinterpret all abnormal
termination as memory exhaustion or all caps as unsuccessful search.

### F09 — medium: stale narrative and rubric overstate evidence

The narrative's paired gains (-2.0%, -3.0%, -21.1%) conflict with the generated
report (-6.7%, -3.7%, -41.0%). Narrative phase shares 90.8% and 94.6% also differ
from the regenerated table. Fix narrative summaries from raw-data-generated
analysis and preserve the original JSONL provenance. The historical fallback
weights total 100, but assigning 18/20 diversity and 10/10 integrity before
eligibility and audit was not supported. Eligibility must precede the unchanged
weighted/tie fallback; MSIS cannot win by a nominal one-point advantage after
F02 disqualification.

Disposition: **open for narrative repair and frozen rubric correction**.
The review does not approve retrospective score changes that conceal why the
prior recommendation failed.

### F10 — medium: parameter and distribution claims need precise scope

The repository caps n at 32, q at 257, and ranks at 5. Standard ML-DSA uses degree
256 and modulus 8380417, so the instruction that tiny profiles correspond to an
actual standardized parameter set cannot literally be satisfied within the
safety boundary. The authorized synthetic study must describe itself as a
structural analogue, preserving caps. ML-DSA relies on MLWE and a nonstandard
SelfTargetMSIS assumption; ordinary short-relation search is not signature
forgery. [FIPS 204, Sections 2.3, 3.2, and Table 1](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.204.pdf).

The current ring checks ensure `q = 1 mod 2n`, but do not alone establish q
prime, n a power of two, or an approved profile combination. The three actual
v1 profiles do have prime q and power-of-two n. A strict new public parser
should bind to versioned profiles instead of accepting arbitrary tuples under
the numeric caps. The generator's uniform bounded secrets are a toy
small-secret MLWE variant, not a claim that every cited worst-case reduction
applies to these tiny parameters or distributions. The primary module-lattice
paper defines distributional problems and parameter-dependent reductions;
no such hardness theorem is established for this benchmark. [Langlois and
Stehlé, *Worst-Case to Average-Case Reductions for Module Lattices*](https://perso.ens-lyon.fr/damien.stehle/downloads/MSIS.pdf).

Disposition: **clarification required; caps unchanged**. No production
parameter, target ingestion, or signature functionality is authorized.

### Explicit disposition of every review question

| Question | Review answer | Evidence and required disposition |
|---|---|---|
| 1. Ring and coefficient embeddings | The negacyclic sign convention and row-vector embeddings are consistent on review. | Exhaustive 625 tiny differential products/matrix actions pass; existing planted-vector embedding identities are algebraically valid. Acceptance is limited to arithmetic, with F07 warning about objective usefulness. |
| 2. Planted MSIS primitive unit | Yes, it creates a decisive noiseless inversion shortcut. | F02: 56/60 exact modular recoveries, 4 explicit singular declines. Disqualify v1 distribution before scoring. F01 additionally permits 60/60 seed recovery. |
| 3. Independent verification | Exact `det(U)=±1` and `B'=U*B` are sound for a trusted source basis; the overall evidence boundary is insufficient. | 19,683 determinant fixtures pass. F03 adds actual MSIS shortness; F04 regenerates source instances/bases and candidates; parser/provenance checks must prevent trusting a merely asserted source ID. |
| 4. Solver diversity | Parameter schedules are useful alternatives but cannot alone establish independent complete approaches. | F05: CVP, hybrid guessing, exhaustive and nearest-plane comparisons must show applicable measured tradeoffs; merely swapping LLL/BKZ or restarting is not sufficient to claim three unrelated families. |
| 5. Caps and difficulty | Caps are defensible resource policy; capped outcomes do not establish difficulty. | F05/F08: retain 60 s and 2 GiB, distinguish all statuses, calibrate development-only profiles and establish two useful eligible levels. Historical unretained pilot timings cannot be reconstructed from the 780 records. |
| 6. Quality/resources | Separate metrics are appropriate; some interpretations are not. | F03: relation validity is not bounded shortness. F06: incomplete share denominator. F07: RHF below 1 is possible and the MLWE basis has a trivial norm-2 vector. F08: define timing/RSS scopes and crash attribution. |
| 7. Fallback and disqualification | Weighted fallback applies only after eligibility. | Disqualify v1 planted MSIS and current BKZ objective; preserve failed BKZ 70/20 gates. MLWE may be calibrated after payload repair but is not yet approved. F09 requires evidence-backed rubric/status repair before freeze. |

### Primary sources inspected and limits of the review

- [NIST FIPS 204 official publication](https://csrc.nist.gov/pubs/fips/204/final)
  and its PDF: ring, structure, parameter sets, and computational assumptions.
  The publication page's errata notice does not change this toy study's caps.
- [Langlois and Stehlé's author-hosted module-lattice paper](https://perso.ens-lyon.fr/damien.stehle/downloads/MSIS.pdf):
  definitions and scope of reductions. The IACR PDF endpoint denied automated
  retrieval; the author-hosted PDF was successfully inspected instead.
- [Regev's author-hosted LWE paper](https://cims.nyu.edu/~regev/papers/qcrypto.pdf):
  noisy linear systems and the distinction from ordinary linear elimination.
- [fpylll 0.6.4 API documentation](https://fpylll.readthedocs.io/en/latest/modules.html),
  [fplll CVP/SVP contracts](https://fplll.github.io/fplll/svpcvp_8h.html), and
  [tagged fpylll 0.6.4 BKZ parameter source](https://github.com/fplll/fpylll/blob/0.6.4/src/fpylll/fplll/bkz_param.pyx):
  row-basis conventions, nearest-plane versus enumeration, fast versus proved
  CVP guarantees, and automatic enabling of `BKZ_MAX_LOOPS` when `max_loops>0`.
  Requested tours are settings, not measured internal enumeration operations.

The review is a code/mathematical and reproducible-toy review, not a proof of
hardness, a production cryptanalysis assessment, a sandbox audit, or human
specialist certification. Single-probe timing is not benchmark evidence. The
780 observations are development data with paired eta values sharing seeds;
three timing repetitions are not three independent problem instances.
Uncertainty must resample or summarize seed clusters, retaining paired solvers
and eta values together. No validation nonce has been generated by this agent.

## Approval statement: initial review, 2026-09-07

**Approval withheld.** The current MSIS proposal fails the direct-recovery and
useful-difficulty gates; the public payload exposes answers on both primitive
tracks; BKZ's objective and measured gain gate fail; and the measurement audit
cannot establish complete independently verified cohorts. F01 and F03–F10
require disposition through repairs, exclusion with justification, or explicit
unresolved gates before a reviewed freeze. F02 is a final disqualification of
the v1 planted distribution, not a waived scientific failure. No nonce or
held-out approval is issued. A repaired MLWE candidate can be reviewed on its
own development evidence, followed by an immutable freeze and fresh validation.

## Repair review in progress: v2, 2026-09-07

The reviewer independently inspected the proposed seedless dataclasses,
strict public-field parser, eta-separated generator streams, both MSIS norm
checks, restored v1 archive, cohort auditor, failure classification, and
proposed decision/ranking module. The archived original Python source digest
now reproduces the original measurement digest
`747181075905c955a3fb72fa2925c6c8d7368a09175ac958760d2c6b63e26877`.

The independent probe
[`contract_probe_v2.py`](../research/primitive_selection/review/contract_probe_v2.py)
runs with:

```sh
source .venv/bin/activate
python -m research.primitive_selection.review.contract_probe_v2 > /tmp/contract-v2-rerun.json
```

Its retained working-source diagnostic
[`contract-v2.json`](../research/primitive_selection/review/contract-v2.json)
records its exact source digest and confirms 240 public round trips, 240
rejected seed injections, 60 valid generated MLWE witnesses, 60 valid generated
MSIS witnesses, 60 rejected q-unit relations, 60 rejected zero relations, and
15,625 exhaustive bounded/unbounded candidate comparisons against independent
tiny MLWE coefficient equations. This supports the code remedies for F01 and
F03; closure still requires the final repaired development and validation
cohorts under the frozen implementation. Source/revision identity in this
probe records a working-tree review, not a clean final freeze.

The reviewer accepts a pre-freeze expansion from 13 to 16 case combinations per
profile/eta/seed to include MLWE direct modular solving, MSIS direct modular
recovery, and sparse relation search. This makes the complete development and
validation cohorts 960 and 1,920 records, respectively; the original portfolio
subset remains 780 and 1,560 records. The frozen manifest must enumerate both
counts and the actual complete grid. Adding simple methods to the common
1-warm-up/3-repetition harness gives them the same provenance and resource
checks. It does not revive the disqualified planted MSIS construction.

The proposed MLWE challenge cells are small/eta 1, small/eta 2, medium/eta 1,
and medium/eta 2; large is a retained stress comparison. Subject to final
calibration evidence, the reviewer accepts the following viability gates for
freezing: reference success at least 90% in every challenge cell; a genuinely
different exhaustive or hybrid family at least 80% in one challenge cell;
at least two distinct degrees; medium/small median complete reference CPU
ratio at least 2; a nonstarter challenge level beyond the fixed exhaustive cap;
and no invalid submitted candidates. Direct modular success at least 90% in
every challenge cell would disqualify the formulation as insufficiently useful
for this challenge. These are minimum empirical viability thresholds, not a
cryptographic hardness statement. The same thresholds must hold on untouched
validation seeds; failure must remain visible.

Additional integration issues reported to the implementation agent include
using `status` consistently in eligibility/ranking (including mixed cases with
an invalid repetition), checking exact dependency sets and frozen metadata in
the auditor, required successful-worker resource evidence, and Wilson
intervals for per-cell success. These must be verified in the final code before
F04–F06/F08 closure. No validation nonce or freeze approval has been issued.

## Development-only difficulty repair review: 2026-09-08

The proposed four-cell small/medium challenge **failed its proposed 2x
complete-reference-runtime separation gate** on the retained 72-case
calibration. The reviewer recomputed the raw records in
`review/calibration-v2-mlwe-01/records.jsonl`: primal-LLL median complete CPU was
0.0262535 s on pooled small/eta 1 and 2 (six seed/eta cases), 0.032911 s on
pooled medium/eta 1 and 2 (six cases), and 0.325584 s on large/eta 1 (three
cases). The medium/small ratio is **1.253585**, below 2. The large/eta-1 versus
pooled-small ratio is **12.401546**. These are diagnostic calibration
observations with one timed invocation per case, not the final three-repeat
cohort or validation evidence. The original records are retained.

The reviewer accepts the following **pre-freeze repair proposal**, rather than
waiving the failed criterion: include large/eta 1 as a fifth equally weighted
ranked challenge cell, retain large/eta 2 as unranked stress evidence, and
require the predeclared large/eta-1 reference median divided by pooled-small
reference median to be at least 2. All five challenge cells must independently
meet the 90% reference-success threshold on all development seeds and again on
untouched validation seeds. The different-family threshold, practical
exhaustive-headroom check, zero-invalid-answer requirement, direct-shortcut
check, safety caps, BKZ gates, and fallback eligibility ordering are unchanged.
Medium provides an intermediate level and exhaustive-search headroom; its
calibration does not independently establish a 2x runtime level.

This is a changed proposed challenge/ranking configuration before any freeze or
reviewer nonce. Full development must establish large/eta-1 applicability under
the repaired common measurement configuration. The reviewer has not approved
freezing or selecting the candidate from the three calibration seeds. A failed
full-development or held-out gate remains a failed gate and cannot be closed
by referring to this provisional acceptance.

## Official-specification errata check: 2026-09-08

The reviewer retrieved and inspected the actual
[NIST FIPS 204 potential-updates spreadsheet](https://csrc.nist.gov/files/pubs/fips/204/final/docs/fips-204-potential-updates.xlsx),
marked last updated 2026-07-31, rather than relying only on the publication-page
notice. Download SHA-256:
`5bc93ce63bc647e6d1d456cb2d3a171426c15aca4a7a0e0edd40d08b7a34c793`.
The source URL, retrieval timestamp, spreadsheet cell references, and extracted
rows are retained in
[`fips204-errata-20260908.json`](../research/primitive_selection/review/fips204-errata-20260908.json).
The web reader could not decode XLSX; the official file was downloaded and its
XML cells inspected directly. NIST labels these as potential corrections for a
future publication update.

The mathematically relevant clarification corrects the NTT exposition: choose
the appropriate root of unity, then evaluate the polynomial once, not twice.
The research implementation performs direct coefficient negacyclic convolution,
so it neither implements nor relies on the erroneous double evaluation.
Infinity-norm and polynomial-vector corrections concern notation and naming;
the verifier already computes the maximum absolute coefficient of complete
vectors. The Table 1 update changes signing repetition estimates, not the
modulus, ring degree, ranks, or short-secret parameter referenced by this study.
Other entries concern signature message ordering, internal routine names,
failed signature-verification returns, Montgomery reduction, UseHint, and
signing loop limits. None of those algorithms is implemented by this research
package. No generator, ring, or verifier repair is required by these entries;
this disposition is limited to the synthetic primitive study and is not a
claim of a conforming ML-DSA signature implementation.

## Dated development acceptance and pre-freeze disposition: 2026-09-08

The dedicated reviewer accepts the repaired candidate and the disposition of
implementation findings at source revision
`9ad9423f7325b73383d250eb48353c3bd816da40`, **conditional on completing the
mandatory two-clean-build reproduction check before freezing**. This is
permission to advance the scientific study to a reviewed freeze; it is not
held-out approval, primitive selection, or permission to waive a failed gate.
No validation nonce has been created.

The accepted complete development run is
`20260908T015636Z-64f6da9501f3478f8edf986f965e9513`, stored under
[`v2-development-20260908`](../research/primitive_selection/results/v2-development-20260908/).
The source, configuration, and dependency digests are respectively:

- `24e45c29e8abf088d5b4a0528cc9a5fb8dd87c502b451720c4c4095f95b69d26`
- `4625e878086446bb698b750c2f60cf8df20819dbf2e4c2c8439648bd2db19fbd`
- `c942b0aacf2afbc007ca0ab3510f29a7d3db0b769f3e2f0a99a3673067fd2734`

All records identify a clean source revision and container image
`sha256:59dcfc904ac66c02c16034e1ba9e305cca0a47950df02762bf5ca4319c150801`.
The raw JSONL SHA-256 is
`70b87590896da4e3af3e83003b8fbad7040df9b40bf931f313141f09828440d4`.
The reviewed strict container audit independently regenerated every input,
reverified candidate correctness/quality and exact BKZ provenance, checked the
full randomized grid and aggregates, and passed all **960 records**. Outcomes
are **717 success, 123 no-candidate, 120 declared applicability caps**, with no
timeouts, memory failures, crashes, invalid answers, or mixed cases. Caps are
not measured failures of algorithms that never ran.

The reviewer separately recomputed the raw counts and numerical gates,
reproduced REPORT.md byte-for-byte with the prescribed `PYTHONHASHSEED=0`, and
reproduced every JSON-normalized CONCLUSION.json field and number. The reviewer
also regenerated the MLWE/MSIS instances and independently reverified all
**2,400 stored non-BKZ warmup/measured outputs**, representing 273 distinct
instance/candidate pairs. The reviewer inspected the full exact-BKZ auditor and
its same-container passing evidence rather than duplicating the entire BKZ
audit a second time. File digests and review scope are retained in
[`development-review-20260908.json`](../research/primitive_selection/review/development-review-20260908.json).

| Ranked cell | Reference successes | Median reference CPU | Hybrid successes | Exhaustive successes |
|---|---:|---:|---:|---:|
| small, eta 1 | 10/10 | 0.006066 s | 10/10 | 10/10 |
| small, eta 2 | 10/10 | 0.006340 s | 10/10 | 10/10 |
| medium, eta 1 | 10/10 | 0.013395 s | 10/10 | 0/10, declared cap |
| medium, eta 2 | 10/10 | 0.013802 s | 9/10 | 0/10, declared cap |
| large, eta 1 | 10/10 | 0.345085 s | 10/10 | 0/10, declared cap |

The exact large/eta-1 versus pooled-small reference CPU ratio is **56.716471**,
exceeding the unchanged 2x gate. All five reference-success gates and the
separate-family gate pass. Direct MLWE modular solving produces no bounded
solution on all 60 development instances. Exhaustive search solves the starter
roughly an order of magnitude faster than the lattice reference, and the
medium/large cases exceed its fixed one-million-assignment applicability cap.
Hybrid guessing plus nearest-plane decoding provides a different applicable
approach from closest-vector enumeration; its one medium/eta-2 no-candidate
outcome remains visible and receives the specified ranking penalty. Large/eta
2 stress has 8/10 hybrid successes while both primal CVP baselines uniformly
declare their eta-2 applicability cap. None of these development observations
is a population-hardness claim or a substitute for held-out evidence.

The two BKZ scientific gates **fail** on the repaired development cohort:
zero distinct measured families meet the 70% complete-CPU threshold, and no
comparison reaches a 20% gain at two sizes. The median seed-level MLWE
substitution gains are -1.60% small, -5.28% medium, and -2.61% large. The
MSIS-derived comparison is also ineligible because its generator still admits
direct modular recovery. The original failed BKZ gate and disqualified MSIS
construction remain recorded; no fallback points can override these exclusions.

### Accepted finding dispositions at the development checkpoint

| Finding | Accepted disposition | Evidence remaining before final selection |
|---|---|---|
| F01 | Seedless strict public schema and eta-separated evaluator streams accepted; cooperative-code limitations explicitly specified. | Same frozen boundary must be used throughout validation. |
| F02 | Planted MSIS remains disqualified before scoring; retained direct comparator demonstrates its shortcut. | No repair or selection of that construction is claimed. |
| F03 | Both MSIS norm bounds are now correctness gates; q-unit/zero regressions and independently verified outputs accepted. | Retain the v1 cohort's weaker historical meaning. |
| F04 | Unique complete/partial runs, strict provenance/completeness auditing, input regeneration and stored-candidate revalidation accepted. | Apply the same audit to the full held-out cohort. |
| F05 | Five declared challenge cells meet reference, family, exhaustive-headroom, and 2x difficulty gates in full development. | All unchanged numeric gates must hold in held-out data. |
| F06 | Complete-CPU denominator and seed-paired statistics accepted; both BKZ gates fail visibly. | Repeat and report those gates on held-out data without waiver. |
| F07 | Current derived-basis first-vector objective remains disqualified; its exact arithmetic checks are retained as comparator evidence. | No selection of the trivial objective is claimed. |
| F08 | Explicit statuses, successful-worker limit evidence, pinned artifacts, one-plus-three protocol, timeout/interruption tests and strict audit accepted. | Two-clean-build reproduction and identical frozen validation configuration. |
| F09 | Original narrative preserved; generated summaries and eligibility-before-fallback interpretation accepted. | Final narrative must derive from both complete cohorts. |
| F10 | Structural-analogue scope, unchanged safety ceilings, fixed-profile parser, and official errata disposition accepted. | No standardized-parameter or production-hardness claim. |

The accepted fallback assessment retains the historical MLWE total **94/100**
with weights and scores relevance 29/30, diversity 18/20, headroom 13/15,
verification 14/15, measurement 10/10, and safety/reproducibility 10/10. The
rationale is now bounded and evidence-backed: relevance is structural rather
than full standardized ML-DSA; exhaustive/CVP/hybrid approaches are applicable;
three degrees and retained stress cases offer headroom; exact feasibility is
clear; and corrected provenance/resource checks support comparison. These are
judgmental rubric points, not measured cryptographic quantities. The last two
scores are conditional on the outstanding reproduction/held-out gates. MLWE
is the sole currently eligible fallback candidate; MSIS and BKZ receive no
eligible score and do not participate in the five-point tie rule.

The scientific specification now fixes five-cell scoring, anchored tie groups,
seed-cluster score uncertainty, 20 seeds per profile for 100 ranked cases per
future evaluation epoch, fresh evaluator-only nonce generation, and the
reference-table lifecycle. The reviewer finds no additional scientific design
choice necessary before implementation **if** unchanged held-out evidence
supports selection. Final approval remains withheld until the reproduction,
committed freeze, post-freeze nonce, complete validation audit, and dated final
review are finished.
