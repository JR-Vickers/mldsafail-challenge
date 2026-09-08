# Primitive-selection development audited report

Generated from complete raw cohorts after input regeneration, independent candidate verification, and aggregate checks.

Success intervals for individual cells use 95% Wilson intervals; other intervals use deterministic 95% percentile bootstrap intervals (2,000 resamples) over seed-level observations. Three timing repetitions are one instance, not three. Small samples limit inference. Cross-track quality has no common score.

Successful timing uses the median measured process CPU; each process includes solver work and independent verification but excludes interpreter startup. Parent wall timing includes startup. Quality is reduced to a median per seed before summary. `n/a` means no usable observations; the outcome table supplies the reason.

## primitive-selection-v2 / development / 20260908T015636Z-64f6da9501f3478f8edf986f965e9513

| Track/source | Solver | Profile/eta | Cases | Seed clusters | Success (95% CI) | Successful median CPU (95% CI), s | Peak RSS MiB |
|---|---|---|---:|---:|---|---|---:|
| bkz/mlwe | fixed-bkz | large/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.028917 [1.006425, 1.056531] | 182.8 |
| bkz/mlwe | fixed-bkz | large/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.059234 [0.984114, 1.715741] | 182.8 |
| bkz/mlwe | fixed-bkz | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.034545 [0.031163, 0.036149] | 182.8 |
| bkz/mlwe | fixed-bkz | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.035712 [0.034362, 0.045665] | 182.8 |
| bkz/mlwe | fixed-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007549 [0.007201, 0.010377] | 182.8 |
| bkz/mlwe | fixed-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007594 [0.007398, 0.007709] | 182.8 |
| bkz/mlwe | lll-only | large/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.943036 [0.909598, 0.988169] | 182.8 |
| bkz/mlwe | lll-only | large/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.013159 [0.964706, 1.032344] | 182.8 |
| bkz/mlwe | lll-only | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.031469 [0.030577, 0.033402] | 182.8 |
| bkz/mlwe | lll-only | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.032086 [0.031030, 0.036260] | 182.8 |
| bkz/mlwe | lll-only | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007243 [0.006603, 0.007508] | 182.8 |
| bkz/mlwe | lll-only | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007107 [0.006745, 0.007380] | 182.8 |
| bkz/mlwe | progressive-bkz | large/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.323220 [1.289778, 1.692021] | 182.8 |
| bkz/mlwe | progressive-bkz | large/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.311442 [1.247519, 2.022643] | 182.8 |
| bkz/mlwe | progressive-bkz | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.048504 [0.047222, 0.051797] | 182.8 |
| bkz/mlwe | progressive-bkz | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.050732 [0.048531, 0.095827] | 182.8 |
| bkz/mlwe | progressive-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.008907 [0.008709, 0.009325] | 182.8 |
| bkz/mlwe | progressive-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.008958 [0.008569, 0.018245] | 182.8 |
| bkz/msis | fixed-bkz | large/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.410062 [1.319812, 2.295946] | 182.8 |
| bkz/msis | fixed-bkz | large/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.403669 [1.364759, 1.508305] | 182.8 |
| bkz/msis | fixed-bkz | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.027466 [0.025001, 0.043618] | 182.8 |
| bkz/msis | fixed-bkz | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.029706 [0.028184, 0.030744] | 182.8 |
| bkz/msis | fixed-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007807 [0.007683, 0.008350] | 182.8 |
| bkz/msis | fixed-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007965 [0.007411, 0.008281] | 182.8 |
| bkz/msis | lll-only | large/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.382870 [1.292142, 2.053852] | 182.8 |
| bkz/msis | lll-only | large/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.390457 [1.251074, 1.477004] | 182.8 |
| bkz/msis | lll-only | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.026136 [0.024781, 0.045000] | 182.8 |
| bkz/msis | lll-only | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.027427 [0.026198, 0.029593] | 182.8 |
| bkz/msis | lll-only | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007438 [0.006853, 0.011171] | 182.8 |
| bkz/msis | lll-only | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007626 [0.007443, 0.007806] | 182.8 |
| bkz/msis | progressive-bkz | large/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.606986 [1.455591, 2.212110] | 182.8 |
| bkz/msis | progressive-bkz | large/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.590466 [1.550228, 1.645610] | 182.8 |
| bkz/msis | progressive-bkz | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.036577 [0.035693, 0.037464] | 182.8 |
| bkz/msis | progressive-bkz | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.038836 [0.036390, 0.039931] | 182.8 |
| bkz/msis | progressive-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.009418 [0.009017, 0.012014] | 182.8 |
| bkz/msis | progressive-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.008920 [0.008464, 0.009415] | 182.8 |
| mlwe/- | direct-linear | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| mlwe/- | direct-linear | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| mlwe/- | direct-linear | medium/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| mlwe/- | direct-linear | medium/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| mlwe/- | direct-linear | small/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| mlwe/- | direct-linear | small/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| mlwe/- | exhaustive | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| mlwe/- | exhaustive | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| mlwe/- | exhaustive | medium/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| mlwe/- | exhaustive | medium/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| mlwe/- | exhaustive | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.000200 [0.000193, 0.000212] | 182.8 |
| mlwe/- | exhaustive | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.000292 [0.000217, 0.000376] | 182.8 |
| mlwe/- | hybrid-bdd | large/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.307671 [0.294325, 0.316003] | 182.8 |
| mlwe/- | hybrid-bdd | large/2 | 10 | 10 | 80.0% [49.0%, 94.3%] | 0.347786 [0.328525, 0.606943] | 182.8 |
| mlwe/- | hybrid-bdd | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.012558 [0.012294, 0.013353] | 182.8 |
| mlwe/- | hybrid-bdd | medium/2 | 10 | 10 | 90.0% [59.6%, 98.2%] | 0.013489 [0.012673, 0.021431] | 182.8 |
| mlwe/- | hybrid-bdd | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.005789 [0.005522, 0.006041] | 182.8 |
| mlwe/- | hybrid-bdd | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007704 [0.006038, 0.012473] | 182.8 |
| mlwe/- | primal-bkz | large/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.340779 [0.334914, 0.355747] | 182.8 |
| mlwe/- | primal-bkz | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| mlwe/- | primal-bkz | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.014647 [0.013601, 0.015448] | 182.8 |
| mlwe/- | primal-bkz | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.014503 [0.013718, 0.015299] | 182.8 |
| mlwe/- | primal-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.006118 [0.006021, 0.006470] | 182.8 |
| mlwe/- | primal-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.006149 [0.005587, 0.006361] | 182.8 |
| mlwe/- | primal-lll | large/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.345085 [0.328791, 0.394905] | 182.8 |
| mlwe/- | primal-lll | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| mlwe/- | primal-lll | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.013395 [0.013001, 0.020593] | 182.8 |
| mlwe/- | primal-lll | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.013802 [0.012593, 0.024363] | 182.8 |
| mlwe/- | primal-lll | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.006066 [0.005796, 0.006187] | 182.8 |
| mlwe/- | primal-lll | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.006340 [0.005719, 0.007035] | 182.8 |
| msis/- | direct-linear | large/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007443 [0.007122, 0.008386] | 182.8 |
| msis/- | direct-linear | large/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007471 [0.007229, 0.007616] | 182.8 |
| msis/- | direct-linear | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.001541 [0.001483, 0.001612] | 182.8 |
| msis/- | direct-linear | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.001543 [0.001504, 0.001621] | 182.8 |
| msis/- | direct-linear | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.001290 [0.001263, 0.002030] | 182.8 |
| msis/- | direct-linear | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.001299 [0.001241, 0.002268] | 182.8 |
| msis/- | lll-short-vector | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| msis/- | lll-short-vector | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| msis/- | lll-short-vector | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.024530 [0.023588, 0.040483] | 182.8 |
| msis/- | lll-short-vector | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.027850 [0.026788, 0.043760] | 182.8 |
| msis/- | lll-short-vector | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007866 [0.007450, 0.010537] | 182.8 |
| msis/- | lll-short-vector | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.007705 [0.007262, 0.009512] | 182.8 |
| msis/- | progressive-bkz | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| msis/- | progressive-bkz | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| msis/- | progressive-bkz | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.035657 [0.032668, 0.052165] | 182.8 |
| msis/- | progressive-bkz | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.037697 [0.035906, 0.042991] | 182.8 |
| msis/- | progressive-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.009217 [0.008991, 0.009523] | 182.8 |
| msis/- | progressive-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.009124 [0.008423, 0.009371] | 182.8 |
| msis/- | restart-bkz | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| msis/- | restart-bkz | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| msis/- | restart-bkz | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.071890 [0.069872, 0.114310] | 182.8 |
| msis/- | restart-bkz | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.078349 [0.076899, 0.098790] | 182.8 |
| msis/- | restart-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.011869 [0.011310, 0.016896] | 182.8 |
| msis/- | restart-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.011914 [0.011721, 0.019325] | 182.8 |
| msis/- | sparse-relation | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| msis/- | sparse-relation | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| msis/- | sparse-relation | medium/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| msis/- | sparse-relation | medium/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| msis/- | sparse-relation | small/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |
| msis/- | sparse-relation | small/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 182.8 |

