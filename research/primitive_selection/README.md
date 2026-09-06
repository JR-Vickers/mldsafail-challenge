# Primitive-selection study

This package compares reduced-scale MLWE recovery, Module-SIS relation search,
and basis reduction as a shared kernel. It is isolated from the production web
application and accepts no external instance files or arbitrary parameters.

The fixed profiles pair `(n,q,ranks)` as `(8,97,2/2)`, `(16,193,3/2)`, and
`(32,257,4/3)`, with `eta` 1 and 2. Module-SIS uses respectively 2x3, 3x4,
and 4x5 module matrices. Every pseudorandom stream is separated by study
version, track, profile, seed, and purpose.

Run through the pinned dependency container:

```sh
research/primitive_selection/primitive-study smoke
research/primitive_selection/primitive-study run --cohort development
research/primitive_selection/primitive-study run --cohort validation --nonce REVIEWER_NONCE
research/primitive_selection/primitive-study report
```

Validation must happen only after code/configuration freeze with a fresh nonce
supplied by the external reviewer. The nonce is embedded in every validation
record. Each case receives one warm-up and three measured repetitions in a
fresh subprocess, with one CPU, a 60-second wall deadline, and a 2-GiB address
space/container limit. The parent randomizes solver order and reports median
process CPU time; Benchmark 0.4.0's cooperative operation meter is not used.

The container installs exact fpylll/cysignals versions. Every result also stores
the actual image content digest; this is the reproducibility authority even if
the upstream base-image tag is later republished.
