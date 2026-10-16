# Terminal build-cache retirement

This protocol reclaims only disposable owned build daemons' volatile `root_dir`
stores after immutable exported images and their receipts have been retained.
It does not prune the staging daemon, delete failed-generation evidence, or
remove source, configuration, journals, image archives, manifests or exec roots.
It establishes no backup or production acceptance.

Use `scripts.retire_build_cache` only from a clean reviewed checkpoint through
`native_operator_unit` in a fresh delegated operator service. Freeze the private
protocol, exact helper/interpreter/rootlesskit identities and dependency inventory
before execution. Reprove current terminal driver/operator cleanup, every recorded
process birth and cgroup, socket absence, and inactive owned units. Hold the
original provisioning lock throughout each retirement.

Require passing build receipts, their complete image exports, every imported
image archive, exact original configuration and cleanup journals. Verify all
checksums before mutation. Require the registered canonical cache device/inode
and owner, with retained artifacts outside it. Inspect accessible process mount
tables and reject mounts at or below the cache. Record inaccessible mount-table
counts as an explicit inspection limit.

The bounded owned rootlesskit child must have the original exact UID/GID mappings:
namespace root maps to host UID/GID 1000; namespace IDs 1–65536 map to host
100000–165535. Bind this host-specific protocol; other mappings require a new
review. The child independently checks mappings, namespace separation, mounts,
complete no-follow traversal, and one filesystem before descriptor-safe removal.
Only the registered `root_dir` is removed. Publish the intent before launch and
completion after proving absence. Any failure preserves partial evidence and
fences dependent execution. Retired daemons must never be restarted; retain the
separate `CACHE_RETIRED.json` marker with the untouched lifecycle manifests.

Independently inspect final cache absence, namespace/operator/client cleanup,
retained archive checksums and protected service identities. Observe the existing
5-GiB disk floor before any subsequent benchmark or rehearsal. Do not substitute
cache retirement for failed epoch or application acceptance.

The first native retirement attempt refused during complete traversal, before any
removal, because a special cache entry was present. Preserve that failure. A new
`action: "inspect"` protocol performs only mapped, no-follow classification and
publishes each special node's relative path, device, inode, full mode and `rdev`.
It removes nothing and cannot publish a retirement marker. Obtain independent
classification before a new `action: "retire"` protocol declares the complete
exact `special_entries` set for each root. Equality is checked during traversal
and again immediately before removal. Reject duplicate, absolute or escaping
paths, changed identities, new nodes, mounts, cross-device entries and unreadable
traversal. Special entries are never opened; only the safe tree-removal routine
may unlink individually reviewed entries. There is no automatic type-wide exception.
