# Primitive-selection development report

Generated only from the committed JSONL records by `primitive-study report`.

| Track | Solver | Cases | Success | Median successful CPU (s) | Peak RSS (MiB) | Median norm² | Median RHF |
|---|---|---:|---:|---:|---:|---:|---:|
| bkz | fixed-bkz | 120 | 66.7% | 0.485451 | 34.2 | n/a | 0.987584 |
| bkz | lll-only | 120 | 66.7% | 0.460862 | 34.0 | n/a | 0.987584 |
| bkz | progressive-bkz | 120 | 66.7% | 0.607808 | 40.5 | n/a | 0.987584 |
| mlwe | exhaustive | 60 | 0.0% | n/a | 19.8 | n/a | n/a |
| mlwe | hybrid-bdd | 60 | 33.3% | 0.042903 | 26.4 | 38.5 | n/a |
| mlwe | primal-bkz | 60 | 50.0% | 0.033716 | 28.9 | 52.0 | n/a |
| mlwe | primal-lll | 60 | 50.0% | 0.033265 | 27.9 | 52.0 | n/a |
| msis | lll-short-vector | 60 | 33.3% | 0.044207 | 26.0 | 15.0 | n/a |
| msis | progressive-bkz | 60 | 33.3% | 0.053328 | 26.5 | 15.0 | n/a |
| msis | restart-bkz | 60 | 33.3% | 0.088089 | 27.0 | 15.0 | n/a |

## Scaling by profile

CPU medians include verified cases only; `n/a` means that the family reached its declared difficulty cap.

| Track | Solver | Profile | Cases | Success | Median CPU (s) | Peak RSS (MiB) |
|---|---|---|---:|---:|---:|---:|
| bkz | fixed-bkz | large | 40 | 0.0% | n/a | 21.9 |
| bkz | fixed-bkz | medium | 40 | 100.0% | 1.113255 | 34.2 |
| bkz | fixed-bkz | small | 40 | 100.0% | 0.048535 | 28.1 |
| bkz | lll-only | large | 40 | 0.0% | n/a | 23.2 |
| bkz | lll-only | medium | 40 | 100.0% | 1.076187 | 34.0 |
| bkz | lll-only | small | 40 | 100.0% | 0.047165 | 26.2 |
| bkz | progressive-bkz | large | 40 | 0.0% | n/a | 21.9 |
| bkz | progressive-bkz | medium | 40 | 100.0% | 1.322481 | 40.5 |
| bkz | progressive-bkz | small | 40 | 100.0% | 0.059241 | 28.1 |
| mlwe | exhaustive | large | 20 | 0.0% | n/a | 18.6 |
| mlwe | exhaustive | medium | 20 | 0.0% | n/a | 18.5 |
| mlwe | exhaustive | small | 20 | 0.0% | n/a | 19.8 |
| mlwe | hybrid-bdd | large | 20 | 0.0% | n/a | 19.7 |
| mlwe | hybrid-bdd | medium | 20 | 0.0% | n/a | 18.6 |
| mlwe | hybrid-bdd | small | 20 | 100.0% | 0.042903 | 26.4 |
| mlwe | primal-bkz | large | 20 | 0.0% | n/a | 19.0 |
| mlwe | primal-bkz | medium | 20 | 50.0% | 0.353318 | 28.9 |
| mlwe | primal-bkz | small | 20 | 100.0% | 0.033500 | 25.8 |
| mlwe | primal-lll | large | 20 | 0.0% | n/a | 18.6 |
| mlwe | primal-lll | medium | 20 | 50.0% | 0.343097 | 27.9 |
| mlwe | primal-lll | small | 20 | 100.0% | 0.033025 | 25.6 |
| msis | lll-short-vector | large | 20 | 0.0% | n/a | 21.1 |
| msis | lll-short-vector | medium | 20 | 0.0% | n/a | 18.9 |
| msis | lll-short-vector | small | 20 | 100.0% | 0.044207 | 26.0 |
| msis | progressive-bkz | large | 20 | 0.0% | n/a | 20.1 |
| msis | progressive-bkz | medium | 20 | 0.0% | n/a | 19.7 |
| msis | progressive-bkz | small | 20 | 100.0% | 0.053328 | 26.5 |
| msis | restart-bkz | large | 20 | 0.0% | n/a | 20.1 |
| msis | restart-bkz | medium | 20 | 0.0% | n/a | 18.9 |
| msis | restart-bkz | small | 20 | 100.0% | 0.088089 | 27.0 |

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
| mlwe | fixed-bkz | large | 0.0% | n/a | 21.9 | n/a |
| mlwe | fixed-bkz | medium | 100.0% | 0.965826 | 34.2 | 0.987584 |
| mlwe | fixed-bkz | small | 100.0% | 0.050932 | 28.1 | 0.976860 |
| mlwe | lll-only | large | 0.0% | n/a | 23.2 | n/a |
| mlwe | lll-only | medium | 100.0% | 0.927168 | 34.0 | 0.987584 |
| mlwe | lll-only | small | 100.0% | 0.049307 | 26.2 | 0.976860 |
| mlwe | progressive-bkz | large | 0.0% | n/a | 21.9 | n/a |
| mlwe | progressive-bkz | medium | 100.0% | 1.202124 | 40.5 | 0.987584 |
| mlwe | progressive-bkz | small | 100.0% | 0.063774 | 28.1 | 0.976860 |
| msis | fixed-bkz | large | 0.0% | n/a | 20.9 | n/a |
| msis | fixed-bkz | medium | 100.0% | 1.336975 | 33.0 | 1.018546 |
| msis | fixed-bkz | small | 100.0% | 0.045854 | 26.8 | 0.988174 |
| msis | lll-only | large | 0.0% | n/a | 22.4 | n/a |
| msis | lll-only | medium | 100.0% | 1.303662 | 31.5 | 1.020161 |
| msis | lll-only | small | 100.0% | 0.044802 | 25.4 | 0.988174 |
| msis | progressive-bkz | large | 0.0% | n/a | 21.6 | n/a |
| msis | progressive-bkz | medium | 100.0% | 1.522614 | 37.8 | 1.018379 |
| msis | progressive-bkz | small | 100.0% | 0.054424 | 26.3 | 0.988174 |

