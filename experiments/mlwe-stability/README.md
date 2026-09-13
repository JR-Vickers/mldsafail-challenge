# MLWE stability cohort

This directory contains the sanitized aggregate output from the completed
`mlwe-measurement-stability-v1` cohort collected on 2026-09-13. It contains no
private epoch inputs, worker streams, host identifiers, source snapshots, or
per-case identities; raw evidence remains outside Git in a restricted location.

The cohort comprises 30 ranked runs and 13,200 fresh worker executions: ten
rotating cycles each for the frozen native solver, its contestant adapter, and
the frozen selected candidate. Both analyses of saved evidence were
byte-identical.

- [summary.json](summary.json) is the machine-readable report: score series,
  per-run frozen intervals, failure counts, cell aggregates, ratios, and only
  aggregate case-level variation.
- [REPORT.md](REPORT.md) is the concise human-readable headline.

This is one macOS ARM64 host and one private epoch. It is descriptive evidence
only, not a portability or statistical-significance claim, and it makes no
change to scoring, the 1% tie band, or the evaluator environment.
