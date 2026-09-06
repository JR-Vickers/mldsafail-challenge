# Primitive Selection Research Milestone

## Status and recommendation

The harness and complete development cohort are implemented. The provisional
choice is **Module-SIS short-relation search**, but the primitive is **not
selected or frozen**. Two mandatory gates remain external to this repository:

1. a lattice-cryptography specialist must review the definitions, embeddings,
   planted-relation construction, verifier, and decision analysis; and
2. that reviewer must provide a fresh nonce after the implementation/configuration
   freeze, after which the 20-seed-per-profile validation cohort must run in the
   rebuilt container.

This distinction matters. The development evidence is enough to reject BKZ as
the organizing primitive under the stated decision rule, but it is not a
substitute for held-out validation or specialist approval.

## Scope and safety

The study uses only repository-generated synthetic instances over
`R_q = Z_q[x]/(x^n + 1)`. The paired profiles are:

| Profile | n | q | MLWE (k,l) | MSIS rows x columns | eta |
|---|---:|---:|---:|---:|---:|
| small | 8 | 97 | (2,2) | 2 x 3 | 1, 2 |
| medium | 16 | 193 | (3,2) | 3 x 4 | 1, 2 |
| large | 32 | 257 | (4,3) | 4 x 5 | 1, 2 |

Each modulus is `1 mod 2n`. Random streams are separated by study version,
track, profile, seed, and sampling purpose. The CLI has no external-instance or
arbitrary-parameter input. The study is a structural analogue; it does not
recover ML-DSA keys or forge signatures. FIPS 204 is the normative source for
the motivating ML-DSA structure, not a target for these experiments:
[NIST FIPS 204](https://csrc.nist.gov/pubs/fips/204/final).

`research/primitive_selection/` is isolated from the production package. Its
container pins its multi-architecture base by digest plus `fpylll==0.6.4` and
`cysignals==1.12.5`; the production lock and web image are unchanged. Adapters
use fpylll for LLL, BKZ, CVP, and enumeration rather than reimplementing fplll.

## Contracts and verification

Version-1 canonical JSON contracts cover public MLWE and MSIS instances,
derived BKZ bases with source provenance, and tagged solver outputs. Instance
IDs hash the complete canonical public payload. Hard caps bound degree,
modulus, ranks, serialized size, process address space, and wall time.

- MLWE verification checks both short vectors, every coefficient bound, and
  the full relation `A*s1+s2=t`.
- Module-SIS verification rejects zero and malformed vectors, checks `A*z=0
  mod q`, and recomputes Euclidean-squared and infinity norms.
- BKZ verification checks `B'=U*B` entry by entry, computes `det(U)` exactly
  with fraction-free elimination, requires `|det(U)|=1`, and independently
  computes determinant and root-Hermite quality.

Only the public dataclass is serialized into a solver subprocess. Generator
wrappers retain planted witnesses evaluator-side, and tests assert those field
names never enter the public payload.

## Measurement protocol

Every case runs with one warm-up followed by three measured repetitions in
fresh subprocesses. Solver order is deterministically randomized. The worker
applies a 2-GiB address-space limit and a single-core affinity where the host
supports it; the parent enforces a 60-second wall limit. Results contain process
CPU, parent-observed wall time, peak RSS, phase timings, fplll/BKZ adapter
counters, correctness, quality, source/input/output digests, revision, and host
metadata. Median process CPU is the time statistic.

The Benchmark 0.4.0 cooperative `OperationMeter` is never imported. MLWE,
Module-SIS, and BKZ results are reported separately and have no synthetic
cross-track score.

## Development evidence

The complete committed development cohort contains 780 records: 10 seeds,
three profiles, two eta values, all configured solvers, and both MLWE- and
MSIS-derived BKZ bases. All records contain three measured repetitions. There
were 380 verified outcomes, no worker crashes, no evaluator timeouts, and no
memory-limit failures. Expected unsupported cases return no candidate with a
dimension/difficulty diagnostic.

| Track and family | Small success | Medium success | Large success | Median successful CPU |
|---|---:|---:|---:|---:|
| MLWE primal LLL | 100% | 50% | 0% | 0.033265 s |
| MLWE primal BKZ | 100% | 50% | 0% | 0.033716 s |
| MLWE hybrid BDD | 100% | 0% | 0% | 0.042903 s |
| MSIS LLL / progressive / restart | 100% | 0% | 0% | 0.044207 / 0.053328 / 0.088089 s |
| Derived-basis LLL / fixed / progressive | 100% | 100% | 0% | 0.460862 / 0.485451 / 0.607808 s |

Medium MLWE succeeds only for `eta=1`, hence its 50% profile rate. Exhaustive
MLWE is valid on the committed `n=2` fixture but deliberately declines every
exploratory-grid case. At the fixed MSIS budget, all three families reach a best
verified norm squared of 5 and a median of 15 on small.

The full generated tables, including per-profile memory and root-Hermite
quality, are in
[`research/primitive_selection/results/REPORT.md`](../research/primitive_selection/results/REPORT.md).
They reproduce from the raw JSONL with:

```sh
research/primitive_selection/primitive-study report
```

## Decision rule

Reduction accounts for 90.8% of median measured phase CPU in MLWE primal BKZ
and 94.6% in progressive Module-SIS, with similarly high shares in MLWE hybrid
and restart Module-SIS. Thus the development data satisfy the first, 70%
kernel-dominance condition in materially different end-to-end solvers.

The second condition fails in development. Replacing LLL with the configured
BKZ strategy produced median end-to-end gains of **-2.0%** on small MLWE,
**-3.0%** on medium MLWE, and **-21.1%** on small Module-SIS. These are
slowdowns, not the required 20% gains at two sizes. Held-out validation is also
absent. BKZ/block-SVP therefore cannot be selected as the organizing primitive
from this milestone's current evidence.

The fallback rubric is necessarily judgmental and is included for reviewer
challenge:

| Criterion | Weight | MLWE | Module-SIS | Rationale |
|---|---:|---:|---:|---|
| Cryptographic relevance | 30 | 29 | 30 | Both model module assumptions; MSIS is the closer forgery-side proxy. |
| Algorithmic diversity | 20 | 18 | 18 | Each has three distinct families, but some apply only to tiny/small cases. |
| Scaling/headroom | 15 | 13 | 12 | MLWE reaches medium/eta=1; MSIS offers continuous norm quality but currently caps at small. |
| Verifier clarity | 15 | 14 | 15 | MSIS has an exact zero-relation check and direct norm objective. |
| Measurement integrity | 10 | 10 | 10 | Same evaluator-controlled protocol. |
| Safety/reproducibility | 10 | 10 | 10 | Same repository-only generation and caps. |
| **Total** | **100** | **94** | **95** | Within the five-point tie band. |

Because the totals are within five points, the predetermined tie rule proposes
**Module-SIS short-relation search**. This is a proposal for validation and
review, not a benchmark `0.5.0` contract.

## Negative results and limitations

- Exact fpylll CVP enumeration hit the 60-second limit at medium; the frozen
  practical portfolio uses fast CVP and caps medium `eta=2` and large.
- Module-SIS enumeration showed seed-dependent 60-second behavior at medium,
  so every medium seed is classified uniformly as outside the baseline cap.
- Fixed/progressive BKZ did not improve end-to-end runtime and generally did
  not improve the measured first-vector quality enough to justify its cost.
- The planted MSIS construction makes the relation lattice nontrivial and
  reproducible, but a specialist must decide whether fixing the last relation
  polynomial to one introduces an unacceptable structural shortcut.
- Peak RSS includes interpreter/fpylll startup, and phase timings are trusted
  harness instrumentation rather than fplll's internal hardware counters.
- The Docker daemon was unavailable on the development host. Exact local pins
  were used, and every record honestly says `container_image_digest=unavailable`.
  The two-build reproduction script therefore remains unexecuted.
- No reviewer nonce has been supplied, so no validation seed was derived and
  no validation result has been generated.

## Reproduction and remaining gates

```sh
research/primitive_selection/primitive-study smoke
research/primitive_selection/primitive-study verify-results
research/primitive_selection/primitive-study report
research/primitive_selection/rebuild-check.sh
```

After external review freezes the code/configuration, the reviewer supplies a
fresh nonce and runs:

```sh
research/primitive_selection/primitive-study run --cohort validation --nonce REVIEWER_NONCE
research/primitive_selection/primitive-study report
```

The nonce is stored in every validation record and therefore appears in the
evidence after evaluation. Blocking review findings require a new freeze and a
new nonce before rerunning affected experiments.

Benchmark `0.4.0`, hosted submission contracts, and the website remain
operational and numerically separate from this study.
