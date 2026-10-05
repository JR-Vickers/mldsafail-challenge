# Disposable operator interruption acceptance

This is a separate gate from two exited fixture activations and inactive unit
parsing. Root is the sole shared-host operator. Do not install or activate
private-staging timers, or use owner off-host credentials for this gate.

Use a clean retained reviewed source and one new private activation root. Supply
a disposable synthetic restic repository with a valid password and a pre-existing
tiny repository-generated snapshot. Run the actual `recovery-check` job through
`deploy.operator_activation` in a named delegated user unit. Its established
staging socket environment is harmless only if the configuration has no shared
service actions: verify this before execution. Its restic/backend Docker commands
must use the freshly injected owned-daemon manifest.

Record the original unit name and exact driver state before signaling. Wait until
`operator_job.journal_created` is true, the operation journal contains a real
owned daemon context, and the repository check is actually in progress. Kill
only this unit's exact process (SIGKILL); retain the unit so `systemctl show`
continues to report `ExecMainCode=2`, `ExecMainStatus=9`. Never signal the default
Docker daemon, staging containers, or unrelated processes. This requires a
bounded synthetic fixture that keeps the actual check in progress long enough;
do not substitute a fixture-only job or fabricate admission records.

Under a new named delegated unit, run a fixture activation with the same
activation root. It must first reconcile the interrupted driver and effective
job configuration, publish positive whole-daemon/worker shutdown before stopping
creator clients, retire the old operation context without restarting it, and
complete independent job cleanup. Run the second fresh fixture activation after
the first exits. Keep every failed and partial receipt.

Run `python -m scripts.native_repeat_activation_verification` with both
`--receipt` paths, a new private `--output`, and `--interrupted-driver` pointing
to the original driver journal. The verifier also checks source identity,
serialized activation ownership, exact terminal retirement, shared root binding,
actual killed-unit disposition, fresh replacement contexts, and absence of all
registered domains. The process must itself run in an owned delegated operator
unit; preserve its outer cleanup proof independently.

A passing read-only verification report is evidence for this disposable local
job gate only. It does not establish off-host durability, owner password custody,
private epoch restoration, native CPU performance, or timer acceptance against
an approved external repository.
