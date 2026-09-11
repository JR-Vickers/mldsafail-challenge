# Frozen specification to implementation

All implementation paths below are under `src/mldsafail/benchmark_v050/`. No runtime import reaches `research/primitive_selection/`.

| Frozen specification section | Implementation | Verification |
|---|---|---|
| Mathematical task, caps and fixed profiles | `constants.py`, `models.py`, `ring.py`, `verify.py` | Sampler/contract differential tests; equation, zero-answer, shape, type, metadata and bound rejection |
| Sampler, NUL domain separation, canonical IDs | `generator.py`; research v2 labels deliberately retained | 60 frozen development instances, all six profile/eta cells |
| Fresh nonce, validation derivation, five-cell epoch | `evidence.seeds`, `evidence.cases`, `cli.create_epoch` | Frozen seed derivation differential; 100 unique cases |
| Strict public tagged contracts | `models.py`, `schemas/instance-v2.schema.json`, `schemas/candidate-v2.schema.json` | Runtime decoding enforces fixed profiles and exact shapes beyond structural schemas |
| Primal-LLL, exhaustive and hybrid settings | `solvers.py`, `embedding.py` | Normalized outputs compared with frozen worker across two clean builds |
| Direct-shortcut viability gate | `simple_baselines.py`, `scoring.eligibility` | Epoch executes frozen direct-linear and exhaustive checks, retains every outcome |
| Fresh worker, complete CPU, RSS, limits | `worker.py`, `execution.invoke` | Real container timeout, memory allocation failure, crash and bounded-output probes |
| Evaluator/solver isolation | `build.py`, `Dockerfile`, `execution.py` | Probe checks absent evaluator paths, network denial, unprivileged UID and read-only root |
| Pinned environment and artifacts | `Dockerfile`, `requirements.txt`, `artifacts.py`, `execution.environment` | Exact wheel hashes, Python/base image and native pins; two-build artifact comparison |
| Epoch/reference lifecycle and evidence | `cli.py`, `evidence.py`, versioned envelope schemas | Exclusive directories, durable per-repetition records, atomic completion manifests, private nonce |
| Independent audit and provenance | `evidence.audit_epoch`, `audit_run`, `partial_diagnostics` | Missing/duplicate records, candidate tampering, settings/version drift and altered aggregate rejection |
| Failure penalty, normalized score, ties, intervals | `scoring.py` ported from frozen `decision.py`; strict audit and eligibility precede scoring | Differential scores, anchored ties and 2,000-resample intervals; frozen reference self-score 1 |
| Historical compatibility | Separate `mldsafail-mlwe` entry point only | Existing tests and `make check`; unchanged 0.4.0 trusted fingerprint |

Public wire objects retain `schema_version="2"` and `study_version="primitive-selection-v2"`; evaluator manifests, summaries and completion markers use `benchmark_version="0.5.0"`. MSIS/BKZ payload branches and generators were excluded. The reference uses the frozen algorithm with the new isolation adapter; each epoch measures its own reference costs with that same adapter.
