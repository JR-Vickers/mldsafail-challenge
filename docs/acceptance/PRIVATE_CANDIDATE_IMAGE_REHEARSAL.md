# Private candidate image rehearsal

`python -m candidate_runtime.rehearsal --config PRIVATE_CONFIG` is a same-process
owned-native-driver consumer. Its source tests establish implementation behavior;
only native execution can establish the corresponding application gate.

The parent of the driver state directory must contain both the ordinary
`v060-protocol.json` and `candidate-image-protocol.json`. The latter has schema
`mldsafail.private-candidate-image-protocol.v1` and paths `worker_artifact`,
`prerequisites`, and `application_artifact`. All are protected private receipts.
The application receipt must bind the exact operator source commit and an inert,
rootless UID0 immutable application image. Include its image archive in the
owned driver's `additional_images`. The primary image is the independently
gated worker. No worker rebuild, context replacement, threshold change, contract
adoption, or production-default change is performed by this callback.

The callback prepares fresh audited references and a separate owned daemon for
application containers and PostgreSQL. Only public source and a socket-only
shared directory enter the application containers. Gateway ownership records,
request evidence, the epoch, reference authority and host measurement controls
remain on the host. Gateway dispatch and native evaluation run on the main
thread. The participant wheel is installed into a fresh environment, and its CLI
submits an explicitly selected 0.6.0 job to the loopback-only image application.
The coordinator reads its public Git repository from the controlled work mount.
The host independently checks the signed result, accepted database record,
authentication and separate default 0.5.0 and candidate 0.6.0 leaderboards.

An encrypted off-host recovery gate is not implied. The callback retains a
custom-format dump, restores it into a fresh disposable database, and verifies
accepted result identity. It also restarts the exact application image and checks
leaderboard preservation. This is explicitly an application restart, not a
rollback: `application_rollback_passed` and
`independent_recovery_acceptance_passed` remain false. Those separate launch gates
must be supplied by their own native acceptance routines.

Every inner context must complete the owned driver's whole-daemon cleanup;
application disposition publication and host environment restoration are
independent cleanup steps. Retain failed journals and negative dispositions.
Never interpret a source review or receipt with any incomplete required parent
gate as public launch approval.
