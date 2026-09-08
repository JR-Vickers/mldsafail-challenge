# Primitive-selection development+validation audited report

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
## primitive-selection-v2 / validation / 20260908T130104Z-d9d15de1ba7b452a879ee6f8bd3391e0

| Track/source | Solver | Profile/eta | Cases | Seed clusters | Success (95% CI) | Successful median CPU (95% CI), s | Peak RSS MiB |
|---|---|---|---:|---:|---|---|---:|
| bkz/mlwe | fixed-bkz | large/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 1.027157 [1.016227, 1.039821] | 184.5 |
| bkz/mlwe | fixed-bkz | large/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 1.028483 [1.007653, 1.044889] | 184.5 |
| bkz/mlwe | fixed-bkz | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.034133 [0.033287, 0.034532] | 184.5 |
| bkz/mlwe | fixed-bkz | medium/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.033977 [0.033432, 0.034634] | 184.5 |
| bkz/mlwe | fixed-bkz | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.007333 [0.007231, 0.007417] | 184.5 |
| bkz/mlwe | fixed-bkz | small/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.007227 [0.007151, 0.007385] | 184.5 |
| bkz/mlwe | lll-only | large/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.990550 [0.976920, 0.999948] | 184.5 |
| bkz/mlwe | lll-only | large/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.972080 [0.957859, 1.011655] | 184.5 |
| bkz/mlwe | lll-only | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.032150 [0.031159, 0.032422] | 184.5 |
| bkz/mlwe | lll-only | medium/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.031828 [0.031049, 0.032736] | 184.5 |
| bkz/mlwe | lll-only | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.006982 [0.006950, 0.007118] | 184.5 |
| bkz/mlwe | lll-only | small/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.006951 [0.006912, 0.007018] | 184.5 |
| bkz/mlwe | progressive-bkz | large/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 1.291212 [1.275635, 1.308084] | 184.5 |
| bkz/mlwe | progressive-bkz | large/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 1.277031 [1.262522, 1.315547] | 184.5 |
| bkz/mlwe | progressive-bkz | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.048538 [0.048059, 0.049250] | 184.5 |
| bkz/mlwe | progressive-bkz | medium/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.048502 [0.047746, 0.049199] | 184.5 |
| bkz/mlwe | progressive-bkz | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.008858 [0.008773, 0.008959] | 184.5 |
| bkz/mlwe | progressive-bkz | small/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.008789 [0.008735, 0.008857] | 184.5 |
| bkz/msis | fixed-bkz | large/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 1.413303 [1.388788, 1.444464] | 184.5 |
| bkz/msis | fixed-bkz | large/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 1.386508 [1.328847, 1.436686] | 184.5 |
| bkz/msis | fixed-bkz | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.026853 [0.026484, 0.027594] | 184.5 |
| bkz/msis | fixed-bkz | medium/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.029254 [0.028729, 0.029928] | 184.5 |
| bkz/msis | fixed-bkz | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.007609 [0.007514, 0.007661] | 184.5 |
| bkz/msis | fixed-bkz | small/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.007665 [0.007623, 0.007778] | 184.5 |
| bkz/msis | lll-only | large/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 1.374883 [1.350980, 1.403425] | 184.5 |
| bkz/msis | lll-only | large/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 1.342906 [1.270581, 1.393279] | 184.5 |
| bkz/msis | lll-only | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.025212 [0.024797, 0.026432] | 184.5 |
| bkz/msis | lll-only | medium/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.027885 [0.027202, 0.028423] | 184.5 |
| bkz/msis | lll-only | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.007184 [0.007131, 0.007245] | 184.5 |
| bkz/msis | lll-only | small/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.007315 [0.007280, 0.007439] | 184.5 |
| bkz/msis | progressive-bkz | large/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 1.637333 [1.603079, 1.659767] | 184.5 |
| bkz/msis | progressive-bkz | large/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 1.570698 [1.519941, 1.632822] | 184.5 |
| bkz/msis | progressive-bkz | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.036107 [0.035525, 0.036639] | 184.5 |
| bkz/msis | progressive-bkz | medium/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.038176 [0.037874, 0.038822] | 184.5 |
| bkz/msis | progressive-bkz | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.008952 [0.008890, 0.009042] | 184.5 |
| bkz/msis | progressive-bkz | small/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.009059 [0.008996, 0.009254] | 184.5 |
| mlwe/- | direct-linear | large/1 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| mlwe/- | direct-linear | large/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| mlwe/- | direct-linear | medium/1 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| mlwe/- | direct-linear | medium/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| mlwe/- | direct-linear | small/1 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| mlwe/- | direct-linear | small/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| mlwe/- | exhaustive | large/1 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| mlwe/- | exhaustive | large/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| mlwe/- | exhaustive | medium/1 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| mlwe/- | exhaustive | medium/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| mlwe/- | exhaustive | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.000189 [0.000185, 0.000196] | 184.5 |
| mlwe/- | exhaustive | small/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.000308 [0.000256, 0.000341] | 184.5 |
| mlwe/- | hybrid-bdd | large/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.322658 [0.318399, 0.328436] | 184.5 |
| mlwe/- | hybrid-bdd | large/2 | 20 | 20 | 85.0% [64.0%, 94.8%] | 0.322034 [0.309470, 0.328653] | 184.5 |
| mlwe/- | hybrid-bdd | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.012568 [0.012296, 0.012793] | 184.5 |
| mlwe/- | hybrid-bdd | medium/2 | 20 | 20 | 95.0% [76.4%, 99.1%] | 0.012582 [0.012352, 0.012831] | 184.5 |
| mlwe/- | hybrid-bdd | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.005922 [0.005865, 0.005967] | 184.5 |
| mlwe/- | hybrid-bdd | small/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.005854 [0.005785, 0.005947] | 184.5 |
| mlwe/- | primal-bkz | large/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.356047 [0.348650, 0.358766] | 184.5 |
| mlwe/- | primal-bkz | large/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| mlwe/- | primal-bkz | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.014115 [0.013862, 0.014271] | 184.5 |
| mlwe/- | primal-bkz | medium/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.014076 [0.013816, 0.014393] | 184.5 |
| mlwe/- | primal-bkz | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.005976 [0.005948, 0.006030] | 184.5 |
| mlwe/- | primal-bkz | small/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.005964 [0.005907, 0.006013] | 184.5 |
| mlwe/- | primal-lll | large/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.341701 [0.332260, 0.345768] | 184.5 |
| mlwe/- | primal-lll | large/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| mlwe/- | primal-lll | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.013011 [0.012829, 0.013282] | 184.5 |
| mlwe/- | primal-lll | medium/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.013375 [0.013081, 0.013758] | 184.5 |
| mlwe/- | primal-lll | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.005890 [0.005817, 0.006027] | 184.5 |
| mlwe/- | primal-lll | small/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.005883 [0.005840, 0.005950] | 184.5 |
| msis/- | direct-linear | large/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.007392 [0.007319, 0.007525] | 184.5 |
| msis/- | direct-linear | large/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.007408 [0.007377, 0.007452] | 184.5 |
| msis/- | direct-linear | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.001549 [0.001541, 0.001554] | 184.5 |
| msis/- | direct-linear | medium/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.001541 [0.001533, 0.001561] | 184.5 |
| msis/- | direct-linear | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.001232 [0.001223, 0.001243] | 184.5 |
| msis/- | direct-linear | small/2 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.001228 [0.001223, 0.001237] | 184.5 |
| msis/- | lll-short-vector | large/1 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| msis/- | lll-short-vector | large/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| msis/- | lll-short-vector | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.024431 [0.023510, 0.025174] | 184.5 |
| msis/- | lll-short-vector | medium/2 | 20 | 20 | 95.0% [76.4%, 99.1%] | 0.026109 [0.025372, 0.027283] | 184.5 |
| msis/- | lll-short-vector | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.007339 [0.007239, 0.007385] | 184.5 |
| msis/- | lll-short-vector | small/2 | 20 | 20 | 95.0% [76.4%, 99.1%] | 0.007386 [0.007270, 0.007463] | 184.5 |
| msis/- | progressive-bkz | large/1 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| msis/- | progressive-bkz | large/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| msis/- | progressive-bkz | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.034374 [0.033834, 0.035387] | 184.5 |
| msis/- | progressive-bkz | medium/2 | 20 | 20 | 95.0% [76.4%, 99.1%] | 0.036464 [0.035932, 0.037256] | 184.5 |
| msis/- | progressive-bkz | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.008979 [0.008902, 0.009065] | 184.5 |
| msis/- | progressive-bkz | small/2 | 20 | 20 | 95.0% [76.4%, 99.1%] | 0.008967 [0.008859, 0.009094] | 184.5 |
| msis/- | restart-bkz | large/1 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| msis/- | restart-bkz | large/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| msis/- | restart-bkz | medium/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.068468 [0.067318, 0.069885] | 184.5 |
| msis/- | restart-bkz | medium/2 | 20 | 20 | 95.0% [76.4%, 99.1%] | 0.077082 [0.073794, 0.077538] | 184.5 |
| msis/- | restart-bkz | small/1 | 20 | 20 | 100.0% [83.9%, 100.0%] | 0.011439 [0.011245, 0.011594] | 184.5 |
| msis/- | restart-bkz | small/2 | 20 | 20 | 95.0% [76.4%, 99.1%] | 0.011504 [0.011250, 0.011602] | 184.5 |
| msis/- | sparse-relation | large/1 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| msis/- | sparse-relation | large/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| msis/- | sparse-relation | medium/1 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| msis/- | sparse-relation | medium/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| msis/- | sparse-relation | small/1 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |
| msis/- | sparse-relation | small/2 | 20 | 20 | 0.0% [0.0%, 16.1%] | n/a n/a | 184.5 |

