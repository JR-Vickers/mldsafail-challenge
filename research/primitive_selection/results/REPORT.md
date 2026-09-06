# Primitive-selection development report

Generated only from the committed JSONL records by `primitive-study report`.

| Track | Solver | Cases | Success | Median successful CPU (s) | Peak RSS (MiB) | Median norm² | Median RHF |
|---|---|---:|---:|---:|---:|---:|---:|
| bkz | fixed-bkz | 120 | 66.7% | 0.491217 | 210.6 | n/a | 0.987584 |
| bkz | lll-only | 120 | 66.7% | 0.460584 | 211.2 | n/a | 0.987584 |
| bkz | progressive-bkz | 120 | 66.7% | 0.635972 | 208.4 | n/a | 0.987584 |
| mlwe | exhaustive | 60 | 0.0% | n/a | 206.2 | n/a | n/a |
| mlwe | hybrid-bdd | 60 | 33.3% | 0.023758 | 199.7 | 38.5 | n/a |
| mlwe | primal-bkz | 60 | 50.0% | 0.014399 | 204.2 | 52.0 | n/a |
| mlwe | primal-lll | 60 | 50.0% | 0.013567 | 197.8 | 52.0 | n/a |
| msis | lll-short-vector | 60 | 33.3% | 0.025150 | 199.7 | 15.0 | n/a |
| msis | progressive-bkz | 60 | 33.3% | 0.035423 | 207.7 | 15.0 | n/a |
| msis | restart-bkz | 60 | 33.3% | 0.072430 | 210.6 | 15.0 | n/a |

## Scaling by profile

CPU medians include verified cases only; `n/a` means that the family reached its declared difficulty cap.

| Track | Solver | Profile | Cases | Success | Median CPU (s) | Peak RSS (MiB) |
|---|---|---|---:|---:|---:|---:|
| bkz | fixed-bkz | large | 40 | 0.0% | n/a | 209.8 |
| bkz | fixed-bkz | medium | 40 | 100.0% | 1.155544 | 207.2 |
| bkz | fixed-bkz | small | 40 | 100.0% | 0.031118 | 210.6 |
| bkz | lll-only | large | 40 | 0.0% | n/a | 211.2 |
| bkz | lll-only | medium | 40 | 100.0% | 1.111154 | 210.3 |
| bkz | lll-only | small | 40 | 100.0% | 0.029111 | 206.3 |
| bkz | progressive-bkz | large | 40 | 0.0% | n/a | 188.4 |
| bkz | progressive-bkz | medium | 40 | 100.0% | 1.404463 | 208.4 |
| bkz | progressive-bkz | small | 40 | 100.0% | 0.042770 | 198.9 |
| mlwe | exhaustive | large | 20 | 0.0% | n/a | 206.2 |
| mlwe | exhaustive | medium | 20 | 0.0% | n/a | 184.7 |
| mlwe | exhaustive | small | 20 | 0.0% | n/a | 198.4 |
| mlwe | hybrid-bdd | large | 20 | 0.0% | n/a | 199.7 |
| mlwe | hybrid-bdd | medium | 20 | 0.0% | n/a | 198.7 |
| mlwe | hybrid-bdd | small | 20 | 100.0% | 0.023758 | 198.4 |
| mlwe | primal-bkz | large | 20 | 0.0% | n/a | 202.1 |
| mlwe | primal-bkz | medium | 20 | 50.0% | 0.348048 | 204.2 |
| mlwe | primal-bkz | small | 20 | 100.0% | 0.013982 | 199.7 |
| mlwe | primal-lll | large | 20 | 0.0% | n/a | 190.1 |
| mlwe | primal-lll | medium | 20 | 50.0% | 0.334751 | 197.8 |
| mlwe | primal-lll | small | 20 | 100.0% | 0.013441 | 191.7 |
| msis | lll-short-vector | large | 20 | 0.0% | n/a | 181.9 |
| msis | lll-short-vector | medium | 20 | 0.0% | n/a | 199.7 |
| msis | lll-short-vector | small | 20 | 100.0% | 0.025150 | 199.7 |
| msis | progressive-bkz | large | 20 | 0.0% | n/a | 207.7 |
| msis | progressive-bkz | medium | 20 | 0.0% | n/a | 197.8 |
| msis | progressive-bkz | small | 20 | 100.0% | 0.035423 | 202.1 |
| msis | restart-bkz | large | 20 | 0.0% | n/a | 210.6 |
| msis | restart-bkz | medium | 20 | 0.0% | n/a | 206.2 |
| msis | restart-bkz | small | 20 | 100.0% | 0.072430 | 200.4 |

