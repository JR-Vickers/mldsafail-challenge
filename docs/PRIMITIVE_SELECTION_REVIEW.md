# Agent Lattice-Cryptography Review Packet

## Review status

- Review agent/model and session identifier: Codex / GPT-6 family description; exact runtime build not exposed; `/root/primitive_review`
- Reviewed commit: `c60e1d069b97006aa22793921e9a2c5a64100edf`; source/configuration digests below
- Review scope: mathematical definitions, code, adversarial synthetic probes, raw development evidence; limitations below
- Review date: 2026-09-07
- Decision: initial approval withheld; blocking findings below; no primitive selected
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
| F01 | blocking | Public seed reconstructs MLWE/MSIS answers | pending | required | open |
| F02 | blocking | Planted MSIS reduces to square modular solve | exclusion required | 60 adversarial fixtures | v1 distribution disqualified |
| F03 | blocking | MSIS success lacks norm-bound correctness gate | pending | required | open |
| F04 | blocking | Audit trusts incomplete/unverified cohorts | pending | required | open |
| F05 | blocking | Useful difficulty and solver coverage unestablished | pending | required | open |
| F06 | blocking | Kernel-share denominator omits runtime | pending | raw 780 recalculated | BKZ gate failed |
| F07 | high | BKZ first-vector objective has trivial structural floor | exclusion required | 60 basis fixtures/raw 120 cases | current objective disqualified |
| F08 | high | Resource/failure categories and intervals ambiguous | pending | required | open |
| F09 | medium | Stale summary and eligibility-free fallback scores | pending | raw report comparison | open |
| F10 | medium | Standard-parameter/distribution claims need scope | pending | primary specifications | clarification required |

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
