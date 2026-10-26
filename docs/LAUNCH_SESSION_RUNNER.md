# Fresh-session launch runner

The controller in [runner.py](../tools/launch_runner/runner.py) runs the remaining
[session schedule](LAUNCH_ARCHITECTURE_REVIEW.md#sequential-agent-implementation-sessions)
sequentially. Every implementation, repair and independent review starts a new
`codex exec` process, without `resume` or `fork`. The repository and durable
handoffs provide continuity. These CLI sessions need not appear as tabs in the
application. The installed Codex CLI supplies authentication and model settings.
[Official non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
describes JSON events and structured reports.

This runner prepares local engineering and independently reviews completion.
It never executes installation, native VPS acceptance, production evaluation,
epoch creation, rollout or deletion. Those rows stop before a child is launched.
Missing host facts or other external inputs also stop progress. Existing exact
execution authority and scientific validators remain mandatory.

## Start one unattended local run

Prerequisites: clean source checkout, Python 3.12+, installed/authenticated `codex`,
Git identity, `uv`, `make`, and local dependencies needed by the session fixtures.
Keep the machine awake and the controller process running. A terminal multiplexer
or service may supervise the controller; launching it does not create a hosted
background job. The runner uses existing CLI authentication; do not put tokens in
prompts, arguments or committed configuration.

From the repository root:

```sh
source .venv/bin/activate
python tools/launch_runner/runner.py init \
  --state-dir "$HOME/.local/state/mldsafail/launch-preview" \
  --branch engineering/launch-preview
python "$HOME/.local/state/mldsafail/launch-preview/controller.py" run \
  --state-dir "$HOME/.local/state/mldsafail/launch-preview"
```

Initialization creates a dedicated Git worktree and branch at the current clean
commit. Your original checkout stays on its original branch. State, private logs,
reports and a frozen copy of the controller/manifest are outside the source
checkout. Use that copied controller for subsequent commands. The default range
is S03–S19; optional S20–S21 require explicit `--through 21`. The first live gate
is S12, but a missing prerequisite can stop earlier. An existing state directory
is never overwritten. No commit is pushed or automatically merged.

The controller pins the 21 assignment rows and refuses changes to them or the
frozen benchmark/controller boundaries. It reads assignment text from the
architecture review rather than maintaining a second prose backlog. Progress
through the selected range requires checks and independent review for every row;
a blocked or optional session is never marked complete by omission.

Implementation agents get `workspace-write`; reviewers get `read-only`;
interactive approvals are disabled for these local subprocesses. The controller
stages and commits completed implementation edits outside the Codex sandbox,
then independently runs `make check`, changed-document link/anchor checks,
`git diff --check`, ledger/handoff/routing validation and a fresh review of the
whole session change. This avoids granting agents write access to the original
checkout's shared Git administration directory. Agents still run relevant focused
tests and report actual checks. Check or review failure starts a fresh bounded
repair and repeats verification. An external blocker stops rather than becoming
a repair task. Reviewers cannot edit source or change commits.

## Progress and limits

```sh
python "$HOME/.local/state/mldsafail/launch-preview/controller.py" status \
  --state-dir "$HOME/.local/state/mldsafail/launch-preview"
```

`state.json` records current session/phase, baseline and expected HEAD, completed
commits, independent reports, repair/launch counters and in-flight intent.
Each `attempt-NNNN` retains the prompt, process identity, JSON events, stderr and
structured final report. These may contain private paths or diagnostics; keep
this directory private and outside participant artifacts. Publication uses atomic
rename plus file/directory fsync. A lock prevents overlapping controllers; the
direct child inherits it so a killed controller cannot immediately launch another.
A surviving child process group also blocks advancement/recovery.

Defaults: two repairs per session, 80 total agent launches, one hour per agent,
30 minutes per controller check invocation. Set `--max-repairs`, `--max-launches`,
`--timeout` and `--check-timeout` at initialization. Limits and counters persist
across restarts. Launch limits bound attempts, not exact token charges or dollars;
account usage limits remain applicable. No automatic budget reset occurs.
Exit 0 means the command succeeded (check `status` for whether the entire range
is complete); 2 means stopped/error, and 130 means interrupted by the terminal.

## Restart and review-failure recovery

Reissuing `run` after a clean checkpoint continues the recorded phase. An
unfinished child invocation is never blindly replayed. After resolving the
recorded blocker or interrupted child, use:

```sh
python "$HOME/.local/state/mldsafail/launch-preview/controller.py" recover \
  --state-dir "$HOME/.local/state/mldsafail/launch-preview"
python "$HOME/.local/state/mldsafail/launch-preview/controller.py" run \
  --state-dir "$HOME/.local/state/mldsafail/launch-preview"
```

`recover` starts a fresh read-only inspection. It preserves interrupted edits and
attempt records, schedules bounded local repair if needed, or rechecks a complete
checkpoint before another independent review. Dirty or moved work is not reset,
stashed, deleted or silently treated as accepted. A reviewer claiming completion
of an uncommitted dirty checkpoint is converted to bounded repair. Review failures consume the
existing repair budget. Missing external evidence and exhausted budgets remain
stop points. Inspect preserved artifacts before creating a newly scoped run.

The process guard covers controller-owned process groups and inherited locks;
it is not a hostile-code containment system. Agents must not detach or daemonize
background work. Fixture ownership/cleanup requirements remain the responsibility
of the session and independent review. A process that escapes its group is not
certified dead by an absent group. Do not clear locks, kill arbitrary processes
or rerun an ambiguous live operation to recover this controller.

## Continuing after an external step

The manifest identifies S12, S13, S15, S16, S17, S19 and S21 as external. The
runner stops at them even if it has prepared a proposal. Perform the exact
separately authorized procedure outside this runner and preserve its receipts;
update its repository handoff, complete ledger row and next routing, and commit
those documents on the runner worktree branch. Failed or partial operations stay
blocked and must not get a complete ledger row.

Create a private JSON record containing:

```json
{
  "session": "S12",
  "commit": "FULL_WORKTREE_COMMIT_HASH",
  "authority": "Private references to the exact owner grant and independent approved packet",
  "evidence": "Private references to actual installed-paused receipts and retained observations"
}
```

Then import the record and continue:

```sh
python "$HOME/.local/state/mldsafail/launch-preview/controller.py" record-external \
  --state-dir "$HOME/.local/state/mldsafail/launch-preview" \
  --receipt /private/completed-session.json
python "$HOME/.local/state/mldsafail/launch-preview/controller.py" run \
  --state-dir "$HOME/.local/state/mldsafail/launch-preview"
```

Import grants no execution and does not advance the session. Controller checks
and a fresh read-only review must accept matching authority, actual evidence,
commit and handoff first. A prose assertion or populated JSON field alone does
not establish a pass. Failed external checks/review never launch writable repair.
This command records evidence; it is not a replacement for the runtime's exact
packet/identity/freshness validators. Correct external evidence through its
approved procedure and import a corrected record when appropriate.

## Verification and reversal

Run the disposable rehearsals with:

```sh
source .venv/bin/activate
python -m pytest tests/test_launch_session_runner.py
make check
```

They use temporary Git repositories and a fake CLI to test fresh sessions, repair
and review failure, malformed/wrong-commit reports, blockers, launch limits,
external gates, dirty interruption, killed-controller locking and surviving
grandchildren. They do not execute project sessions or certify the VPS. The
[runner preparation handoff](LAUNCH_ARCHITECTURE_REVIEW.md#runner-preparation-handoff--2026-10-26)
records the separate real-CLI toy rehearsal and independent code review.
To repeat the real CLI rehearsal after a Codex upgrade, explicitly run
`python tools/launch_runner/smoke.py --directory /private/new-runner-smoke`.
Choose a new writable directory; this starts actual billed/account-metered Codex
sessions against a toy repository, keeps the records, and never starts project S03.

Stop the controller before reverting its source commit. Existing runs retain their
pinned controller; stopping/reverting source does not cancel an already-running
child or alter its branch. Preserve private run records and worktree commits;
remove only positively inactive disposable resources under the retention policy.
No runtime rollback or production change is implied.
