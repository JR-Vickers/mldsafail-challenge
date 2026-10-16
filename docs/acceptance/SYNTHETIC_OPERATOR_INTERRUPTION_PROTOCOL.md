# End-to-end synthetic scheduled-job interruption

Run `python -m scripts.native_synthetic_operator_interruption --config PRIVATE`
inside the reviewed generic owned native driver controller. This gate uses no
existing private-staging timer, owner repository, password, or webhook.

The exact retained callback source commit, callback SHA256, aggregate native
helper SHA256, source-bound supervisor/auditor/native-protocol reviews, immutable
fixture image and archive SHA256 must be supplied through the normal native
configuration. The immutable fixture image must support the existing Python
activation fixture. A separate freshly created delegated controller and private
state root are required. The generic driver's protected roots/cgroups remain in
force; each inner activation also protects the outer driver root and controller.

Beside `state_root`, supply private `synthetic-interruption-protocol.json`:

```json
{
  "schema": "mldsafail.synthetic-operator-interruption.v1",
  "artifacts_directory": "/ABSOLUTE/PRIVATE/NATIVE/SYNTHETIC/ARTIFACTS"
}
```

That directory contains `restic`, `minio`, and private `artifacts.json` from the
native synthetic S3 fixture retention procedure. Its scope is `synthetic-only`;
`restic_binary_sha256` and `minio_binary_sha256` must match the actual executables.
These exact binary hashes are copied into private result evidence. No package
installation, download, or permissive checksum fallback occurs in the gate.
The installed interpreter is the exact source-bound native interpreter selected
for the outer driver; it is reused for all actual temporary activation units.

The callback generates a private local CA and disposable HTTPS MinIO server,
fresh random synthetic credentials/password and explicitly synthetic custody
copy, one tiny repository-generated public file, an actual restic initialization,
backup, and complete repository check. Temporary activation units have 512 MiB memory and 128-task ceilings; the MinIO
fixture limits Go execution to two threads and a 256 MiB managed-memory target.
The backend is then paused through a
process descriptor after its full birth and owned domain are verified. Pause
intent is durable and the finite original-driver/admission waits bound the pause
phase to 450 seconds; independent cleanup attempts backend continuation first.

A unique temporary delegated user unit runs the real `recovery-check` job. The
observer records the actual admitted journal, exact owned daemon context, pinned
live restic process, and activation birth before sending SIGKILL through a
process descriptor to that activation MainPID only. Its unit uses `KillMode=process`
so the test itself does not cancel creator clients before terminal reconciliation.
The backend resumes immediately. Two separately named, exited fixture units run
under the same activation-root flock; the first must retire the interrupted
context and independently clean the actual operation before provisioning a new
epoch. The read-only verifier checks exact original/replacement evidence and
actual systemd killed-unit disposition and domain absence.

A fresh cleanup-only activation is attempted independently before backend/client
cleanup, even after an earlier failure. Original failures and failed receipts
remain private. Positive callback evidence is published only after independent
cleanup; ambiguous final publication is retried with a negative disposition.
Outer driver terminal cleanup and independent domain absence are required in
addition to the callback result. None of these receipts constitutes off-host
storage or owner password custody acceptance.

For interrupted fixture cleanup, use a new owned native controller with the exact
retained original source and callback identity, and invoke the same module with
`--config NEW_CONTROLLER_CONFIG --cleanup-root ORIGINAL_PRIVATE_FIXTURE_ROOT`.
This mode checks original source authority, stops only the recorded exact owner,
resumes only recorded backend clients, runs cleanup-only fresh activation, and
independently stops backend clients. It publishes a separate cleanup receipt and
never replays the original acceptance sequence or changes an earlier failed gate
into a pass. Any missing or replaced identity remains fenced for explicit repair.
