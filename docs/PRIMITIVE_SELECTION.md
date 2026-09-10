# Primitive selection research

MLWE bounded recovery is selected for the next benchmark. The dedicated review agent approved the frozen challenge on 2026-09-10 after development and held-out validation; every blocking finding has an explicit closed disposition in [the finding log](PRIMITIVE_SELECTION_REVIEW.md). Benchmark 0.4.0 and hosted integration remain unchanged.

## Challenge and implementation handoff

The [frozen challenge specification](PRIMITIVE_SELECTION_SPEC.md) defines every scientific choice for implementation: generator distribution, seed protocol, public input/output schema, independent verification, profiles, solver settings, resource limits, ranking, and migration requirements. Its exact source is frozen at commit `4bfcd079068bdfc8035532f4b92d9743a96be1f1`; [freeze manifest](../research/primitive_selection/freeze/v2.json) SHA-256 is `a682ffe79987e22f5ee0308b5bab208278e11eb53817b86622c9145e2acd69f6`. Scientific source revision is `9ad9423f7325b73383d250eb48353c3bd816da40`, with digest `24e45c29e8abf088d5b4a0528cc9a5fb8dd87c502b451720c4c4095f95b69d26`.

Given A and t over R_q = Z_q[x]/(x^n+1), recover any bounded pair (s1,s2) satisfying A*s1+s2=t modulo q, with every coefficient in [-eta,eta]. The generator samples uniform A and independent bounded secrets/errors. This is a small synthetic feasibility challenge motivated by ML-DSA's module structure; it carries no standardized-parameter or production-hardness claim. Primary literature, official specifications, errata, and arithmetic review are linked in the finding log and specification.

| Profile | n | q | k,l | Ranked eta |
|---|---:|---:|---|---|
| small | 4 | 97 | 2,1 | 1, 2 |
| medium | 8 | 97 | 2,2 | 1, 2 |
| large | 16 | 193 | 3,2 | 1 |

Large/eta2 remains a visible stress cell. The existing ceilings (n<=32, q<=257, rank<=5), 60-second case deadline, 2-GiB memory limit, and one CPU remain fixed. Each case retains one warmup and three measured fresh subprocesses in randomized case order. Complete-worker CPU includes verification under the exact clock boundaries in the specification; it is not hardware-independent cost.

The public contract omits seeds, nonce, witness, and evaluator metadata, rejects unexpected fields, and accepts only fixed profiles. Independent verification checks all coefficient types, shapes, bounds, and ring equations. The shared research process/filesystem still assumes cooperative solver code: published development seeds cannot be treated as secret, and contestants may not reconstruct answers from evaluator files or known seeds. The migration specification requires actual evaluator/solver isolation, new versioned fingerprints and storage, the frozen reference and scoring rules, complete failure evidence, and replay tests preserving all historical 0.4.0 behavior. Production integration is subsequent implementation work.

## Evidence and decision criteria

The original 780 development records are preserved byte for byte, identifying measurement revision `b33f229338695fcccfba415245058deb772a5a8f`. Review began at `c60e1d069b97006aa22793921e9a2c5a64100edf`. The measurement archive and original report renderer have distinct recorded provenance. [Original audit](../research/primitive_selection/results/v1-audited/AUDIT.json), [corrected historical tables](../research/primitive_selection/results/v1-audited/REPORT.md), and [historical narrative](../research/primitive_selection/review/NARRATIVE-v1.md) preserve their original meanings rather than relabeling them as v2.

The repaired portfolio adds three simple comparators to the original thirteen combinations: the original subset contributes 780/1,560 development/validation records and the added comparators contribute 180/360. No cases were dropped.

| Cohort | Records | Success | No candidate | Applicability cap | Invalid answer | Mixed |
|---|---:|---:|---:|---:|---:|---:|
| v2 development | 960 | 717 | 123 | 120 | 0 | 0 |
| v2 validation | 1,920 | 1,430 | 244 | 239 | 6 | 1 |

Both strict audits regenerate inputs and independently verify every stored warmup/measured candidate and quality, as well as completeness, uniqueness, seeds, settings, provenance, revisions, aggregates, and input/output digests. The six invalid answers are rejected MSIS lattice-comparator outputs on two eta2 instances, not accepted MLWE solutions. There are no memory failures or crashes. One mixed case contains a timeout; it must not disappear behind the exclusive status counts.

