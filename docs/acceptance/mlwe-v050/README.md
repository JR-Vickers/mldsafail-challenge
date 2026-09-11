# Local 0.5.0 acceptance evidence

The [check record](checks.json) retains the baseline and final test counts and both trusted fingerprints. The historical fingerprint remains `bc70d64d7334e8de3c87480604d12070ed0d041f93a0af6aa98ef1eaff5ce8a4`; the historical full baseline score was 110201 and the final small check scored 3901. [Make check](make-check.log) passed 240 tests; its eight opt-in Docker tests passed separately in [the Docker log](docker-tests.log).

The real container probes exercise evaluator/repository/credential-path isolation, network denial, read-only root and unprivileged execution; exceptions and process crashes; malformed and non-finite candidates; address-space allocation failure; output overflow; and actual 60-second termination. The first probe initially treated `PermissionError` while examining `/root/.aws` as a test failure. It was corrected to recognize permission denial as inaccessible; the final probe suite passes. An interrupted slow wheel download was replaced with an offline copy of the same wheels, verified against the pinned hashes. No mathematical settings or seeds were adjusted.

Two clean builds used the same committed source and exact wheel inputs with Docker `--no-cache`. Their [artifact comparison](reproduction/result.json) passes. [Normalized public fixtures and outputs](reproduction/normalized.json) cover 36 profile/eta/seed/solver combinations, including stress inputs, and match both clean builds and the frozen research worker. [Native and wheel artifact hashes](reproduction/artifacts.json), [build A](rebuild-a.log), and [build B](rebuild-b.log) are retained. These are public development fixtures, not private epoch inputs.

The `full/` directory contains only whitelisted shareable summaries from the full acceptance workflow. Raw epoch evidence, nonce, seeds, candidates, individual measurements, and contestant snapshots are retained outside the repository in restrictive directories. The evaluator-local location is recorded in `.git/mlwe-v050-private-evidence`; that pointer is not committed. `scripts/mlwe_acceptance.py` reproduces the workflow into fresh directories, and `scripts/mlwe_reproduce.py` performs the clean-build comparison.

The full workflow executes 100 reference cases, 100 exhaustive viability cases and 100 direct-linear viability cases, each with one warmup and three measurements. It then evaluates the reference and hybrid contestants on all 100 ranked cases with the same protocol. Audits regenerate every input and independently verify every candidate; repeated audits and rankings must match exactly. Frozen-reference self-comparison must score 1 with interval [1, 1]. Failed gates abort the workflow and preserve their evidence.

The [full acceptance](full/acceptance.json) passed: 2,000 fresh executions across the epoch, viability checks and two contestant runs. All [viability gates](full/gates.json) passed; large/eta1 reference median CPU was 49.60 times the pooled-small median. [Repeated audits](full/audit-reproduced.json) and [repeated rankings](full/rank-reproduced.json) exactly reproduced their first outputs.

| Entry | Successful ranked cases | Score | 95% score interval | Rank |
|---|---:|---:|---|---:|
| Frozen reference table | 100/100 | 1.000000 | [1.000000, 1.000000] | 1 |
| Reference contestant | 100/100 | 1.022289 | [1.017569, 1.027045] | 2 |
| Hybrid contestant | 99/100 | 1.083590 | [0.990003, 1.289014] | 3 |

Hybrid's one no-candidate case receives the full 60-second penalty. There were no invalid contestant answers. The separate reference contestant includes its adapter/module-loading work and fresh timings; it is not the frozen table's self-comparison.

The [real interruption check](interruption.json) sent SIGINT after one durable warmup. Audit independently verified that record, reported 399 missing executions, and returned nonzero without ranking the partial run. The [final smoke](smoke.json) exercises the installed `mldsafail-mlwe` command and is explicitly non-ranking. All complete private records remain available for another independent audit.
