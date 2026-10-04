# Compose switch remediation — 2026-10-03

**The requested remediation prerequisites pass.** Disposable native deployment,
rollback, forward restoration and cleanup passed on the staging host's Compose
v5.5.1, including a repeat against the newly built release's exact image IDs.
Live staging remains on exact `b4d212d`; no live deployment was retried.

The disposable test reproduced the completed-migration dependency that caused
trouble. It caught a second path: `compose start` restarted the dummy migration
during cleanup. The runner now resolves existing application IDs through Compose
and starts/stops those containers directly through Docker. Image switches and
restoration explicitly reset web/coordinator dependencies and use supported
`up --no-start --no-deps` to keep the coordinator stopped during the drill.
Failed synthetic evidence was preserved and its containers were removed.

The corrected test passed forward, rollback and forward-again switches, backup
web stop/restart, the actual failure-driver restoration path and repeated cleanup.
The dummy migration ran once during setup and never restarted during testing;
the dummy database identity and start time stayed unchanged. Hashes of existing
staging service configurations, identities and start times stayed unchanged.
All disposable containers were removed. The test had no staging credentials,
database volumes, private epoch mounts or published ports.

Fresh Linux amd64 release **`fd4be66575ae6dbef9785321a79a687f418df0b8`** contains
the corrected runner. Source archives, immutable application images, original
participant wheel, manifests, build logs and checksums are retained and independently
verified locally and on the VPS. The entire extracted native source matches its
manifest, and both packaged evaluator file sets exactly match the frozen source.
The packaged coordinator's runner also matches the manifest. Worker identity,
locks, schema source, benchmark/evaluator source and private Compose configuration
remain unchanged from `b4d212d`.

Local verification: 56 focused tests; `make check` passed with 320 tests, eight
native pytest tests skipped, and historical smoke score 3901. The native Compose
drill was executed separately using the frozen Python 3.12.10 operator environment.
No commits were pushed; the original main worktree was preserved.

This closes the requested disposable verification and fresh-release preparation.
It does not close the seven-scenario live acceptance or application rollback/forward
checkpoint. Use the fresh full-commit manifest and image IDs for that later attempt;
older retained releases do not contain these corrections.

See [the complete gate report](report.json) and [the original failed checkpoint](../compatible-v050/README.md).
