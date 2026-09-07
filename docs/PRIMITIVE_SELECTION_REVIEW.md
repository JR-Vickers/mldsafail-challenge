# Agent Lattice-Cryptography Review Packet

## Review status

- Review agent/model and session identifier: pending
- Reviewed commit and source/configuration digests: pending
- Review scope and limitations: pending
- Review date: pending
- Decision: pending
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
| — | — | No review received | — | — | pending |

A blocking finding is resolved only after the reviewer accepts the change and
all affected development/validation experiments have been rerun. Any such
change invalidates a previously supplied validation nonce.

## Approval statement

The reviewer should replace this section with a dated statement that either:

- approves Module-SIS short-relation search for the next benchmark design;
- approves a different primitive with reasons tied to the decision rule; or
- withholds approval and lists the remaining blocking findings.
