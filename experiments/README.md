# Experiment records

Every serious benchmark run appends one JSON object to `results/experiments.jsonl`. The log is the MVP datastore and research audit trail: never rewrite it merely because an experiment failed.

Each record contains an experiment ID, ISO-8601 timestamp, schema and benchmark versions, selected solver, source revision and dirty-tree status, exact command, agent/model and hypothesis, environment metadata, profile metrics, aggregate metrics, verification outcome or failure reason, parent experiment, tags, and a trusted-input integrity fingerprint.

Representative shape:

```json
{
  "experiment_id": "2026-08-12-0017",
  "timestamp": "2026-08-12T13:40:00+08:00",
  "schema_version": "2",
  "benchmark_version": "0.2.0",
  "agent": "codex",
  "hypothesis": "cache repeated reduction state",
  "solver": "lazy",
  "correct": true,
  "score": 188411,
  "cost_model_version": "2",
  "resource_limits": {
    "per_instance_wall_seconds": 5.0,
    "per_instance_peak_memory_bytes": 67108864
  },
  "aggregate": {
    "score": 188411,
    "abstract_cost": 188411,
    "total_wall_seconds": 0.13,
    "peak_memory_bytes": 11780096,
    "solution_quality": 3
  },
  "profiles": {"small": {}, "medium": {}, "large": {}},
  "tags": ["algorithm", "public"],
  "notes": "Improves medium and large profiles."
}
```

The benchmark writes the canonical score both at the top level and under `aggregate`; schema validation requires them to match. Diagnostics and per-category counts remain under aggregate, profile, and instance data. The dashboard skips malformed JSONL lines and reports their count instead of hiding the issue or failing the whole view.

Failed, timed-out, invalid, and over-limit experiments include the same provenance fields, set `correct` to false, set score fields to `null`, and provide `failure_reason`. Regressions can remain correct and scored, but do not advance the best-known-score frontier. Every experiment remains visible in recent history.

Comparison scope is derived deterministically from the benchmark/schema versions, trusted fingerprint, and suite/profile names stored under `suites`. Full public-plus-hidden evaluations are the official cohort. Schema-1 history remains readable but is never ranked with schema-2 scored results.
