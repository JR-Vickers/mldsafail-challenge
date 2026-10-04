# Affected disposable recovery power-loss protocol

This gate exercises the current owned-daemon recovery API in a new QEMU overlay.
The original protected VM disk, firmware variables, and earlier private receipts
remain unchanged. No shared VPS, staging epoch, benchmark measurement, public
endpoint, owner credential, or paid service participates.

Before execution retain clean source, independent source/protocol review packet,
source bundle hash, official base-image identity, protected disk/firmware hashes,
resolved PostgreSQL image ID/archive SHA, rootless executable hashes, Docker
server/API identity, guest UID, Python version, kernel identity, and boot IDs.
All SSH exposure is loopback-only with the existing task-owned synthetic key.

1. Boot the new overlay and prove healthy multi-user boot. Provision an isolated
   user-1000 rootless daemon, delegated operator domain, and entire worker domain
   using the source-bound native driver. Protect the VM's bootstrap daemon.
2. Create a tiny tmpfs PostgreSQL database containing one repository-generated
   public small-profile instance. Retain an immutable custom-format dump and its
   hash. Record exact synthetic schema/payload/image identities and a durable
   paused pre-loss boundary. This is not an acceptance pass.
3. Hard-kill only the exact owned QEMU process, without guest shutdown. Reboot
   the overlay and require a changed boot ID and the exact old unit inactive.
4. Keep old kernel authority fenced. Provision a new dedicated daemon and fresh
   data roots; never re-register old Docker roots, cgroups, or reference costs.
   Restore the immutable dump into a fresh tiny tmpfs database. Verify schema,
   public payload, dump/image identity, and source identity.
5. Require independently complete post-restoration client/resource cleanup and
   native driver daemon/whole-worker termination. Collect private raw journals
   independently of exact VM cleanup, prove every owned VM stopped, and rehash
   the protected disk/firmware. Preserve every failed or partial attempt.

A pass proves actual changed-boot loss followed by logical synthetic database
restoration using fresh current authority. It does not prove preservation of old
Docker container IDs, restoration of a real private epoch, approved off-host
storage, independent owner password custody, or benchmark-accounting acceptance.
Earlier primitive power-loss receipts remain historical evidence of their own
source and protocol.