## Module-SIS quality at the fixed budget

| Solver | Profile | Success | Best verified norm² | Median verified norm² |
|---|---|---:|---:|---:|
| lll-short-vector | large | 0.0% | n/a | n/a |
| lll-short-vector | medium | 0.0% | n/a | n/a |
| lll-short-vector | small | 100.0% | 5.0 | 15.0 |
| progressive-bkz | large | 0.0% | n/a | n/a |
| progressive-bkz | medium | 0.0% | n/a | n/a |
| progressive-bkz | small | 100.0% | 5.0 | 15.0 |
| restart-bkz | large | 0.0% | n/a | n/a |
| restart-bkz | medium | 0.0% | n/a | n/a |
| restart-bkz | small | 100.0% | 5.0 | 15.0 |

## Derived-basis quality against resources

| Source | Solver | Profile | Success | Median CPU (s) | Peak RSS (MiB) | Median RHF |
|---|---|---|---:|---:|---:|---:|
| mlwe | fixed-bkz | large | 0.0% | n/a | 209.8 | n/a |
| mlwe | fixed-bkz | medium | 100.0% | 0.989460 | 192.2 | 0.987584 |
| mlwe | fixed-bkz | small | 100.0% | 0.033538 | 198.7 | 0.976860 |
| mlwe | lll-only | large | 0.0% | n/a | 211.2 | n/a |
| mlwe | lll-only | medium | 100.0% | 0.952816 | 202.9 | 0.987584 |
| mlwe | lll-only | small | 100.0% | 0.031101 | 197.7 | 0.976860 |
| mlwe | progressive-bkz | large | 0.0% | n/a | 184.6 | n/a |
| mlwe | progressive-bkz | medium | 100.0% | 1.262731 | 201.6 | 0.987584 |
| mlwe | progressive-bkz | small | 100.0% | 0.048217 | 198.9 | 0.976860 |
| msis | fixed-bkz | large | 0.0% | n/a | 196.7 | n/a |
| msis | fixed-bkz | medium | 100.0% | 1.387082 | 207.2 | 1.018546 |
| msis | fixed-bkz | small | 100.0% | 0.027607 | 210.6 | 0.988174 |
| msis | lll-only | large | 0.0% | n/a | 198.6 | n/a |
| msis | lll-only | medium | 100.0% | 1.334296 | 210.3 | 1.020161 |
| msis | lll-only | small | 100.0% | 0.026948 | 206.3 | 0.988174 |
| msis | progressive-bkz | large | 0.0% | n/a | 188.4 | n/a |
| msis | progressive-bkz | medium | 100.0% | 1.592995 | 208.4 | 1.018379 |
| msis | progressive-bkz | small | 100.0% | 0.037123 | 198.8 | 0.988174 |

## Reduction share in end-to-end solvers

| Track | Solver | Median reduction share | Verified cases |
|---|---|---:|---:|
| mlwe | primal-bkz | 90.9% | 30 |
| mlwe | hybrid-bdd | 85.9% | 20 |
| msis | progressive-bkz | 94.2% | 20 |
| msis | restart-bkz | 92.2% | 20 |

## Paired kernel substitutions

Positive values are end-to-end CPU gains from replacing the LLL kernel with the BKZ strategy on the same verified case.

| Track | Comparison | Profile | Paired cases | Median gain |
|---|---|---|---:|---:|
| mlwe | primal-bkz vs primal-lll | medium | 10 | -3.7% |
| mlwe | primal-bkz vs primal-lll | small | 20 | -6.7% |
| msis | progressive-bkz vs lll-short-vector | small | 20 | -41.0% |

## Decision-rule status

The development data meet the 70% reduction-share gate in multiple end-to-end families, but the paired substitutions do not establish a 20% gain at two sizes. No recommendation is frozen: validation results from a post-freeze reviewer nonce and external specialist approval are absent.

## Negative results and limitations

- Exhaustive MLWE is deliberately limited to the committed tiny fixture; the exploratory grid is beyond its search cap.
- Hybrid MLWE is tractable only at the small profile. Primal LLL/BKZ also solve medium/eta=1, but medium/eta=2 and large exceed the frozen applicability limit.
- All three Module-SIS families verify on small, while seed-dependent enumeration made medium and large unsuitable for the fixed budget.
- Derived-basis reduction verifies at small and medium; large derived bases exceed the frozen dimension limit.
- The development run was executed in the digest-pinned container; validation must use a fresh reviewer nonce after the freeze.

## Integrity notes

Times, memory, correctness, and quality remain separate; no cross-track synthetic score is computed.
The cooperative Benchmark 0.4.0 `OperationMeter` is not imported or used.
