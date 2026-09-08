# Development calibration and simple adversarial baselines

These exploratory observations use development seeds only. They are separate
from the final development/validation cohorts and do not have the final
cohort's warm-up plus three repetitions. Each observation ran in a fresh
subprocess with the existing 60-second deadline and 2-GiB address-space cap.
They establish settings to investigate; they do not waive a scientific gate.

The two completed v2 directories contain unique run identities, exact Python
source snapshots and SHA-256 digests, configuration, dependency versions,
input/output digests, every observed candidate, and completion manifests:

| Evidence | Development seeds | Records | Independently verified candidates |
|---|---|---:|---:|
| `calibration-v2-mlwe-01` | 0–2 | 72 | 53 |
| `calibration-v2-simple-01` | 0–9 | 180 | 60 |

Independent audit regenerates evaluator inputs, checks case completeness,
uniqueness and digests, and reruns the mathematical verifier on every stored
candidate. Reproduce the audits from the repository root with pinned research
dependencies:

```sh
source .venv/bin/activate
python -m research.primitive_selection.calibration --audit --output research/primitive_selection/review/calibration-v2-mlwe-01
python -m research.primitive_selection.calibration --audit --output research/primitive_selection/review/calibration-v2-simple-01
python -m pytest tests/test_primitive_algorithms.py tests/test_primitive_selection.py
```

To collect a new exploratory run, use `--kind mlwe --seed-count 3` or
`--kind simple --seed-count 10` and a new `--output` directory. Existing
directories are refused. To reproduce historical algorithm snapshots, copy
the selected run's `source/*.py` into an isolated checkout's
`research/primitive_selection/` directory at the manifest's base revision,
install the manifest's pinned dependencies, and collect into a new directory.
The final warm-up/three-repetition cohorts supersede these single observations.

## Observed solver coverage

The fixed proposed profiles are small `(n,q,k,l)=(4,97,2,1)`, medium
`(8,97,2,2)`, and large `(16,193,3,2)`, each with eta 1 and 2. Existing caps
remain degree 32, modulus 257, rank 5, 60 seconds and 2 GiB.

| MLWE profile / eta | Exhaustive | LLL + CVP | BKZ + CVP | Guess + BKZ + Babai |
|---|---:|---:|---:|---:|
| small / 1 | 3/3 | 3/3 | 3/3 | 3/3 |
| small / 2 | 3/3 | 3/3 | 3/3 | 3/3 |
| medium / 1 | cap | 3/3 | 3/3 | 3/3 |
| medium / 2 | cap | 3/3 | 3/3 | 3/3 |
| large / 1 | cap | 3/3 | 3/3 | 3/3 |
| large / 2 | cap | cap | cap | 2/3 |

The exhaustive baseline enumerates s1 only and derives s2 from the public
equation. Its explicit one-million-candidate applicability cap includes all
small cases (81 or 625 possible s1 values). It excludes medium and large
cases before searching. Small-instance exhaustive CPU medians were about
0.15–0.20 ms; lattice methods were about 26 ms including their Python binding
startup. Medium BKZ/CVP CPU medians were about 34 ms, with about 7 ms spent in
reduction. Large eta-1 BKZ/CVP used about 340 ms, with about 307 ms spent in
reduction. These local single-observation timings are calibration evidence,
not final benchmark rankings.

The hybrid baseline guesses one bounded s1 coefficient and applies Babai
nearest-plane decoding to the remaining lattice. It reduces this common
lattice once and reuses it for every guess; it performs no CVP enumeration.
This is an approximate decoder with actual observed no-candidate outcomes,
so it offers a different runtime/correctness tradeoff from exact CVP. Its
dimension cap is 128. LLL/CVP and BKZ/CVP retain identical applicability caps
(dimension 128 for eta 1, dimension 64 for eta 2) for paired comparisons.

Large eta-2 hybrid had one no-candidate result out of three; it was not a
timeout, a declared cap, or a verified solve. Such outcomes must remain visible
in final cohorts. The calibration supplies no basis to claim validated large
eta-2 baseline coverage.

## Simple algebraic and relation searches

All 60 generated MSIS development instances were solved by direct modular
elimination from the public matrix alone. Fixing the final polynomial of z to
one leaves `A_prefix*z_prefix = -A_last (mod q)`. An invertible square prefix
gives the planted answer directly; singular prefixes were handled by bounded
enumeration of the RREF free coefficients. Neither method uses a generation
seed, planted witness, or lattice reduction. Retaining this construction as a
comparator does not make it eligible for selection.

The equally explicit MLWE baseline solves `[A | I]*(s1,s2)=t (mod q)` by
modular elimination with free variables zero. All 60 algebraic answers failed
the required shortness verifier. Ordinary modular solving does not solve this
bounded formulation. A sparse MSIS search checking every relation with one or
two coefficients in `{-1,+1}` found none in the same 60 instances. This zero
success rate cannot counteract the direct modular MSIS shortcut.

## Retained initial exploration

`calibration-initial-unfrozen` retains all 72 measurements and the actual driver
from the first three-seed exploration, which used the original v1 generator
with the proposed smaller profiles and then-in-progress algorithm changes.
Large eta-2 LLL/CVP exceeded 60 seconds on seeds 0 and 1; BKZ/CVP succeeded on
all three seeds. These observations motivated the conservative shared CVP
eta-2 dimension cap. Applying that shared cap to BKZ is an applicability
decision; its capped cases must not be called measured algorithmic failures.

The exact initial algorithm source snapshot and start timestamp were not
captured. Its manifest labels that provenance limitation, and the observations
are excluded from final scientific evidence. They are retained so the failed
attempt and reason for later calibration choices are visible. The subsequent
v2 calibration and complete final cohorts provide the reproducible evidence.
