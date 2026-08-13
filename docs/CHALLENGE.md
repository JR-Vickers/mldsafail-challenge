# Benchmark 0.2 challenge contract

Benchmark `0.3.0` asks a solver to recover a bounded coefficient vector from a
small repository-generated modular linear relation. It is a synthetic,
ML-DSA-motivated optimization problem, not a production cryptanalytic target.

## Instance and candidate

For a fixed profile and seed, the trusted generator selects an invertible
square matrix `A` over `Z/qZ`, plants a vector `s` whose coefficients lie in
`[-eta, eta]`, and publishes `(A, t = A s mod q)` as a `ChallengeInstance`.
Only the profile names `small`, `medium`, and `large` are accepted. Their fixed
dimensions, prime moduli, coefficient bounds, and suite sizes live in
`config/profiles.toml`.

The solver contract is:

```python
candidate = solve(instance, operations)
```

It returns `Candidate(coefficients=tuple[int, ...])`. The candidate is valid
only when it has exactly the configured dimension, every coefficient is in
`[-eta, eta]`, and `A * coefficients == t (mod q)`. The independent verifier
checks the fixed profile, public-data identifier, shape, types, bounds, and
relation without receiving the planted solution.

## Evaluation and score

The public and hidden JSON seed maps define the fixed suite. An official result
runs all three profiles over both maps with an unchanged trusted fingerprint.
Custom, single-profile, public-only, legacy-version, or fingerprint-mismatched
runs are useful diagnostics but cannot enter the official ranking.

Correctness gates scoring. The headline score is the sum across every suite
instance of version-2 weighted abstract operations. Version 2 assigns unit
weight to additions, multiplications, modular reductions, basis updates,
memory reads, and memory writes. Thus:

```text
score = sum(all six operation counts over all evaluated instances)
```

Lowest score wins. Wall-clock time, peak memory, solution quality, and raw
category counts are diagnostics only. Changing categories, weights, suite
aggregation, profiles, verification, or limits requires a new benchmark
version and baseline.

Solvers receive a trusted `OperationMeter` with validated increment methods.
The interface rejects negative and malformed increments and exposes immutable
snapshots. This is an audit boundary for cooperative research code, not a
sandbox against malicious Python.

## Resource limits

Each instance must finish within five wall-clock seconds and 64 MiB peak
resident memory. Exceeding either limit makes the instance and run invalid and
unscored. These limits were calibrated on the target MacBook Pro M4 Max using
ten full-suite runs each of the reference and lazy solvers. The slowest observed
instance took 0.040561 seconds and the largest observed peak was 13,565,952
bytes. Applying the documented 10x time and 4x memory margins, rounding, and
the five-second/64-MiB minimums selects the frozen limits above.

## Safety boundary

The runner accepts repository seeds and profiles only. It does not accept
external matrices, public keys, signatures, arbitrary parameter combinations,
or production ML-DSA parameter sets. All executable experiments remain small,
synthetic, deterministic, and locally generated.
