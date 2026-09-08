# Primitive-selection development audited report

Generated from complete raw cohorts after input regeneration, independent candidate verification, and aggregate checks.

Success intervals for individual cells use 95% Wilson intervals; other intervals use deterministic 95% percentile bootstrap intervals (2,000 resamples) over seed-level observations. Three timing repetitions are one instance, not three. Small samples limit inference. Cross-track quality has no common score.

Successful timing uses the median measured process CPU; each process includes solver work and independent verification but excludes interpreter startup. Parent wall timing includes startup. Quality is reduced to a median per seed before summary. `n/a` means no usable observations; the outcome table supplies the reason.

## primitive-selection-v1 / development / legacy

| Track/source | Solver | Profile/eta | Cases | Seed clusters | Success (95% CI) | Successful median CPU (95% CI), s | Peak RSS MiB |
|---|---|---|---:|---:|---|---|---:|
| bkz/mlwe | fixed-bkz | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 209.8 |
| bkz/mlwe | fixed-bkz | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 199.7 |
| bkz/mlwe | fixed-bkz | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.990260 [0.972061, 1.023470] | 192.2 |
| bkz/mlwe | fixed-bkz | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.988673 [0.984103, 1.029844] | 172.0 |
| bkz/mlwe | fixed-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.033234 [0.032262, 0.034084] | 180.8 |
| bkz/mlwe | fixed-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.033695 [0.032806, 0.034025] | 198.7 |
| bkz/mlwe | lll-only | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 204.2 |
| bkz/mlwe | lll-only | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 211.2 |
| bkz/mlwe | lll-only | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.953474 [0.933911, 0.987112] | 162.7 |
| bkz/mlwe | lll-only | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.952816 [0.934957, 0.976837] | 202.9 |
| bkz/mlwe | lll-only | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.030737 [0.030284, 0.031997] | 197.7 |
| bkz/mlwe | lll-only | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.031383 [0.030972, 0.031806] | 189.3 |
| bkz/mlwe | progressive-bkz | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 184.6 |
| bkz/mlwe | progressive-bkz | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 183.4 |
| bkz/mlwe | progressive-bkz | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.255595 [1.234409, 1.287504] | 201.6 |
| bkz/mlwe | progressive-bkz | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.269160 [1.242763, 1.287030] | 187.6 |
| bkz/mlwe | progressive-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.048287 [0.047247, 0.048907] | 198.9 |
| bkz/mlwe | progressive-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.048057 [0.047488, 0.049598] | 192.8 |
| bkz/msis | fixed-bkz | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 190.3 |
| bkz/msis | fixed-bkz | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 196.7 |
| bkz/msis | fixed-bkz | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.370157 [1.299705, 1.448781] | 207.2 |
| bkz/msis | fixed-bkz | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.388755 [1.355656, 1.427385] | 198.2 |
| bkz/msis | fixed-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.026988 [0.026079, 0.027536] | 210.6 |
| bkz/msis | fixed-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.029205 [0.028739, 0.029697] | 186.1 |
| bkz/msis | lll-only | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 198.6 |
| bkz/msis | lll-only | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 178.6 |
| bkz/msis | lll-only | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.315825 [1.260929, 1.386467] | 205.7 |
| bkz/msis | lll-only | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.344579 [1.326799, 1.385576] | 210.3 |
| bkz/msis | lll-only | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.025139 [0.024245, 0.026202] | 204.9 |
| bkz/msis | lll-only | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.027806 [0.027400, 0.028555] | 206.3 |
| bkz/msis | progressive-bkz | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 188.4 |
| bkz/msis | progressive-bkz | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 188.2 |
| bkz/msis | progressive-bkz | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.573634 [1.515466, 1.643512] | 208.4 |
| bkz/msis | progressive-bkz | medium/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 1.607140 [1.579437, 1.640010] | 204.7 |
| bkz/msis | progressive-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.036057 [0.034484, 0.036411] | 198.8 |
| bkz/msis | progressive-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.038114 [0.037520, 0.038739] | 178.4 |
| mlwe/- | exhaustive | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 206.2 |
| mlwe/- | exhaustive | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 195.2 |
| mlwe/- | exhaustive | medium/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 184.7 |
| mlwe/- | exhaustive | medium/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 154.4 |
| mlwe/- | exhaustive | small/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 198.4 |
| mlwe/- | exhaustive | small/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 198.4 |
| mlwe/- | hybrid-bdd | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 199.7 |
| mlwe/- | hybrid-bdd | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 167.5 |
| mlwe/- | hybrid-bdd | medium/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 198.7 |
| mlwe/- | hybrid-bdd | medium/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 195.2 |
| mlwe/- | hybrid-bdd | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.024215 [0.012805, 0.028866] | 192.9 |
| mlwe/- | hybrid-bdd | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.023758 [0.013529, 0.032304] | 198.4 |
| mlwe/- | primal-bkz | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 202.1 |
| mlwe/- | primal-bkz | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 196.8 |
| mlwe/- | primal-bkz | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.348048 [0.334188, 0.359224] | 204.2 |
| mlwe/- | primal-bkz | medium/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 161.6 |
| mlwe/- | primal-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.014080 [0.013708, 0.014443] | 184.7 |
| mlwe/- | primal-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.013982 [0.013740, 0.014338] | 199.7 |
| mlwe/- | primal-lll | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 178.6 |
| mlwe/- | primal-lll | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 190.1 |
| mlwe/- | primal-lll | medium/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.334751 [0.325579, 0.347263] | 195.2 |
| mlwe/- | primal-lll | medium/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 197.8 |
| mlwe/- | primal-lll | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.013068 [0.012445, 0.013495] | 191.7 |
| mlwe/- | primal-lll | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.013491 [0.013073, 0.013658] | 180.8 |
| msis/- | lll-short-vector | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 167.5 |
| msis/- | lll-short-vector | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 181.9 |
| msis/- | lll-short-vector | medium/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 199.7 |
| msis/- | lll-short-vector | medium/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 199.7 |
| msis/- | lll-short-vector | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.023937 [0.023515, 0.024727] | 199.7 |
| msis/- | lll-short-vector | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.026045 [0.025596, 0.026600] | 198.7 |
| msis/- | progressive-bkz | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 199.7 |
| msis/- | progressive-bkz | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 207.7 |
| msis/- | progressive-bkz | medium/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 178.1 |
| msis/- | progressive-bkz | medium/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 197.8 |
| msis/- | progressive-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.034470 [0.033847, 0.034980] | 202.1 |
| msis/- | progressive-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.036415 [0.035955, 0.036979] | 195.2 |
| msis/- | restart-bkz | large/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 185.9 |
| msis/- | restart-bkz | large/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 210.6 |
| msis/- | restart-bkz | medium/1 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 206.2 |
| msis/- | restart-bkz | medium/2 | 10 | 10 | 0.0% [0.0%, 27.8%] | n/a n/a | 186.6 |
| msis/- | restart-bkz | small/1 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.068853 [0.067310, 0.070086] | 200.4 |
| msis/- | restart-bkz | small/2 | 10 | 10 | 100.0% [72.2%, 100.0%] | 0.075225 [0.073556, 0.077626] | 167.5 |

