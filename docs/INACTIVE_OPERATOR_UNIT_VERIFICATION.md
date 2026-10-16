# Native inactive operator unit verification

Render units from retained operator source and its source-file metadata using `deploy.render_operator_units`. The supplied interpreter must be the installed Python 3.12.10 environment, rather than an absent `/srv/mldsafail/current/.venv`. Missing private configuration remains an activation blocker.

Inside the reviewed native delegated operator wrapper, run:

```sh
python -m scripts.native_operator_unit_verification --units PRIVATE_RENDERED_UNITS --metadata RETAINED_SOURCE_METADATA.json --output NEW_PRIVATE_EVIDENCE_DIRECTORY
```

The runner checks exact source, interpreter, unit hashes and module imports, then invokes `systemd-analyze verify` on inactive unit files. All child commands use durable cgroup ownership, bounded capture and independent cleanup. It installs no units, starts no services and reads no owner credential values. Raw logs and a source-bound private verification journal remain in the new evidence directory. A successful parse and executable check does not satisfy manual backup, restoration, external monitoring or timer activation gates.

Daily recovery assembly and database dumping use the established staging Docker endpoint. Only disposable restoration uses the separately configured `owned_daemon_manifest` in the backup JSON, with `MLDSAFAIL_OPERATOR_DAEMON_MANIFEST` as an explicit fallback. Dedicated-daemon proof cannot clear uncertainty for staging maintenance.

The renderer's per-unit oneshot cgroup template is insufficient for repeat activation when a dedicated manifest binds an earlier parent inode. Before timer activation, provide a persistent delegated operator parent and verify its ownership and timer serialization, or a reviewed native re-registration procedure for every activation. Keep recovery and monitoring timers inactive until this lifecycle gate and their manual acceptance and required external owner inputs pass.