The validation container was externally paused during case 368 (exhaustive MLWE, large/eta1). Its repetitions are cap/timeout/cap; recorded parent wall time is 16,596.54 seconds and includes the external pause. The [interruption record](../research/primitive_selection/results/v2-validation-20260908/external-pause-resume-20260909.json) retains the observed state and unknown pause initiator. The same run resumed without configuration or seed changes. The case receives the frozen 60-second failure penalty, as it would for its applicability cap. No rerun, favorable deletion, or scientific-gate waiver was made. This elapsed time is not measured algorithm runtime; the interruption limits wall-time comparability.

The reviewer created the [fresh nonce](../research/primitive_selection/results/v2-validation-20260908/reviewer-nonce.json) at `2026-09-08T13:00:14.881555+00:00`, after the freeze commit. The rebuilt validation container used all 20 derived seeds per profile across both eta values and all frozen tracks/solvers. [Development evidence](../research/primitive_selection/results/v2-development-20260908/REPORT.md), [held-out evidence](../research/primitive_selection/results/v2-validation-20260908/REPORT.md), and the [combined comparison](../research/primitive_selection/results/v2-final/REPORT.md) provide raw-record-derived tables. [Quantitative conclusions](../research/primitive_selection/results/v2-final/CONCLUSION.json) retain eligibility, paired gains, reduction shares, ranking, and uncertainty separately for each cohort.

| MLWE gate or observation | Development | Validation |
|---|---|---|
| Reference primal-LLL, five ranked cells | 50/50; 10/10 each cell | 100/100; 20/20 each cell |
| Distinct hybrid guess/Babai approach | 49/50 ranked | 99/100 ranked |
| Exhaustive starter | 20/20 | 40/40 |
| Large/eta1 versus pooled-small reference CPU | 56.716x | 58.056x |
| Direct modular bounded recovery, all six cells | 0/60 | 0/120 |
| Invalid MLWE answers | 0 | 0 |
| Hybrid large/eta2 stress | 8/10 | 17/20 |

Medium and large exceed exhaustive's fixed one-million-assignment cap; those caps do not demonstrate measured algorithm failure. The initial small/medium calibration failed the 2x difficulty gate (1.25x); this failed proposal is preserved in [calibration evidence](../research/primitive_selection/review/CALIBRATION.md). Adding large/eta1 before freeze produced useful separation without reducing the threshold. Both complete cohorts independently pass the revised frozen five-cell criteria.

Reference validation median CPU is approximately 0.00589 seconds on small, 0.0130–0.0134 on medium, and 0.3417 on large/eta1. Hybrid large/eta1 takes 0.3227 seconds, but its medium/eta2 failure incurs the full penalty. Exhaustive is a faster starter baseline with limited applicability. These tradeoffs leave concrete room for adaptive solver choice, bounded search, decoding improvements, and implementation work under the unchanged contract.

The tables report quality distributions as diagnostics, not a cross-track score. For example, large/eta1 reference squared-norm p10/median/p90 changes from 46/51/54.3 to 49.9/54/57.3; hybrid has the same summaries. Success intervals use seed-level Wilson intervals: even 20/20 has a 95% lower bound of 83.9%. Bootstrap intervals use 2,000 seed-level resamples, pairing eta and solver observations where appropriate; three repetitions are not three instances. Degenerate empirical bootstrap success-difference intervals on all-success cells do not prove a zero population difference. Results establish viability on these sampled distributions, not universal success or hardness.

## Rejected alternatives and frozen ranking

The planted Module-SIS generator A=[B|-Bw] fixes the last witness polynomial to one and permits direct modular answer recovery. The v1 adversarial probe recovered 56/60 immediately; bounded free-variable handling recovered all 60 v2 development cases. Its distribution is disqualified before scoring. The corrected verifier enforces both norm bounds and nonzero output; the six held-out invalid lattice answers remain failures. This finding does not disqualify every possible Module-SIS distribution.

The derived-basis BKZ objective has trivial norm-squared-two vectors on MLWE sources. BKZ also fails both retained scientific gates in development and validation: zero distinct end-to-end families have median reduction share >=70%, and there is no >=20% complete-solver gain at two sizes. Validation MLWE paired gains are -1.06%, -6.16%, and -4.34% across small/medium/large. Runtime spent reducing a basis does not establish that stronger reduction improves the complete solver; these strategy comparisons do not isolate a causal reduction-only effect.

