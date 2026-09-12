# MLWE Measurement-Stability Study

## Protocol

This is an observational study of the frozen local 0.5.0 MLWE benchmark.  It
does not alter frozen scoring, the 1% tie band, worker code, environment, or
benchmark semantics.  Its purpose is to describe repeat-execution variation
for one private epoch on this idle macOS ARM64 MacBook and to separate the
frozen native primal-LLL measurement from the same algorithm through the
contestant adapter. The evaluated worker remains the pinned Linux ARM64 Docker
image; only the Docker host is macOS. The harness rejects any other host class
before it creates private evidence.

The study is implemented by `scripts/mlwe_stability.py`.  Before a cohort is
started, the operator records the exact adapter and selected-candidate source
digests.  The frozen worker image, trusted-code fingerprint, artifact digest,
architecture, Python version, and package artifacts are captured from the
epoch manifest.  The native role is the frozen worker's `primal-lll` solver;
the adapter role is an unchanged contestant snapshot of primal-LLL; and the
candidate role is the already frozen selected contestant.  No role may change
source or environment during the cohort.

`run` creates a new, exclusive private evidence root and exactly one fresh
epoch.  Epoch creation contains its frozen 1,200 executions (100 cases, three
reference solvers, one warm-up plus three measurements).  It then executes ten
cycles, each with all three roles and the epoch's 100 ranked cases.  Every run
has one warm-up and three measured fresh-container executions, so the cohort
has 30 ranked runs and 12,000 further executions, for 13,200 total fresh
executions.

The order rotates in the following predeclared sequence, with cycle numbers
starting at one:

1. native, adapter, candidate
2. adapter, candidate, native
3. candidate, native, adapter

Those three orders repeat through cycle ten.  Run directory names encode both
cycle and role.  All runs are sequential.  A source or environment mismatch
stops the cohort.

## Evidence and interruption handling

The private root is created exclusively and is never resumed or overwritten.
Every completed worker record is already durable under the frozen evidence
format.  On interruption or another error, `INCOMPLETE.json` is written when
possible and partial evidence remains in place.  A partial cohort is not
analyzed as a complete cohort, cannot be resumed, cannot be replaced with a
new epoch under the same root, and cannot be used to select a favorable repeat.

`analyze` independently audits the epoch and every complete run, rechecks both
contestant source digests and the pinned environment, and regenerates the
analysis twice from saved evidence.  It rejects incomplete evidence, invalid
answers, drift, or a byte mismatch between the two analyses.  Normal frozen
failure penalties remain in the score, but an invalid answer makes the cohort
ineligible for analysis.

Raw nonce, cases, seeds, candidates, worker streams, individual measurements,
host IDs, and private filesystem paths remain only in the private evidence
root and are never committed.  `report` writes new, exclusive sanitized JSON
and Markdown outputs.  Recursive filtering excludes those fields even if they
are nested in an input object.

## Published aggregates and interpretation

The sanitized report publishes per-role ordered score series, each frozen
score and bootstrap interval, range, median, coefficient of variation, failure
counts, and cell aggregates.  It also publishes adapter/native ratios,
candidate/adapter ratios, and their per-cell geometric aggregates.  Case-level
variation is summarized only as aggregate counts and variation statistics; it
does not expose case identities.

The report describes the observed score spread relative to the frozen 1% tie
band.  It is descriptive only: this single-host, single-epoch cohort makes no
statistical-significance or portability claim and cannot justify a scoring,
tie-band, or environment change.  A cross-epoch or multi-host study is a
separate protocol.
