# MLWE Agent Optimization Pilot

## Purpose and scope

This bounded pilot asks whether one optimization agent can improve the frozen
local 0.5.0 MLWE primal-LLL baseline on repository-generated toy instances. A
well-supported negative result is a valid outcome. Hosted integration and all
changes to the frozen benchmark package or worker image are outside scope.

The preparation revision is
`065c5488306e02531605a4438d417a1051985a0d`. The orchestration agent is Codex
(GPT-6). The dedicated optimizer is predeclared as Codex Astra with xhigh
reasoning, subject to local availability; the experiment ledger records the
actual agent and model used before execution.

## Fixed boundaries

The immutable comparison baseline is an unchanged snapshot of
`examples/mlwe/primal-lll/solver.py`. The contestant starts as a separate copy
of that snapshot and retains the public `solve(public_instance)` interface.
Contestant submissions contain Python source only, contain no symlinks, and
must remain within the existing 2,000,000-byte source limit.

Optimization edits are permitted only in the contestant workspace. The pilot
orchestrator, its focused tests, this protocol, the experiment ledger, the
sanitized report, and `docs/PLAN.md` may change to support and record the pilot.
The optimizer may copy general-purpose routines into the contestant workspace.
It may not edit or import private evaluator state, change
`src/mldsafail/benchmark_v050/`, rebuild the generator, cache answers,
special-case seeds or instance identifiers, manipulate timing, accept external
cryptographic targets, or weaken verification, scoring, limits, or environment
identity checks.

Raw private epoch material and run evidence live under an ignored private
evidence root outside the contestant workspace. They never enter Git. Public
development evidence is diagnostic and is stored separately from private
evidence and official rankings.

## Preparation

Before optimization starts:

1. Commit this protocol.
2. Run `source .venv/bin/activate && make check`.
3. Resolve the pinned `mldsafail-mlwe:0.5.0` image and require its trusted label
   to equal the frozen package fingerprint.
4. Run the existing local `mldsafail-mlwe smoke` workflow in real containers.
5. Create immutable baseline and editable contestant workspaces from the
   primal-LLL starter.
6. Exercise the new public development path in real containers.
7. Establish the contestant baseline on the full public development suite.

Preparation and final private validation do not consume the optimization
budget.

## Public development protocol

The public suite is the Cartesian product of the five ranked cells
`small/eta1`, `small/eta2`, `medium/eta1`, `medium/eta2`, and `large/eta1` with
seeds 0 through 9. It therefore has exactly 50 cases. Every case gets one
warm-up and three measured fresh-container executions, for 200 executions per
development evaluation.

`scripts/mlwe_pilot.py develop` creates a unique output directory exclusively,
snapshots contestant source, records its digest and the full pinned environment
identity, writes every execution durably, audits correctness, and produces cell
and total diagnostic scores normalized to the separately measured development
baseline. Existing output directories are rejected. Interrupted runs retain
their records, have no completion marker, and cannot participate in candidate
selection.

Before each experiment, append a record containing a falsifiable hypothesis and
its intended mechanism. Each completed record contains the parent revision,
source digest, agent/model, timestamps, exact command, environment, correctness,
failures, cell scores, total diagnostic score, and keep/revert decision. Invalid,
regressing, abandoned, and incomplete attempts remain in the ledger. Focused
correctness checks precede every full public evaluation.

## Optimization budget and selection

The optimization budget is at most six hypotheses or four elapsed hours,
whichever occurs first. The clock starts only after preparation and the full
development baseline complete. Public evaluation time counts. A development
evaluation already running at the four-hour deadline may finish; after the
deadline the optimizer makes no edits and starts no further hypothesis. A
seventh hypothesis is never started.

Validated improvements receive descriptive checkpoint commits. Regressions are
reverted from contestant source while their revisions or patches and ledger
records remain as evidence. Candidate selection considers only complete,
audited, fully verified public runs with the frozen source and environment
identities. The lowest raw diagnostic score wins; an exact score tie keeps the
earlier candidate. If nothing improves the development baseline, the original
contestant wins. The selected source digest is frozen and the optimizer session
ends before any private epoch or feedback exists.

## Private validation order

After candidate freeze, create exactly one fresh private epoch with the existing
epoch command. Its frozen reference and viability gates must pass. Failed gates
and all partial evidence are retained, and seeds are not silently replaced.

On the same idle host and epoch, run the unchanged reference contestant and the
frozen candidate sequentially in this predeclared order:

1. reference, candidate;
2. candidate, reference;
3. reference, candidate.

Each run uses the epoch's 100 ranked cases with one warm-up and three measured
executions. Together with the epoch creation runs, the protocol performs 3,600
fresh container executions. Normal solver failures receive the frozen penalty;
any invalid answer makes its run ineligible. Interruptions leave the comparison
incomplete and are neither discarded nor silently rerun.

All six runs are independently audited. Rankings are regenerated twice from
saved evidence and both analyses must be identical. The public artifact is a
strictly filtered aggregate containing source identities, provenance, each
score and interval, three paired candidate/reference ratios, reference spread,
failures, and cell-level comparisons. Nonces, cases, seeds, candidates, streams,
individual measurements, host identifiers, and private filesystem paths are
excluded recursively.

## Acceptance and interpretation

The pilot is operationally complete when preparation checks pass, every
attempt is recorded, a candidate is frozen without private feedback, the single
private epoch and prescribed six runs either complete or retain documented
partial evidence, audits reproduce exactly, focused tests and `make check` pass,
and the requested handoff artifacts exist.

Call the result a **consistent observed improvement** only when all six runs are
eligible and the candidate beats its paired reference by more than the frozen
1% tie band in all three predeclared pairs. This rule is descriptive and does
not establish statistical significance. Otherwise classify the result as tied,
inconsistent, regressed, invalid, or incomplete. Never select the best private
repetition or alter official scoring.

The three pairs estimate repeat-execution variation on this host. The report
separately identifies the already known frozen-reference versus contestant
adapter difference. This initial stability check does not replace a broader
measurement study. Local execution also assumes cooperative submitted Python;
the existing isolation and resource caps limit impact but are not a hostile-code
security boundary.