### Every case outcome

Applicability caps are declared omissions, not measured algorithmic failures. Signals alone are crashes, not evidence of a memory limit. A mixed case has different outcomes across repetitions; its repetitions remain in the raw record. Warmups are retained and independently checked but do not enter timing summaries.

| Track | Solver | Cases | Success | Cap | Timeout | Memory | Crash | Invalid | No candidate | Mixed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bkz | fixed-bkz | 120 | 80 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| bkz | lll-only | 120 | 80 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| bkz | progressive-bkz | 120 | 80 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlwe | exhaustive | 60 | 0 | 60 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlwe | hybrid-bdd | 60 | 20 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlwe | primal-bkz | 60 | 30 | 30 | 0 | 0 | 0 | 0 | 0 | 0 |
| mlwe | primal-lll | 60 | 30 | 30 | 0 | 0 | 0 | 0 | 0 | 0 |
| msis | lll-short-vector | 60 | 20 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| msis | progressive-bkz | 60 | 20 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| msis | restart-bkz | 60 | 20 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |

Measured repetition outcomes (three per case; not independent problem instances): applicability_cap=1200, success=1140.
Warmup outcomes: not retained in the historical v1 cohort.

### Quality and complete-process reduction share

Reduction share divides instrumented reduction CPU by complete measured process CPU, including verification and overhead. A large share establishes runtime consumption only. It does not establish an end-to-end gain from improving reduction.