### Every case outcome

Applicability caps are declared omissions, not measured algorithmic failures. Signals alone are crashes, not evidence of a memory limit. A mixed case has different outcomes across repetitions; its repetitions remain in the raw record. Warmups are retained and independently checked but do not enter timing summaries.

| Track | Solver | Cases | Success | Cap | Timeout | Memory | Crash | Invalid | No candidate | Mixed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bkz | fixed-bkz | 120 | 120 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| bkz | lll-only | 120 | 120 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| bkz | progressive-bkz | 120 | 120 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlwe | direct-linear | 60 | 0 | 0 | 0 | 0 | 0 | 0 | 60 | 0 |
| mlwe | exhaustive | 60 | 20 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlwe | hybrid-bdd | 60 | 57 | 0 | 0 | 0 | 0 | 0 | 3 | 0 |
| mlwe | primal-bkz | 60 | 50 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlwe | primal-lll | 60 | 50 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| msis | direct-linear | 60 | 60 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| msis | lll-short-vector | 60 | 40 | 20 | 0 | 0 | 0 | 0 | 0 | 0 |
| msis | progressive-bkz | 60 | 40 | 20 | 0 | 0 | 0 | 0 | 0 | 0 |
| msis | restart-bkz | 60 | 40 | 20 | 0 | 0 | 0 | 0 | 0 | 0 |
| msis | sparse-relation | 60 | 0 | 0 | 0 | 0 | 0 | 0 | 60 | 0 |

