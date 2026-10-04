# Isolated ARM64 hard-power-loss rehearsal

On an Apple Silicon host with QEMU and hdiutil, run:

```sh
python -m deploy.qemu_recovery_powerloss --output NEW_PRIVATE_ABSOLUTE_DIRECTORY
```

The operator downloads the official dated Ubuntu Noble ARM64 cloud image and
checks its published SHA256, creates a new 16-GiB overlay disk, task-only SSH key
and NoCloud seed, and boots one 2-GiB VM using HVF. SSH binds only 127.0.0.1 on an
ephemeral port, with an isolated known-hosts file. No staging credentials, mounts,
ports or resources enter the VM. Installation changes occur only inside the guest.
Ubuntu's Python 3.12 runs the standard-library restoration helpers; this gate does
not execute benchmark workers or establish frozen evaluator compatibility.

The guest installs rootless Docker, creates one migration-dependent dummy Compose
project, durably records baseline and maintenance intent, and stops original
application containers. The host SIGKILLs its exact owned QEMU process without
guest shutdown, then restarts the same disk. Reconciliation checks changed boot ID,
unchanged original application/migration container IDs, single migration sentinel,
independent repeated cleanup and zero owned fixture resources. The host always
stops its owned QEMU processes and retains disks, logs and raw evidence privately.

A source checksum/guest archive checksum binds the actual uploaded helper files;
a Git identity alone does not describe uncommitted source. Retain interrupted
attempts separately. Report a pass only after guest reconciliation and host-owned
process cleanup succeed. This is a synthetic local recovery gate, not off-host
production recovery or permission to power-cycle staging.

The VM-only fstab override names verified image partitions `/dev/vda16` and
`/dev/vda15` directly to avoid a post-fsck label-symlink discovery race. Readiness
requires `multi-user.target` active after both boots. The separate transport gate
creates a fresh fixture/journal, kills its exact owned local SSH client after the
durable maintenance boundary, reconnects without reboot, verifies unchanged boot
ID, and audits cleanup/identity/migration invariants. Raw guest evidence is exported
before stopping the VM. These two gates must have distinct outcomes.
