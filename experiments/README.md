# Experiment records

Every serious benchmark run appends one JSON object to `results/experiments.jsonl`. The log is the MVP datastore and research audit trail: never rewrite it merely because an experiment failed.

Each record contains an experiment ID, ISO-8601 timestamp, schema and benchmark versions, selected solver, source revision and dirty-tree status, exact command, agent/model and hypothesis, environment metadata, profile metrics, aggregate metrics, verification outcome or failure reason, parent experiment, tags, and a trusted-input integrity fingerprint.

Representative shape:

```json
{
  "experiment_id": "2026-08-12-0017",
  "timestamp": "2026-08-12T13:40:00+08:00",
  "schema_version": "1",
  "benchmark_version": "0.1.0",
  "commit": "def456",
  "dirty": false,
  "command": "python -m mldsafail.benchmark.runner",
  "agent": "codex",
  "hypothesis": "cache repeated reduction state",
  "solver": "balanced",
  "correct": true,
  "runtime_seconds": 1.82,
  "peak_memory_bytes": 224395264,
  "abstract_cost": 934128,
  "solution_quality": 12,
  "profiles": {"toy-small": {}, "toy-medium": {}, "toy-large": {}},
  "tags": ["algorithm", "public"],
  "notes": "Improves medium and large profiles."
}
```

The benchmark writes aggregate values under `aggregate`. The dashboard also accepts historical values at the top level or nested under `aggregate_metrics`, `metrics`, or `summary`. It skips malformed JSONL lines and reports their count instead of hiding the issue or failing the whole view.

Failed, timed-out, invalid, and regressing experiments should include the same provenance fields, set `correct` to false where applicable, and provide `failure_reason`. They are excluded from records and the Pareto frontier but remain visible in recent history.

Comparison scope is derived deterministically from the trusted fingerprint plus the suite and profile names stored under `suites`. Full public-plus-hidden evaluations are the preferred official cohort. When no full evaluation exists, the dashboard selects one exact contract/suite/profile signature; it never ranks a one-seed custom run, an older benchmark contract, or a single-profile smoke run against a broader evaluation.
