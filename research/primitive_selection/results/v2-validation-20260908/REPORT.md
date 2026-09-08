# Primitive-selection validation audited report

Generated from complete raw cohorts after input regeneration, independent candidate verification, and aggregate checks.

Success intervals for individual cells use 95% Wilson intervals; other intervals use deterministic 95% percentile bootstrap intervals (2,000 resamples) over seed-level observations. Three timing repetitions are one instance, not three. Small samples limit inference. Cross-track quality has no common score.

Successful timing uses the median measured process CPU; each process includes solver work and independent verification but excludes interpreter startup. Parent wall timing includes startup. Quality is reduced to a median per seed before summary. `n/a` means no usable observations; the outcome table supplies the reason.

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

## Study decision

This report computes descriptive evidence only. Eligibility, scientific gates, primitive selection, and agent approval must be recorded separately under the committed freeze. Neither a complete cohort nor high reduction share waives a failed gate.
