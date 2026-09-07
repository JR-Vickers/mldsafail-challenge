# Primitive selection research

Primitive selection is incomplete. The independent agent review has found blocking scientific and interface defects in research v1. The earlier Module-SIS recommendation is withdrawn; v2 is evaluating MLWE against the eligibility gates before applying the fallback rubric. Benchmark 0.4.0 and hosted integration are unchanged.

The original 780 development records and generated report are preserved byte for byte in `research/primitive_selection/results/`. They identify measurement revision `b33f229338695fcccfba415245058deb772a5a8f`; the starting review revision was `c60e1d069b97006aa22793921e9a2c5a64100edf`. The initial `make check` passed 144 tests and benchmark small score 3901. Original report byte reproduction passed. Baseline provenance is in `research/primitive_selection/review/baseline.json`; the historical narrative is retained in `research/primitive_selection/review/NARRATIVE-v1.md`.

The dedicated review and reproducible adversarial evidence are in [the finding log](PRIMITIVE_SELECTION_REVIEW.md). Its initial findings supersede the old narrative:

- Public generation seeds reconstruct every planted answer. V2 public dataclasses and JSON omit seeds, with strict field rejection. Evaluator records retain reproducibility metadata.
- The planted Module-SIS construction fixes the final witness polynomial to one and admits direct modular recovery through its square prefix. It is disqualified as a proposed challenge, while remaining a labeled research comparator.
- V1 Module-SIS verification accepts relations outside the advertised shortness bounds. V2 requires both Euclidean-squared and infinity bounds. Historical success flags retain their historical meaning.
- The old reduction-share denominator includes instrumented phases only. Complete-worker CPU gives median shares of approximately 54.9%, 62.7%, 69.6%, and 71.0% for primal BKZ, hybrid BDD, progressive MSIS, and restart MSIS. These do not establish the 70% gate in two distinct end-to-end solvers. Consuming reduction time alone does not establish useful improvement.
- Every successful v1 MLWE-derived basis reduction has first-vector squared norm 2, explained by a trivial basis vector. BKZ also lacks the required measured 20% complete-solver gain at two sizes.
- Declared applicability caps are unmeasured cases, not observed algorithm failures. The historical 94/95 fallback scores cannot make an ineligible candidate eligible.

The 70%/20% BKZ gates and six fallback weights (30/20/15/15/10/10, five-point Module-SIS tie preference) are retained. Eligibility checks will precede scoring. A freeze, fresh post-freeze reviewer nonce, complete held-out cohort, clean-build reproduction, and explicit reviewer approval remain mandatory. No failed gate is waived.
