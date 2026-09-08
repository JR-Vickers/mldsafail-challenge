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

## Repaired development evidence (2026-09-08)

The version-2 cohort at source revision 9ad9423 contains all 960 cases: the original 13-combination portfolio plus three simple comparators. Independent auditing regenerated inputs and verified every stored warmup/measured candidate, quality, grid, aggregate, and digest. It found 717 successes, 123 no-candidate outcomes, and 120 declared applicability caps, with no invalid answers, crashes, timeouts, or memory failures.

The MLWE reference solves all 50 ranked development cases across small/eta1, small/eta2, medium/eta1, medium/eta2, and large/eta1. The hybrid solves 49/50, providing an observed success/runtime tradeoff. Large/eta1 is 56.716x the pooled-small median reference CPU. Large/eta2 remains stress evidence. The initial small/medium-only calibration failed the proposed 2x gate and is preserved; adding the measured large/eta1 challenge cell before freeze repairs that failure without lowering the threshold.

Direct modular MLWE solves 0/60 development cases. Direct modular MSIS solves all 60, confirming its disqualification. BKZ fails the complete-runtime dominance and two-size gain gates. The five-cell exact ranking, cooperative-code assumptions, generator, verifier, epoch/reference lifecycle, and production migration requirements are specified in [the proposed contract](PRIMITIVE_SELECTION_SPEC.md).

Raw evidence, audited tables, and reproducible quantitative gates are in [the development packet](../research/primitive_selection/results/v2-development-20260908/REPORT.md), alongside AUDIT.json and CONCLUSION.json. The original v1 report remains byte-identical and reproduces with the preserved c60e1d0 renderer; the measurement generator/verifier archive remains b33f229. These distinct provenance roles are recorded explicitly.

Selection still requires clean-build reproduction, a committed freeze, a fresh reviewer nonce, all 1,920 held-out records, and final agent approval.
