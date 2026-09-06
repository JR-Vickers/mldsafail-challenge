# Primitive-selection development report

Generated only from the committed JSONL records by `primitive-study report`.

| Track | Solver | Cases | Success | Median CPU (s) | Peak RSS (MiB) | Median norm² | Median RHF |
|---|---|---:|---:|---:|---:|---:|---:|
| bkz | fixed-bkz | 120 | 66.7% | 0.048535 | 34.2 | n/a | 0.987584 |
| bkz | lll-only | 120 | 66.7% | 0.047165 | 34.0 | n/a | 0.987584 |
| bkz | progressive-bkz | 120 | 66.7% | 0.059241 | 40.5 | n/a | 0.987584 |
| mlwe | exhaustive | 60 | 0.0% | 0.000064 | 19.8 | n/a | n/a |
| mlwe | hybrid-bdd | 60 | 33.3% | 0.012676 | 26.4 | 38.5 | n/a |
| mlwe | primal-bkz | 60 | 50.0% | 0.016411 | 28.9 | 52.0 | n/a |
| mlwe | primal-lll | 60 | 50.0% | 0.016022 | 27.9 | 52.0 | n/a |
| msis | lll-short-vector | 60 | 33.3% | 0.021651 | 26.0 | 15.0 | n/a |
| msis | progressive-bkz | 60 | 33.3% | 0.021530 | 26.5 | 15.0 | n/a |
| msis | restart-bkz | 60 | 33.3% | 0.021616 | 27.0 | 15.0 | n/a |

## Reduction share in end-to-end solvers

| Solver | Median reduction share | Verified cases |
|---|---:|---:|
| primal-bkz | 90.8% | 30 |
| hybrid-bdd | 86.2% | 20 |
| progressive-bkz | 100.0% | 100 |
| restart-bkz | 92.9% | 20 |

## Decision-rule status

No recommendation is frozen: validation results from a post-freeze reviewer nonce are absent.

## Integrity notes

Times, memory, correctness, and quality remain separate; no cross-track synthetic score is computed.
The cooperative Benchmark 0.4.0 `OperationMeter` is not imported or used.