| Track/source | Solver | Profile/eta | Norm² p10/p50/p90 (median 95% CI) | RHF p10/p50/p90 (median 95% CI) | Reduction share (95% CI) |
|---|---|---|---|---|---|
| bkz/mlwe | fixed-bkz | large/1 | n/a n/a | n/a n/a | n/a n/a |
| bkz/mlwe | fixed-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| bkz/mlwe | fixed-bkz | medium/1 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.743359 [73.7%, 75.0%] |
| bkz/mlwe | fixed-bkz | medium/2 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.744381 [73.7%, 74.9%] |
| bkz/mlwe | fixed-bkz | small/1 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.495901 [48.1%, 50.8%] |
| bkz/mlwe | fixed-bkz | small/2 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.502009 [49.1%, 51.1%] |
| bkz/mlwe | lll-only | large/1 | n/a n/a | n/a n/a | n/a n/a |
| bkz/mlwe | lll-only | large/2 | n/a n/a | n/a n/a | n/a n/a |
| bkz/mlwe | lll-only | medium/1 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.735678 [73.1%, 74.1%] |
| bkz/mlwe | lll-only | medium/2 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.731727 [72.5%, 73.8%] |
| bkz/mlwe | lll-only | small/1 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.459367 [44.5%, 47.6%] |
| bkz/mlwe | lll-only | small/2 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.462845 [44.8%, 47.7%] |
| bkz/mlwe | progressive-bkz | large/1 | n/a n/a | n/a n/a | n/a n/a |
| bkz/mlwe | progressive-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| bkz/mlwe | progressive-bkz | medium/1 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.795973 [79.2%, 80.0%] |
| bkz/mlwe | progressive-bkz | medium/2 | n/a n/a | 0.987584/0.987584/0.987584 [0.987584, 0.987584] | 0.795829 [79.2%, 80.1%] |
| bkz/mlwe | progressive-bkz | small/1 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.652482 [64.3%, 65.8%] |
| bkz/mlwe | progressive-bkz | small/2 | n/a n/a | 0.976860/0.976860/0.976860 [0.976860, 0.976860] | 0.651659 [64.8%, 65.9%] |
| bkz/msis | fixed-bkz | large/1 | n/a n/a | n/a n/a | n/a n/a |
| bkz/msis | fixed-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| bkz/msis | fixed-bkz | medium/1 | n/a n/a | 0.994702/0.995656/1.019945 [0.994905, 1.019316] | 0.833815 [81.9%, 84.4%] |
| bkz/msis | fixed-bkz | medium/2 | n/a n/a | 1.017788/1.018608/1.019806 [1.018165, 1.019394] | 0.825507 [82.3%, 83.0%] |
| bkz/msis | fixed-bkz | small/1 | n/a n/a | 0.981166/0.985422/0.986585 [0.983117, 0.986408] | 0.544967 [53.6%, 55.1%] |
| bkz/msis | fixed-bkz | small/2 | n/a n/a | 0.993871/0.997939/1.000254 [0.995461, 0.999390] | 0.572301 [56.6%, 57.6%] |
| bkz/msis | lll-only | large/1 | n/a n/a | n/a n/a | n/a n/a |
| bkz/msis | lll-only | large/2 | n/a n/a | n/a n/a | n/a n/a |
| bkz/msis | lll-only | medium/1 | n/a n/a | 0.996738/1.020173/1.021482 [1.008382, 1.021446] | 0.818307 [81.1%, 82.6%] |
| bkz/msis | lll-only | medium/2 | n/a n/a | 1.019245/1.019992/1.021373 [1.019295, 1.020773] | 0.821491 [82.0%, 82.6%] |
| bkz/msis | lll-only | small/1 | n/a n/a | 0.981166/0.985422/0.986585 [0.983117, 0.986408] | 0.510438 [50.0%, 52.6%] |
| bkz/msis | lll-only | small/2 | n/a n/a | 0.993871/0.997939/1.000254 [0.995461, 0.999390] | 0.546069 [54.5%, 55.0%] |
| bkz/msis | progressive-bkz | large/1 | n/a n/a | n/a n/a | n/a n/a |
| bkz/msis | progressive-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| bkz/msis | progressive-bkz | medium/1 | n/a n/a | 0.994702/0.995409/1.019150 [0.994905, 1.018299] | 0.861127 [84.5%, 86.9%] |
| bkz/msis | progressive-bkz | medium/2 | n/a n/a | 1.018120/1.018534/1.019067 [1.018321, 1.018941] | 0.849997 [84.7%, 85.4%] |
| bkz/msis | progressive-bkz | small/1 | n/a n/a | 0.981166/0.985422/0.986585 [0.983117, 0.986408] | 0.658808 [65.2%, 66.2%] |
| bkz/msis | progressive-bkz | small/2 | n/a n/a | 0.993871/0.997939/1.000254 [0.995461, 0.999390] | 0.672840 [67.1%, 67.4%] |
| mlwe/- | exhaustive | large/1 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | exhaustive | large/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | exhaustive | medium/1 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | exhaustive | medium/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | exhaustive | small/1 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | exhaustive | small/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | hybrid-bdd | large/1 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | hybrid-bdd | large/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | hybrid-bdd | medium/1 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | hybrid-bdd | medium/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | hybrid-bdd | small/1 | 17.9/21.0/23.2 [19.000000, 23.000000] | n/a n/a | 0.626863 [50.3%, 65.5%] |
| mlwe/- | hybrid-bdd | small/2 | 53.8/63.0/74.7 [58.500000, 71.500000] | n/a n/a | 0.628364 [51.8%, 67.7%] |
| mlwe/- | primal-bkz | large/1 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | primal-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | primal-bkz | medium/1 | 48.8/52.0/58.5 [50.500000, 55.500000] | n/a n/a | 0.959857 [95.8%, 96.1%] |
| mlwe/- | primal-bkz | medium/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | primal-bkz | small/1 | 17.9/21.0/23.2 [19.000000, 23.000000] | n/a n/a | 0.540092 [53.0%, 54.9%] |
| mlwe/- | primal-bkz | small/2 | 53.8/63.0/74.7 [58.500000, 71.500000] | n/a n/a | 0.539990 [52.4%, 55.3%] |
| mlwe/- | primal-lll | large/1 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | primal-lll | large/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | primal-lll | medium/1 | 48.8/52.0/58.5 [50.500000, 55.500000] | n/a n/a | 0.957756 [95.7%, 95.9%] |
| mlwe/- | primal-lll | medium/2 | n/a n/a | n/a n/a | n/a n/a |
| mlwe/- | primal-lll | small/1 | 17.9/21.0/23.2 [19.000000, 23.000000] | n/a n/a | 0.504609 [48.9%, 51.8%] |
| mlwe/- | primal-lll | small/2 | 53.8/63.0/74.7 [58.500000, 71.500000] | n/a n/a | 0.498323 [47.4%, 51.3%] |
| msis/- | lll-short-vector | large/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | lll-short-vector | large/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | lll-short-vector | medium/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | lll-short-vector | medium/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | lll-short-vector | small/1 | 8.6/12.0/13.2 [10.000000, 13.000000] | n/a n/a | 0.549082 [53.4%, 56.3%] |
| msis/- | lll-short-vector | small/2 | 24.0/33.0/39.7 [27.000000, 37.000000] | n/a n/a | 0.580613 [57.3%, 58.6%] |
| msis/- | progressive-bkz | large/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | progressive-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | progressive-bkz | medium/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | progressive-bkz | medium/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | progressive-bkz | small/1 | 8.6/12.0/13.2 [10.000000, 13.000000] | n/a n/a | 0.683433 [67.7%, 69.2%] |
| msis/- | progressive-bkz | small/2 | 24.0/33.0/39.7 [27.000000, 37.000000] | n/a n/a | 0.702100 [69.9%, 70.6%] |
| msis/- | restart-bkz | large/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | restart-bkz | large/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | restart-bkz | medium/1 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | restart-bkz | medium/2 | n/a n/a | n/a n/a | n/a n/a |
| msis/- | restart-bkz | small/1 | 8.6/12.0/13.2 [10.000000, 13.000000] | n/a n/a | 0.689095 [68.4%, 70.2%] |
| msis/- | restart-bkz | small/2 | 24.0/33.0/39.7 [27.000000, 37.000000] | n/a n/a | 0.720004 [71.5%, 72.7%] |

