# Independent 0.6.0 review — 2026-10-03

Reviewer: separate review agent `contract_review`, read-only review of
`docs/MLWE_V060_CONTRACT.md` and `research/cpu_measurement`.
Decision: **fail; contract freeze and adoption blocked**.

1. Scoring wording could allow replacement measurements or success-only sampling.
   Resolved in the proposal: exactly three measurements; any failed measurement
   penalizes the whole case; any invalid candidate makes the run ineligible.
2. The directory flock disappears on SIGKILL. There is no durable ownership
   journal, startup reconciliation, fencing or private Unix-socket supervisor.
   Replacement work cannot prove interrupted accounting cleanup has completed.
3. `harness.run` releases ownership before `native_suite` writes evidence.
   Writes are not synchronized. Ownership must persist through durable counters,
   termination and cleanup records, including failure records.
4. Temporary output files are polled every 50 milliseconds and can grow beyond
   the cap between checks. Implement bounded streaming capture and termination.
5. Initial emptiness and a single membership check do not establish exclusive
   accounting throughout execution. Define authorized descendants, delegation,
   stable cgroup identity and contamination detection and audit their evidence.
6. Generic exception handling discards failure detail; container-removal failure
   can bypass subsequent process cleanup. Preserve original and cleanup failures
   independently, journal mutation boundaries and refuse new work while cleanup
   remains incomplete.
7. The paired gate validates counts without establishing unique complete pairs,
   finite values, provenance, statuses or sequential execution. Native counter,
   contamination, competing-owner, delegation and cleanup fault scenarios are
   missing. Positive grandchild CPU alone does not prove descendant accounting.
8. Freeze a strict versioned evidence schema and independent audit binding
   source, image, epoch, host, accounting parent, ownership generation, membership,
   input delivery, counters, termination, cleanup, output and verifier decisions.
   Current prototype evidence does not satisfy that contract.

Only finding 1 is resolved here. Findings 2–8 remain open. Local prototype tests
cannot substitute for the native fault suite or the unchanged 30-pair thresholds.
Review the supervisor and auditor independently after implementation, before
contract freeze and isolated evaluator integration. No 0.5.0 artifact, score,
worker, epoch, dependency lock or evaluator contract was changed by this review.
