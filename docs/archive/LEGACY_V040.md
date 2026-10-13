# Unsupported historical benchmark 0.4.0

Retained for reproduction and rollback only. New hosted submissions and supported
clone choices exclude 0.4.0. Historical results, contracts, generators and shared
math remain readable; do not compare their operation counts with MLWE CPU scores.

Use `mldsafail-legacy-bench` or `python -m mldsafail.benchmark.runner` with
that release's ledger metadata, profiles and reviewed fingerprint. The original
Compose files are retained in `deploy/archive/`; run them with the repository
as the explicit project directory, only in an isolated archival environment.
Neither `make bench` nor `mldsafail run` invokes this benchmark anymore.

See preserved source bundle and branch disposition in `docs/acceptance/integration/`.
No historical release, database row or evidence file was deleted by retirement.