Measured repetition outcomes (three per case; not independent problem instances): applicability_cap=360, no_candidate=369, success=2151.
Warmup outcomes: applicability_cap=120, no_candidate=123, success=717.

### Quality and complete-process reduction share

Reduction share divides instrumented reduction CPU by complete measured process CPU, including verification and overhead. A large share establishes runtime consumption only. It does not establish an end-to-end gain from improving reduction.

| Track/source | Solver | Profile/eta | Norm² p10/p50/p90 (median 95% CI) | RHF p10/p50/p90 (median 95% CI) | Reduction share (95% CI) |
|---|---|---|---|---|---|
| bkz/mlwe | fixed-bkz | large/1 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.746505 [74.4%, 75.4%] |
| bkz/mlwe | fixed-bkz | large/2 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.751623 [74.3%, 75.4%] |
| bkz/mlwe | fixed-bkz | medium/1 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.501536 [49.1%, 51.2%] |
| bkz/mlwe | fixed-bkz | medium/2 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.504728 [49.0%, 52.1%] |
| bkz/mlwe | fixed-bkz | small/1 | n/a n/a | 0.935677/0.935677/0.935677 [0.935677, 0.935677] | 0.087248 [7.9%, 9.4%] |
| bkz/mlwe | fixed-bkz | small/2 | n/a n/a | 0.935677/0.935677/0.935677 [0.935677, 0.935677] | 0.090378 [8.6%, 9.3%] |
| bkz/mlwe | lll-only | large/1 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.739681 [73.6%, 74.4%] |
| bkz/mlwe | lll-only | large/2 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.740886 [73.8%, 74.6%] |
| bkz/mlwe | lll-only | medium/1 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.467069 [45.4%, 47.9%] |
| bkz/mlwe | lll-only | medium/2 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.469374 [45.9%, 48.1%] |
| bkz/mlwe | lll-only | small/1 | n/a n/a | 0.935677/0.935677/0.935677 [0.935677, 0.935677] | 0.057889 [5.7%, 6.3%] |
| bkz/mlwe | lll-only | small/2 | n/a n/a | 0.935677/0.935677/0.935677 [0.935677, 0.935677] | 0.058747 [5.6%, 6.1%] |
| bkz/mlwe | progressive-bkz | large/1 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.797644 [79.0%, 80.5%] |
| bkz/mlwe | progressive-bkz | large/2 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.801657 [79.7%, 80.7%] |
| bkz/mlwe | progressive-bkz | medium/1 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.652936 [64.6%, 65.5%] |
| bkz/mlwe | progressive-bkz | medium/2 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.649025 [63.8%, 65.8%] |
| bkz/mlwe | progressive-bkz | small/1 | n/a n/a | 0.935677/0.935677/0.935677 [0.935677, 0.935677] | 0.242869 [23.9%, 24.7%] |
| bkz/mlwe | progressive-bkz | small/2 | n/a n/a | 0.935677/0.935677/0.935677 [0.935677, 0.935677] | 0.247319 [24.2%, 24.9%] |
| bkz/msis | fixed-bkz | large/1 | n/a n/a | 0.995204/1.018924/1.019913 [0.995204, 1.019732] | 0.825920 [81.8%, 83.2%] |
| bkz/msis | fixed-bkz | large/2 | n/a n/a | 1.018428/1.019055/1.019637 [1.018535, 1.019533] | 0.824782 [82.1%, 83.3%] |
| bkz/msis | fixed-bkz | medium/1 | n/a n/a | 0.983049/0.984350/0.986664 [0.983178, 0.986408] | 0.538488 [52.0%, 55.0%] |
| bkz/msis | fixed-bkz | medium/2 | n/a n/a | 0.993414/0.996977/0.999518 [0.994504, 0.998484] | 0.568523 [56.0%, 58.0%] |
| bkz/msis | fixed-bkz | small/1 | n/a n/a | 0.950033/0.954373/0.958379 [0.950033, 0.958058] | 0.131482 [12.5%, 13.6%] |
| bkz/msis | fixed-bkz | small/2 | n/a n/a | 0.972365/0.982243/0.986979 [0.976274, 0.985882] | 0.138796 [13.3%, 14.5%] |
| bkz/msis | lll-only | large/1 | n/a n/a | 1.017263/1.020885/1.021481 [1.019912, 1.021196] | 0.818227 [81.3%, 83.2%] |
| bkz/msis | lll-only | large/2 | n/a n/a | 1.019190/1.020190/1.021875 [1.019439, 1.020950] | 0.822723 [81.4%, 83.0%] |
| bkz/msis | lll-only | medium/1 | n/a n/a | 0.983049/0.984350/0.986664 [0.983178, 0.986408] | 0.515187 [50.4%, 52.6%] |
| bkz/msis | lll-only | medium/2 | n/a n/a | 0.993414/0.996977/0.999518 [0.994504, 0.998484] | 0.547565 [52.7%, 56.4%] |
| bkz/msis | lll-only | small/1 | n/a n/a | 0.950033/0.954373/0.958379 [0.950033, 0.958058] | 0.098290 [9.7%, 11.1%] |
| bkz/msis | lll-only | small/2 | n/a n/a | 0.972365/0.982243/0.986979 [0.976274, 0.985882] | 0.112584 [10.7%, 11.6%] |
| bkz/msis | progressive-bkz | large/1 | n/a n/a | 0.995189/0.995607/1.019005 [0.995204, 1.018175] | 0.854728 [84.8%, 86.4%] |
| bkz/msis | progressive-bkz | large/2 | n/a n/a | 1.018347/1.018796/1.019126 [1.018442, 1.019095] | 0.850538 [84.7%, 85.4%] |
| bkz/msis | progressive-bkz | medium/1 | n/a n/a | 0.983049/0.984350/0.986664 [0.983178, 0.986408] | 0.653214 [64.7%, 65.7%] |
| bkz/msis | progressive-bkz | medium/2 | n/a n/a | 0.993414/0.996977/0.999518 [0.994504, 0.998484] | 0.672429 [66.4%, 67.7%] |
| bkz/msis | progressive-bkz | small/1 | n/a n/a | 0.950033/0.954373/0.958379 [0.950033, 0.958058] | 0.264808 [25.5%, 27.0%] |
| bkz/msis | progressive-bkz | small/2 | n/a n/a | 0.972365/0.982243/0.986979 [0.976274, 0.985882] | 0.268764 [26.0%, 27.4%] |
| mlwe/- | direct-linear | large/1 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | direct-linear | large/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | direct-linear | medium/1 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | direct-linear | medium/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | direct-linear | small/1 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | direct-linear | small/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | exhaustive | large/1 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | exhaustive | large/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | exhaustive | medium/1 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | exhaustive | medium/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | exhaustive | small/1 | 6.7/8.0/10.1 [7.000000, 10.000000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| mlwe/- | exhaustive | small/2 | 18.9/23.0/30.4 [20.000000, 28.000000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| mlwe/- | hybrid-bdd | large/1 | 46.0/51.0/54.3 [49.000000, 52.500000] | n/a n/a | 0.971631 [97.0%, 97.3%] |
| mlwe/- | hybrid-bdd | large/2 | 139.6/152.5/174.8 [145.000000, 173.000000] | n/a n/a | 0.969214 [96.5%, 97.3%] |
| mlwe/- | hybrid-bdd | medium/1 | 15.0/22.0/24.0 [17.000000, 24.000000] | n/a n/a | 0.510244 [50.4%, 52.1%] |
| mlwe/- | hybrid-bdd | medium/2 | 55.6/63.0/68.2 [56.000000, 67.000000] | n/a n/a | 0.505386 [48.2%, 52.3%] |
| mlwe/- | hybrid-bdd | small/1 | 6.7/8.0/10.1 [7.000000, 10.000000] | n/a n/a | 0.037634 [3.5%, 3.9%] |
| mlwe/- | hybrid-bdd | small/2 | 18.9/23.0/30.4 [20.000000, 28.000000] | n/a n/a | 0.038110 [3.6%, 4.0%] |
| mlwe/- | primal-bkz | large/1 | 46.0/51.0/54.3 [49.000000, 52.500000] | n/a n/a | 0.959681 [95.8%, 96.1%] |
| mlwe/- | primal-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | primal-bkz | medium/1 | 15.0/22.0/24.0 [17.000000, 24.000000] | n/a n/a | 0.538535 [52.5%, 55.0%] |
| mlwe/- | primal-bkz | medium/2 | 55.8/63.5/69.4 [56.500000, 68.000000] | n/a n/a | 0.534215 [52.3%, 54.8%] |
| mlwe/- | primal-bkz | small/1 | 6.7/8.0/10.1 [7.000000, 10.000000] | n/a n/a | 0.045651 [4.4%, 4.8%] |
| mlwe/- | primal-bkz | small/2 | 18.9/23.0/30.4 [20.000000, 28.000000] | n/a n/a | 0.045291 [4.3%, 4.8%] |
| mlwe/- | primal-lll | large/1 | 46.0/51.0/54.3 [49.000000, 52.500000] | n/a n/a | 0.957802 [95.4%, 95.9%] |
| mlwe/- | primal-lll | large/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | primal-lll | medium/1 | 15.0/22.0/24.0 [17.000000, 24.000000] | n/a n/a | 0.509257 [49.5%, 52.6%] |
| mlwe/- | primal-lll | medium/2 | 55.8/63.5/69.4 [56.500000, 68.000000] | n/a n/a | 0.499712 [49.2%, 51.1%] |
| mlwe/- | primal-lll | small/1 | 6.7/8.0/10.1 [7.000000, 10.000000] | n/a n/a | 0.029431 [2.8%, 3.1%] |
| mlwe/- | primal-lll | small/2 | 18.9/23.0/30.4 [20.000000, 28.000000] | n/a n/a | 0.028088 [2.8%, 3.2%] |
| msis/- | direct-linear | large/1 | 30.9/31.5/37.1 [31.000000, 36.500000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| msis/- | direct-linear | large/2 | 85.6/92.0/102.1 [86.000000, 101.000000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| msis/- | direct-linear | medium/1 | 9.9/11.0/13.3 [10.000000, 13.000000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| msis/- | direct-linear | medium/2 | 23.1/30.5/37.4 [25.000000, 34.500000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| msis/- | direct-linear | small/1 | 5.0/6.0/7.1 [5.000000, 7.000000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| msis/- | direct-linear | small/2 | 12.7/19.0/23.0 [15.000000, 22.000000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| msis/- | lll-short-vector | large/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | lll-short-vector | large/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | lll-short-vector | medium/1 | 9.9/11.0/13.3 [10.000000, 13.000000] | n/a n/a | 0.546397 [52.4%, 55.5%] |
| msis/- | lll-short-vector | medium/2 | 23.1/30.5/37.4 [25.000000, 34.500000] | n/a n/a | 0.588041 [55.9%, 60.2%] |
| msis/- | lll-short-vector | small/1 | 5.0/6.0/7.1 [5.000000, 7.000000] | n/a n/a | 0.098903 [9.1%, 11.1%] |
| msis/- | lll-short-vector | small/2 | 12.7/19.0/23.0 [15.000000, 22.000000] | n/a n/a | 0.114418 [10.8%, 11.7%] |
| msis/- | progressive-bkz | large/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | progressive-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | progressive-bkz | medium/1 | 9.9/11.0/13.3 [10.000000, 13.000000] | n/a n/a | 0.677880 [66.6%, 68.1%] |
| msis/- | progressive-bkz | medium/2 | 23.1/30.5/37.4 [25.000000, 34.500000] | n/a n/a | 0.697246 [69.4%, 70.7%] |
| msis/- | progressive-bkz | small/1 | 5.0/6.0/7.1 [5.000000, 7.000000] | n/a n/a | 0.271175 [26.0%, 27.7%] |
| msis/- | progressive-bkz | small/2 | 12.7/19.0/23.0 [15.000000, 22.000000] | n/a n/a | 0.278606 [27.5%, 28.0%] |
| msis/- | restart-bkz | large/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | restart-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | restart-bkz | medium/1 | 9.9/11.0/13.3 [10.000000, 13.000000] | n/a n/a | 0.691119 [67.7%, 69.6%] |
| msis/- | restart-bkz | medium/2 | 23.1/30.5/37.4 [25.000000, 34.500000] | n/a n/a | 0.719203 [71.2%, 72.4%] |
| msis/- | restart-bkz | small/1 | 5.0/6.0/7.1 [5.000000, 7.000000] | n/a n/a | 0.260153 [24.0%, 26.8%] |
| msis/- | restart-bkz | small/2 | 12.7/19.0/23.0 [15.000000, 22.000000] | n/a n/a | 0.272917 [26.1%, 28.7%] |
| msis/- | sparse-relation | large/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | sparse-relation | large/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | sparse-relation | medium/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | sparse-relation | medium/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | sparse-relation | small/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | sparse-relation | small/2 | n/a n/a | n/a n/a | n/a n/a |

### Paired complete-solver comparisons

Positive gains mean lower complete CPU on cases solved by both methods. All eligible pair counts are shown, including unsolved pairs. Conditioning on joint success can bias timing comparisons; failure and quality columns must be considered. These strategy comparisons do not isolate a causal reduction-only change.

| Track | Comparison | Profile/eta | All pairs | Joint successes | Median CPU gain (95% CI) | Median norm² change |
|---|---|---|---:|---:|---|---:|
| mlwe | primal-bkz / primal-lll | large/1 | 10 | 10 | -2.6% [-8.4%, 4.9%] | 0.0 |
| mlwe | primal-bkz / primal-lll | large/2 | 10 | 0 | n/a n/a | n/a |
| mlwe | primal-bkz / primal-lll | medium/1 | 10 | 10 | -8.2% [-14.9%, 20.6%] | 0.0 |
| mlwe | primal-bkz / primal-lll | medium/2 | 10 | 10 | -5.5% [-20.8%, 29.6%] | 0.0 |
| mlwe | primal-bkz / primal-lll | small/1 | 10 | 10 | -2.1% [-10.9%, 0.3%] | 0.0 |
| mlwe | primal-bkz / primal-lll | small/2 | 10 | 10 | 2.7% [-9.7%, 15.8%] | 0.0 |
| msis | progressive-bkz / lll-short-vector | large/1 | 10 | 0 | n/a n/a | n/a |
| msis | progressive-bkz / lll-short-vector | large/2 | 10 | 0 | n/a n/a | n/a |
| msis | progressive-bkz / lll-short-vector | medium/1 | 10 | 10 | -46.2% [-115.3%, 4.9%] | 0.0 |
| msis | progressive-bkz / lll-short-vector | medium/2 | 10 | 10 | -38.6% [-72.6%, 3.8%] | 0.0 |
| msis | progressive-bkz / lll-short-vector | small/1 | 10 | 10 | -20.6% [-29.2%, 18.9%] | 0.0 |
| msis | progressive-bkz / lll-short-vector | small/2 | 10 | 10 | -15.3% [-21.1%, 3.3%] | 0.0 |

## Study decision

This report computes descriptive evidence only. Eligibility, scientific gates, primitive selection, and agent approval must be recorded separately under the committed freeze. Neither a complete cohort nor high reduction share waives a failed gate.