Eligibility precedes the preserved fallback weights 30/20/15/15/10/10 and five-point MSIS tie preference. MLWE's reviewed 94/100 is a judgmental suitability assessment; excluded MSIS and BKZ cannot become eligible through points. MLWE is preferable here because it retains a valid baseline, multiple applicable approaches, meaningful measured difficulty, exact bounded verification, and failed direct-shortcut baselines within the safety caps.

There is one ranking for the five MLWE cells. Any invalid ranked answer makes a submission ineligible. All three measured repetitions must verify; otherwise the case costs 60 seconds. A success costs the median complete-worker CPU, floored at one microsecond. Divide by the same-instance frozen primal-LLL cost, take the geometric mean within each cell, and equally weight the five cell means. Lower is better. Tie groups are anchored at their lowest score and include scores within 1%; groups receive competitive ranks and display by submission ID. Stress and other tracks never enter this ranking. The specification fixes seed-cluster uncertainty and future 20-seed/profile epoch/reference lifecycle.

| Solver | Development score | Validation score (95% interval) |
|---|---:|---|
| primal-LLL reference | 1.0000 | 1.0000 [1.0000, 1.0000] |
| primal-BKZ | 0.9666 | 1.0391 [1.0304, 1.0488] |
| hybrid-BDD | 1.1379 | 1.0576 [0.9663, 1.2550] |
| exhaustive | 19.9881 | 22.5863 [22.1262, 23.0489] |
| direct-linear | 2874.6291 | 3270.4797 [3243.8384, 3296.2861] |

The change in point ordering between cohorts is retained. No solver settings were tuned on held-out outcomes.

## Reproduction and completion checks

Run from the repository root with Docker and the frozen validation image available. The final read-only reproduction command mounts current evidence into that image, strictly audits both cohorts, and compares regenerated audit, report bytes, and numeric conclusions. It projects candidates in memory only after independently verifying their complete stored content, keeping the reporting process within 2 GiB.

```sh
source .venv/bin/activate
make check
python -m research.primitive_selection.review.reproduce_v1_report

docker run --rm --cpus=1 --memory=2g --entrypoint sh \
  mldsafail-primitive-study:validation-v2 \
  -c 'python -m pytest -q tests/test_primitive*.py'

docker run --rm --cpus=1 --memory=2g --entrypoint python \
  --volume "$PWD/research/primitive_selection/results:/study/research/primitive_selection/results:ro" \
  --volume "$PWD/research/primitive_selection/review/reproduce_final_v2.py:/study/research/primitive_selection/review/reproduce_final_v2.py:ro" \
  mldsafail-primitive-study:validation-v2 \
  -m research.primitive_selection.review.reproduce_final_v2

research/primitive_selection/rebuild-check.sh /absolute/path/to/new-reproduction-directory
```

For a fresh installation, check out freeze commit `4bfcd079` in a separate worktree and build the image using `PRIMITIVE_STUDY_IMAGE=mldsafail-primitive-study:validation-v2 research/primitive_selection/primitive-study --help`; restore the committed final results and mount the reproduction reader from the final evidence checkout. The build/reproduction script records image IDs and checks exact native dependency provenance; a newly resolved OS package artifact mismatch is a failed reproduction, not permission to relax the audit. New experiment runs require a unique output directory and must never overwrite the reviewed cohorts. Reproduction timings need not match byte for byte.

Completion evidence: initial `make check` 144 tests; final `make check` 221 tests with historical score 3901; final pinned research suite 94 tests; original 780-record audit and report reproduction; complete 960/1,920 audits; separate-interpreter final report byte reproduction; and [two clean builds](../research/primitive_selection/results/v2-reproduction-20260908/reproduction.json) with identical deterministic fixtures and normalized warmup/measured outputs. Interrupted calibration and source-drift runs remain excluded and preserved. The frozen scientific files and production paths remain unchanged after freeze. The dated agent decision closes the scientific review gates; the [completion-check record](../research/primitive_selection/review/handoff-checks-20260910/CHECKS.json) records the final handoff verification.

Checkpoints: `c88a1c9` baseline archive; `bf08de8` initial findings; `9ad9423` reviewed repairs; `ba585c6` development evidence; `4bfcd079` freeze and clean builds; `cbf777a` held-out evidence and audited comparisons. All commits remain local; nothing was pushed.