## Reduction share in end-to-end solvers

| Track | Solver | Median reduction share | Verified cases |
|---|---|---:|---:|
| mlwe | primal-bkz | 90.8% | 30 |
| mlwe | hybrid-bdd | 86.2% | 20 |
| msis | progressive-bkz | 94.6% | 20 |
| msis | restart-bkz | 92.9% | 20 |

## Paired kernel substitutions

Positive values are end-to-end CPU gains from replacing the LLL kernel with the BKZ strategy on the same verified case.

| Track | Comparison | Profile | Paired cases | Median gain |
|---|---|---|---:|---:|
| mlwe | primal-bkz vs primal-lll | medium | 10 | -3.0% |
| mlwe | primal-bkz vs primal-lll | small | 20 | -2.0% |
| msis | progressive-bkz vs lll-short-vector | small | 20 | -21.1% |

## Decision-rule status

The development data meet the 70% reduction-share gate in multiple end-to-end families, but the paired substitutions do not establish a 20% gain at two sizes. No recommendation is frozen: validation results from a post-freeze reviewer nonce and external specialist approval are absent.

## Negative results and limitations

- Exhaustive MLWE is deliberately limited to the committed tiny fixture; the exploratory grid is beyond its search cap.
- Hybrid MLWE is tractable only at the small profile. Primal LLL/BKZ also solve medium/eta=1, but medium/eta=2 and large exceed the frozen applicability limit.
- All three Module-SIS families verify on small, while seed-dependent enumeration made medium and large unsuitable for the fixed budget.
- Derived-basis reduction verifies at small and medium; large derived bases exceed the frozen dimension limit.
- The development run used exact local Python pins because Docker was unavailable; its image digest is recorded as `unavailable`, so it cannot substitute for the required container rebuild and validation run.

## Integrity notes

Times, memory, correctness, and quality remain separate; no cross-track synthetic score is computed.
The cooperative Benchmark 0.4.0 `OperationMeter` is not imported or used.
