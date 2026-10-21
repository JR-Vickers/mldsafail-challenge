# Protected-runtime owner-console collection

This procedure collects missing facts only. It grants no installation, scheduling,
mount, fixture or epoch authority. Use the existing VPS root console. Raw outputs
can contain scheduling commands and must remain private. Do not post them in Git.

Use the reviewed source checkout containing
[scripts/workload_owner_collection.py](../scripts/workload_owner_collection.py),
[deploy/privileged_scheduling.py](../deploy/privileged_scheduling.py) (the `deploy` namespace directory needs no `__init__.py`). Verify both collector hashes against the reviewed
source packet before invoking them; do not use an unreviewed remote script.
From that checkout, with an unused private output directory on existing storage:

```sh
umask 077
mkdir -m 700 /root/mldsafail-owner-observation-20261021
sha256sum scripts/workload_owner_collection.py deploy/privileged_scheduling.py
python3 -m scripts.workload_owner_collection \
  --raw-output /root/mldsafail-owner-observation-20261021/raw-1.jsonl \
  > /root/mldsafail-owner-observation-20261021/collection-1.json
sha256sum /root/mldsafail-owner-observation-20261021/raw-1.jsonl \
  /root/mldsafail-owner-observation-20261021/collection-1.json
```

The all-account collector inventories every account's crontab and user-manager
identity, loaded active user managers, vendor/local system and user units,
timers/sockets/paths, execution references and cron/at spool paths. It is bounded
at 128 accounts, 180 seconds, 256 KiB per command, 1 MiB per file and 2,048
entries per root. Any account bound, timeout, error or truncation is a blocker;
`readiness` is always false until separate reference review. Missing managers
are observations, not evidence that their persistent units cannot start later.
A nonzero command cannot silently pass collection. Keep failed attempts.

Privately review the raw unit/cron sources and every script they reference.
Record manager, account/UID, exact original settings, path/hash, rationale,
computational/retained disposition and outgoing references for each item.
Resolve relative paths against the actual working directory and environment;
do not guess or execute scripts. Repeat the collector with unused output files
and `--reviewed-path /absolute/script` for every newly identified literal script,
recursively until closure. Dynamic/unresolved references block readiness.
At jobs need their individually identified `at -c JOB_ID` output and hashes;
container restart policies need the actual owner's daemon inventory, including
root-owned and other-user daemons. The new collector does not close those gaps.
Do not remove jobs or change restart policies to simplify collection.

Separately provide read-only identities and permissions for the actual user
manager, delegated parent and each cgroup ancestor: device/inode/UID/mode,
controllers, subtree allowances, memory/swap/PID/CPU limits and control-file
permissions. Bind the actual rootless daemon UID map and coordinator image UID.
Do not change a shared Docker daemon or retained-service ancestor.

For storage, identify an existing compliant persistent ext4/xfs filesystem first.
Record `findmnt` source/target/type/options, mount identity, ownership, capacity,
backing-device free bytes and preservation inventory. Missing compliant storage
requires a separately reviewed exclusively created ext4 backing-file proposal of
at most 1 GiB, with noexec/nosuid/nodev, exact paths, ownership and reversal. This
collection procedure authorizes no loop device, file allocation, format or mount.
Keep the 1 GiB MemAvailable floor and 5 GiB backing-space floor; refresh those
volatile facts at eventual authorized admission. Infeasibility is a blocker.

Return only private evidence references/hashes and a redacted classification
summary to the deployment review. No installation authorization should be
requested until the complete executable proposal, rollback and coverage exist.