### Every case outcome

Applicability caps are declared omissions, not measured algorithmic failures. Signals alone are crashes, not evidence of a memory limit. A mixed case has different outcomes across repetitions; its repetitions remain in the raw record. Warmups are retained and independently checked but do not enter timing summaries.

| Track | Solver | Cases | Success | Cap | Timeout | Memory | Crash | Invalid | No candidate | Mixed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bkz | fixed-bkz | 240 | 240 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| bkz | lll-only | 240 | 240 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| bkz | progressive-bkz | 240 | 240 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlwe | direct-linear | 120 | 0 | 0 | 0 | 0 | 0 | 0 | 120 | 0 |
| mlwe | exhaustive | 120 | 40 | 79 | 0 | 0 | 0 | 0 | 0 | 1 |
| mlwe | hybrid-bdd | 120 | 116 | 0 | 0 | 0 | 0 | 0 | 4 | 0 |
| mlwe | primal-bkz | 120 | 100 | 20 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlwe | primal-lll | 120 | 100 | 20 | 0 | 0 | 0 | 0 | 0 | 0 |
| msis | direct-linear | 120 | 120 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| msis | lll-short-vector | 120 | 78 | 40 | 0 | 0 | 0 | 2 | 0 | 0 |
| msis | progressive-bkz | 120 | 78 | 40 | 0 | 0 | 0 | 2 | 0 | 0 |
| msis | restart-bkz | 120 | 78 | 40 | 0 | 0 | 0 | 2 | 0 | 0 |
| msis | sparse-relation | 120 | 0 | 0 | 0 | 0 | 0 | 0 | 120 | 0 |