### Paired complete-solver comparisons

Positive gains mean lower complete CPU on cases solved by both methods. All eligible pair counts are shown, including unsolved pairs. Conditioning on joint success can bias timing comparisons; failure and quality columns must be considered. These strategy comparisons do not isolate a causal reduction-only change.

| Track | Comparison | Profile/eta | All pairs | Joint successes | Median CPU gain (95% CI) | Median norm² change |
|---|---|---|---:|---:|---|---:|
| mlwe | primal-bkz / primal-lll | large/1 | 10 | 0 | n/a n/a | n/a |
| mlwe | primal-bkz / primal-lll | large/2 | 10 | 0 | n/a n/a | n/a |
| mlwe | primal-bkz / primal-lll | medium/1 | 10 | 10 | -3.7% [-4.7%, -2.7%] | 0.0 |
| mlwe | primal-bkz / primal-lll | medium/2 | 10 | 0 | n/a n/a | n/a |
| mlwe | primal-bkz / primal-lll | small/1 | 10 | 10 | -7.7% [-10.4%, -6.2%] | 0.0 |
| mlwe | primal-bkz / primal-lll | small/2 | 10 | 10 | -5.3% [-8.1%, -3.0%] | 0.0 |
| msis | progressive-bkz / lll-short-vector | large/1 | 10 | 0 | n/a n/a | n/a |
| msis | progressive-bkz / lll-short-vector | large/2 | 10 | 0 | n/a n/a | n/a |
| msis | progressive-bkz / lll-short-vector | medium/1 | 10 | 0 | n/a n/a | n/a |
| msis | progressive-bkz / lll-short-vector | medium/2 | 10 | 0 | n/a n/a | n/a |
| msis | progressive-bkz / lll-short-vector | small/1 | 10 | 10 | -43.2% [-44.6%, -40.2%] | 0.0 |
| msis | progressive-bkz / lll-short-vector | small/2 | 10 | 10 | -39.7% [-42.3%, -38.0%] | 0.0 |

## Study decision

This report computes descriptive evidence only. Eligibility, scientific gates, primitive selection, and agent approval must be recorded separately under the committed freeze. Neither a complete cohort nor high reduction share waives a failed gate.
