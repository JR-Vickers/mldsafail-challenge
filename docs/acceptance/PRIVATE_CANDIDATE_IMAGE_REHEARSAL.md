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
custom-format dump, restores it into a separate network-none PostgreSQL
container, and compares every ORM table and public schema to the original
disposable database. It also restarts the exact application image and checks
leaderboard preservation. This is explicitly an application restart, not a
rollback. Without a separately identified prior candidate image,
`application_rollback_passed` remains false.
`independent_recovery_acceptance_passed` remains false in either case. If `rollback_application_artifact` and `rollback_application_source_commit`
are supplied together in the image protocol, the callback additionally validates
a separately source-bound prior inert candidate image. Its source commit and
immutable image must both differ from the forward image; a frozen staging image
cannot substitute for that candidate artifact. Both archives must be preloaded.
The callback stops the current web image, starts the prior image, verifies
authentication, default/candidate cohorts and all retained database state, then
forwards the original image and repeats verification. It invokes no migrations
and never restores the original database. Only API-token `last_used_at` is
normalized during these authenticated switch comparisons; fresh restoration
compares every field exactly. Actual rollback acceptance stays false unless this
entire native sequence completes. Independent recovery acceptance still requires
its own native gate.

Every inner context must complete the owned driver's whole-daemon cleanup;
application disposition publication and host environment restoration are
independent cleanup steps. Retain failed journals and negative dispositions.
Never interpret a source review or receipt with any incomplete required parent
gate as public launch approval.