Measured repetition outcomes (three per case; not independent problem instances): applicability_cap=719, invalid_answer=18, no_candidate=732, success=4290, timeout=1.
Warmup outcomes: applicability_cap=240, invalid_answer=6, no_candidate=244, success=1430.

### Quality and complete-process reduction share

Reduction share divides instrumented reduction CPU by complete measured process CPU, including verification and overhead. A large share establishes runtime consumption only. It does not establish an end-to-end gain from improving reduction.

| Track/source | Solver | Profile/eta | Norm² p10/p50/p90 (median 95% CI) | RHF p10/p50/p90 (median 95% CI) | Reduction share (95% CI) |
|---|---|---|---|---|---|
| bkz/mlwe | fixed-bkz | large/1 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.751051 [74.6%, 75.3%] |
| bkz/mlwe | fixed-bkz | large/2 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.749809 [74.4%, 75.5%] |
| bkz/mlwe | fixed-bkz | medium/1 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.499925 [49.2%, 51.0%] |
| bkz/mlwe | fixed-bkz | medium/2 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.500303 [48.8%, 50.7%] |
| bkz/mlwe | fixed-bkz | small/1 | n/a n/a | 0.935677/0.935677/0.935677 [0.935677, 0.935677] | 0.089838 [8.7%, 9.4%] |
| bkz/mlwe | fixed-bkz | small/2 | n/a n/a | 0.935677/0.935677/0.935677 [0.935677, 0.935677] | 0.091764 [9.0%, 9.4%] |
| bkz/mlwe | lll-only | large/1 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.739286 [73.6%, 74.1%] |
| bkz/mlwe | lll-only | large/2 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.738352 [73.3%, 74.6%] |
| bkz/mlwe | lll-only | medium/1 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.465059 [45.5%, 48.0%] |
| bkz/mlwe | lll-only | medium/2 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.467321 [45.8%, 47.9%] |
| bkz/mlwe | lll-only | small/1 | n/a n/a | 0.935677/0.935677/0.935677 [0.935677, 0.935677] | 0.060622 [5.5%, 6.3%] |
| bkz/mlwe | lll-only | small/2 | n/a n/a | 0.935677/0.935677/0.935677 [0.935677, 0.935677] | 0.060779 [5.8%, 6.5%] |
| bkz/mlwe | progressive-bkz | large/1 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.801400 [79.8%, 80.3%] |
| bkz/mlwe | progressive-bkz | large/2 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.801585 [79.5%, 80.4%] |
| bkz/mlwe | progressive-bkz | medium/1 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.652320 [65.0%, 65.7%] |
| bkz/mlwe | progressive-bkz | medium/2 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.653568 [64.7%, 65.6%] |
| bkz/mlwe | progressive-bkz | small/1 | n/a n/a | 0.935677/0.935677/0.935677 [0.935677, 0.935677] | 0.246800 [24.2%, 25.0%] |
| bkz/mlwe | progressive-bkz | small/2 | n/a n/a | 0.935677/0.935677/0.935677 [0.935677, 0.935677] | 0.246953 [24.6%, 25.0%] |
| bkz/msis | fixed-bkz | large/1 | n/a n/a | 0.994892/0.995743/1.019031 [0.995413, 1.018414] | 0.833338 [82.8%, 83.7%] |
| bkz/msis | fixed-bkz | large/2 | n/a n/a | 1.018065/1.018987/1.019678 [1.018650, 1.019505] | 0.825851 [81.8%, 83.0%] |
| bkz/msis | fixed-bkz | medium/1 | n/a n/a | 0.981740/0.984350/0.987322 [0.983178, 0.985915] | 0.537955 [52.9%, 55.3%] |
| bkz/msis | fixed-bkz | medium/2 | n/a n/a | 0.993997/0.997367/0.999548 [0.996132, 0.998334] | 0.568016 [56.6%, 57.6%] |
| bkz/msis | fixed-bkz | small/1 | n/a n/a | 0.950033/0.956216/0.961262 [0.954373, 0.958058] | 0.133620 [12.8%, 13.9%] |
| bkz/msis | fixed-bkz | small/2 | n/a n/a | 0.968461/0.980912/0.986979 [0.975646, 0.983536] | 0.137357 [13.4%, 14.3%] |
| bkz/msis | lll-only | large/1 | n/a n/a | 1.016229/1.020290/1.021655 [1.019585, 1.020587] | 0.823866 [82.1%, 82.8%] |
| bkz/msis | lll-only | large/2 | n/a n/a | 1.019624/1.020316/1.021266 [1.020147, 1.020440] | 0.818593 [81.3%, 82.5%] |
| bkz/msis | lll-only | medium/1 | n/a n/a | 0.981740/0.984350/0.987322 [0.983178, 0.985915] | 0.508297 [50.1%, 52.3%] |
| bkz/msis | lll-only | medium/2 | n/a n/a | 0.993997/0.997367/0.999548 [0.996132, 0.998334] | 0.546109 [53.8%, 55.8%] |
| bkz/msis | lll-only | small/1 | n/a n/a | 0.950033/0.956216/0.961262 [0.954373, 0.958058] | 0.102622 [9.9%, 10.7%] |
| bkz/msis | lll-only | small/2 | n/a n/a | 0.968461/0.980912/0.986979 [0.975646, 0.983536] | 0.108671 [10.5%, 11.4%] |
| bkz/msis | progressive-bkz | large/1 | n/a n/a | 0.994892/0.995929/1.018890 [0.995345, 1.007286] | 0.857375 [85.3%, 86.4%] |
| bkz/msis | progressive-bkz | large/2 | n/a n/a | 1.017734/1.018509/1.019245 [1.018047, 1.018653] | 0.846995 [84.3%, 85.3%] |
| bkz/msis | progressive-bkz | medium/1 | n/a n/a | 0.981740/0.984350/0.987322 [0.983178, 0.985915] | 0.649786 [64.3%, 65.9%] |
| bkz/msis | progressive-bkz | medium/2 | n/a n/a | 0.993997/0.997367/0.999548 [0.996132, 0.998334] | 0.668706 [66.6%, 67.3%] |
| bkz/msis | progressive-bkz | small/1 | n/a n/a | 0.950033/0.956216/0.961262 [0.954373, 0.958058] | 0.265778 [26.4%, 27.2%] |
| bkz/msis | progressive-bkz | small/2 | n/a n/a | 0.968461/0.980912/0.986979 [0.975646, 0.983536] | 0.270656 [26.8%, 27.5%] |
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
| mlwe/- | exhaustive | small/1 | 6.0/7.0/9.0 [7.000000, 8.000000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| mlwe/- | exhaustive | small/2 | 16.9/25.5/33.2 [20.000000, 30.000000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| mlwe/- | hybrid-bdd | large/1 | 49.9/54.0/57.3 [52.000000, 55.500000] | n/a n/a | 0.971418 [97.1%, 97.3%] |
| mlwe/- | hybrid-bdd | large/2 | 144.0/155.0/171.4 [148.000000, 162.000000] | n/a n/a | 0.968863 [96.7%, 97.3%] |
| mlwe/- | hybrid-bdd | medium/1 | 18.9/21.0/23.2 [20.000000, 21.500000] | n/a n/a | 0.511946 [50.6%, 52.1%] |
| mlwe/- | hybrid-bdd | medium/2 | 50.0/66.0/78.6 [60.000000, 72.000000] | n/a n/a | 0.505584 [49.7%, 51.1%] |
| mlwe/- | hybrid-bdd | small/1 | 6.0/7.0/9.0 [7.000000, 8.000000] | n/a n/a | 0.038790 [3.7%, 4.0%] |
| mlwe/- | hybrid-bdd | small/2 | 16.9/25.5/33.2 [20.000000, 30.000000] | n/a n/a | 0.039774 [3.9%, 4.1%] |
| mlwe/- | primal-bkz | large/1 | 49.9/54.0/57.3 [52.000000, 55.500000] | n/a n/a | 0.959888 [95.9%, 96.1%] |
| mlwe/- | primal-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | primal-bkz | medium/1 | 18.9/21.0/23.2 [20.000000, 21.500000] | n/a n/a | 0.546904 [53.5%, 55.0%] |
| mlwe/- | primal-bkz | medium/2 | 50.0/66.0/78.3 [58.000000, 71.500000] | n/a n/a | 0.544152 [53.4%, 55.1%] |
| mlwe/- | primal-bkz | small/1 | 6.0/7.0/9.0 [7.000000, 8.000000] | n/a n/a | 0.047197 [4.5%, 4.9%] |
| mlwe/- | primal-bkz | small/2 | 16.9/25.5/33.2 [20.000000, 30.000000] | n/a n/a | 0.048254 [4.6%, 5.0%] |
| mlwe/- | primal-lll | large/1 | 49.9/54.0/57.3 [52.000000, 55.500000] | n/a n/a | 0.958056 [95.7%, 95.9%] |
| mlwe/- | primal-lll | large/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | primal-lll | medium/1 | 18.9/21.0/23.2 [20.000000, 21.500000] | n/a n/a | 0.509177 [49.4%, 52.0%] |
| mlwe/- | primal-lll | medium/2 | 50.0/66.0/78.3 [58.000000, 71.500000] | n/a n/a | 0.507568 [49.3%, 51.6%] |
| mlwe/- | primal-lll | small/1 | 6.0/7.0/9.0 [7.000000, 8.000000] | n/a n/a | 0.030968 [3.0%, 3.2%] |
| mlwe/- | primal-lll | small/2 | 16.9/25.5/33.2 [20.000000, 30.000000] | n/a n/a | 0.030239 [3.0%, 3.2%] |
| msis/- | direct-linear | large/1 | 28.9/34.0/37.0 [32.000000, 36.000000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| msis/- | direct-linear | large/2 | 80.0/98.0/110.1 [85.500000, 103.500000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| msis/- | direct-linear | medium/1 | 8.9/11.0/14.0 [10.000000, 12.500000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| msis/- | direct-linear | medium/2 | 24.0/31.5/37.5 [29.000000, 34.000000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| msis/- | direct-linear | small/1 | 5.0/6.5/8.0 [6.000000, 7.000000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| msis/- | direct-linear | small/2 | 10.8/18.0/23.0 [14.500000, 20.000000] | n/a n/a | 0.000000 [0.0%, 0.0%] |
| msis/- | lll-short-vector | large/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | lll-short-vector | large/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | lll-short-vector | medium/1 | 8.9/11.0/14.0 [10.000000, 12.500000] | n/a n/a | 0.544796 [53.4%, 56.1%] |
| msis/- | lll-short-vector | medium/2 | 24.0/33.0/38.0 [29.000000, 34.000000] | n/a n/a | 0.584935 [57.7%, 59.8%] |
| msis/- | lll-short-vector | small/1 | 5.0/6.5/8.0 [6.000000, 7.000000] | n/a n/a | 0.101539 [9.7%, 10.7%] |
| msis/- | lll-short-vector | small/2 | 10.6/17.0/23.0 [14.000000, 20.000000] | n/a n/a | 0.109816 [10.4%, 11.2%] |
| msis/- | progressive-bkz | large/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | progressive-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | progressive-bkz | medium/1 | 8.9/11.0/14.0 [10.000000, 12.500000] | n/a n/a | 0.682053 [67.5%, 68.9%] |
| msis/- | progressive-bkz | medium/2 | 24.0/33.0/38.0 [29.000000, 34.000000] | n/a n/a | 0.699997 [69.7%, 70.7%] |
| msis/- | progressive-bkz | small/1 | 5.0/6.5/8.0 [6.000000, 7.000000] | n/a n/a | 0.273469 [26.9%, 27.9%] |
| msis/- | progressive-bkz | small/2 | 10.6/17.0/23.0 [14.000000, 20.000000] | n/a n/a | 0.281356 [27.7%, 28.5%] |
| msis/- | restart-bkz | large/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | restart-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | restart-bkz | medium/1 | 8.9/11.0/14.0 [10.000000, 12.500000] | n/a n/a | 0.690112 [68.5%, 69.7%] |
| msis/- | restart-bkz | medium/2 | 24.0/33.0/38.0 [29.000000, 34.000000] | n/a n/a | 0.723533 [71.2%, 72.7%] |
| msis/- | restart-bkz | small/1 | 5.0/6.5/8.0 [6.000000, 7.000000] | n/a n/a | 0.255535 [25.2%, 26.7%] |
| msis/- | restart-bkz | small/2 | 10.6/17.0/23.0 [14.000000, 20.000000] | n/a n/a | 0.269946 [26.7%, 27.7%] |
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
| mlwe | primal-bkz / primal-lll | large/1 | 20 | 20 | -4.3% [-4.7%, -3.7%] | 0.0 |
| mlwe | primal-bkz / primal-lll | large/2 | 20 | 0 | n/a n/a | n/a |
| mlwe | primal-bkz / primal-lll | medium/1 | 20 | 20 | -7.8% [-9.4%, -6.3%] | 0.0 |
| mlwe | primal-bkz / primal-lll | medium/2 | 20 | 20 | -4.9% [-8.2%, -3.4%] | 0.0 |
| mlwe | primal-bkz / primal-lll | small/1 | 20 | 20 | -0.9% [-2.4%, -0.1%] | 0.0 |
| mlwe | primal-bkz / primal-lll | small/2 | 20 | 20 | -1.5% [-3.8%, 0.8%] | 0.0 |
| msis | progressive-bkz / lll-short-vector | large/1 | 20 | 0 | n/a n/a | n/a |
| msis | progressive-bkz / lll-short-vector | large/2 | 20 | 0 | n/a n/a | n/a |
| msis | progressive-bkz / lll-short-vector | medium/1 | 20 | 20 | -42.1% [-43.9%, -40.2%] | 0.0 |
| msis | progressive-bkz / lll-short-vector | medium/2 | 20 | 19 | -40.2% [-42.3%, -37.9%] | 0.0 |
| msis | progressive-bkz / lll-short-vector | small/1 | 20 | 20 | -23.5% [-24.0%, -21.2%] | 0.0 |
| msis | progressive-bkz / lll-short-vector | small/2 | 20 | 19 | -21.2% [-22.5%, -19.8%] | 0.0 |

## Development versus held-out validation

Cells are compared within the same study version. Success difference is validation minus development, with a two-sample seed bootstrap interval; it is not a paired-seed estimate. The preceding tables retain timing, quality, reduction-share, and failure distributions separately for each cohort.

| Version | Track/source | Solver | Profile/eta | Development n | Validation n | Success difference (95% CI) | Successful CPU ratio validation/development |
|---|---|---|---|---:|---:|---|---:|
| primitive-selection-v2 | bkz/mlwe | fixed-bkz | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9983 |
| primitive-selection-v2 | bkz/mlwe | fixed-bkz | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9710 |
| primitive-selection-v2 | bkz/mlwe | fixed-bkz | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9881 |
| primitive-selection-v2 | bkz/mlwe | fixed-bkz | medium/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9514 |
| primitive-selection-v2 | bkz/mlwe | fixed-bkz | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9713 |
| primitive-selection-v2 | bkz/mlwe | fixed-bkz | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9516 |
| primitive-selection-v2 | bkz/mlwe | lll-only | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0504 |
| primitive-selection-v2 | bkz/mlwe | lll-only | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9595 |
| primitive-selection-v2 | bkz/mlwe | lll-only | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0217 |
| primitive-selection-v2 | bkz/mlwe | lll-only | medium/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9920 |
| primitive-selection-v2 | bkz/mlwe | lll-only | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9639 |
| primitive-selection-v2 | bkz/mlwe | lll-only | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9780 |
| primitive-selection-v2 | bkz/mlwe | progressive-bkz | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9758 |
| primitive-selection-v2 | bkz/mlwe | progressive-bkz | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9738 |
| primitive-selection-v2 | bkz/mlwe | progressive-bkz | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0007 |
| primitive-selection-v2 | bkz/mlwe | progressive-bkz | medium/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9560 |
| primitive-selection-v2 | bkz/mlwe | progressive-bkz | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9945 |
| primitive-selection-v2 | bkz/mlwe | progressive-bkz | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9811 |
| primitive-selection-v2 | bkz/msis | fixed-bkz | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0023 |
| primitive-selection-v2 | bkz/msis | fixed-bkz | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9878 |
| primitive-selection-v2 | bkz/msis | fixed-bkz | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9777 |
| primitive-selection-v2 | bkz/msis | fixed-bkz | medium/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9848 |
| primitive-selection-v2 | bkz/msis | fixed-bkz | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9746 |
| primitive-selection-v2 | bkz/msis | fixed-bkz | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9624 |
| primitive-selection-v2 | bkz/msis | lll-only | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9942 |
| primitive-selection-v2 | bkz/msis | lll-only | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9658 |
| primitive-selection-v2 | bkz/msis | lll-only | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9647 |
| primitive-selection-v2 | bkz/msis | lll-only | medium/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0167 |
| primitive-selection-v2 | bkz/msis | lll-only | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9659 |
| primitive-selection-v2 | bkz/msis | lll-only | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9591 |
| primitive-selection-v2 | bkz/msis | progressive-bkz | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0189 |
| primitive-selection-v2 | bkz/msis | progressive-bkz | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9876 |
| primitive-selection-v2 | bkz/msis | progressive-bkz | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9871 |
| primitive-selection-v2 | bkz/msis | progressive-bkz | medium/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9830 |
| primitive-selection-v2 | bkz/msis | progressive-bkz | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9505 |
| primitive-selection-v2 | bkz/msis | progressive-bkz | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0156 |
| primitive-selection-v2 | mlwe/- | direct-linear | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | mlwe/- | direct-linear | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | mlwe/- | direct-linear | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | mlwe/- | direct-linear | medium/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | mlwe/- | direct-linear | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | mlwe/- | direct-linear | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | mlwe/- | exhaustive | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | mlwe/- | exhaustive | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | mlwe/- | exhaustive | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | mlwe/- | exhaustive | medium/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | mlwe/- | exhaustive | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9459 |
| primitive-selection-v2 | mlwe/- | exhaustive | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0545 |
| primitive-selection-v2 | mlwe/- | hybrid-bdd | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0487 |
| primitive-selection-v2 | mlwe/- | hybrid-bdd | large/2 | 10 | 20 | 5.0% [-25.0%, 40.0%] | 0.9260 |
| primitive-selection-v2 | mlwe/- | hybrid-bdd | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0007 |
| primitive-selection-v2 | mlwe/- | hybrid-bdd | medium/2 | 10 | 20 | 5.0% [-15.0%, 30.0%] | 0.9327 |
| primitive-selection-v2 | mlwe/- | hybrid-bdd | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0230 |
| primitive-selection-v2 | mlwe/- | hybrid-bdd | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.7598 |
| primitive-selection-v2 | mlwe/- | primal-bkz | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0448 |
| primitive-selection-v2 | mlwe/- | primal-bkz | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | mlwe/- | primal-bkz | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9637 |
| primitive-selection-v2 | mlwe/- | primal-bkz | medium/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9705 |
| primitive-selection-v2 | mlwe/- | primal-bkz | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9769 |
| primitive-selection-v2 | mlwe/- | primal-bkz | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9699 |
| primitive-selection-v2 | mlwe/- | primal-lll | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9902 |
| primitive-selection-v2 | mlwe/- | primal-lll | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | mlwe/- | primal-lll | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9713 |
| primitive-selection-v2 | mlwe/- | primal-lll | medium/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9691 |
| primitive-selection-v2 | mlwe/- | primal-lll | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9711 |
| primitive-selection-v2 | mlwe/- | primal-lll | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9280 |
| primitive-selection-v2 | msis/- | direct-linear | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9932 |
| primitive-selection-v2 | msis/- | direct-linear | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9915 |
| primitive-selection-v2 | msis/- | direct-linear | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 1.0056 |
| primitive-selection-v2 | msis/- | direct-linear | medium/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9986 |
| primitive-selection-v2 | msis/- | direct-linear | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9545 |
| primitive-selection-v2 | msis/- | direct-linear | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9452 |
| primitive-selection-v2 | msis/- | lll-short-vector | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | msis/- | lll-short-vector | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | msis/- | lll-short-vector | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9960 |
| primitive-selection-v2 | msis/- | lll-short-vector | medium/2 | 10 | 20 | -5.0% [-15.0%, 0.0%] | 0.9375 |
| primitive-selection-v2 | msis/- | lll-short-vector | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9330 |
| primitive-selection-v2 | msis/- | lll-short-vector | small/2 | 10 | 20 | -5.0% [-15.0%, 0.0%] | 0.9586 |
| primitive-selection-v2 | msis/- | progressive-bkz | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | msis/- | progressive-bkz | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | msis/- | progressive-bkz | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9640 |
| primitive-selection-v2 | msis/- | progressive-bkz | medium/2 | 10 | 20 | -5.0% [-15.0%, 0.0%] | 0.9673 |
| primitive-selection-v2 | msis/- | progressive-bkz | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9742 |
| primitive-selection-v2 | msis/- | progressive-bkz | small/2 | 10 | 20 | -5.0% [-15.0%, 0.0%] | 0.9827 |
| primitive-selection-v2 | msis/- | restart-bkz | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | msis/- | restart-bkz | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | msis/- | restart-bkz | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9524 |
| primitive-selection-v2 | msis/- | restart-bkz | medium/2 | 10 | 20 | -5.0% [-15.0%, 0.0%] | 0.9838 |
| primitive-selection-v2 | msis/- | restart-bkz | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | 0.9637 |
| primitive-selection-v2 | msis/- | restart-bkz | small/2 | 10 | 20 | -5.0% [-15.0%, 0.0%] | 0.9656 |
| primitive-selection-v2 | msis/- | sparse-relation | large/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | msis/- | sparse-relation | large/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | msis/- | sparse-relation | medium/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | msis/- | sparse-relation | medium/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | msis/- | sparse-relation | small/1 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |
| primitive-selection-v2 | msis/- | sparse-relation | small/2 | 10 | 20 | 0.0% [0.0%, 0.0%] | n/a |

## Study decision

This report computes descriptive evidence only. Eligibility, scientific gates, primitive selection, and agent approval must be recorded separately under the committed freeze. Neither a complete cohort nor high reduction share waives a failed gate.
