# Protected runtime preparation verification — 2026-10-21

This verifies the blocked source checkpoint `396d1b6`, not an installation.

- Final `make check`: **1,493 passed, 45 skipped**, 12 existing warnings;
  separate frozen 0.5.0 contract suite: **8 passed**.
- Focused checks: **105 passed**; disposable loopback PostgreSQL: **46 passed**.
- Disposable Linux: eight inert control cases passed. `--init` reaped orphaned
  children; bounded tmpfs exercised file/volume enforcement. No actual VPS
  delegation, systemd abnormal-exit cleanup or production filesystem was tested.
- All named disposable fixture containers were absent after cleanup.
- Changed Markdown: 74 local links checked, none missing; `git diff --check` passed.
- Independent source review found no new unsafe execution path in the blocked
  checkpoint. It explicitly did **not** approve deployment or native acceptance.

Immutable public source-only records (166 bound source/configuration-definition
files, no private configuration contents):

| Record | SHA-256 |
| --- | --- |
| [Bootstrap source review](protected-runtime-source-review-v2.json) | `34d5f8f16d62cc331bb186eacb619ae70558a83a2a808de2181d5f1ddb8c5497` |
| [Source manifest](protected-runtime-source-release-v2.json) | `514a2be0dc93fd4777e05f0cd207c8f89dfe4f107afd1b76a225e3326152661e` |

The source manifest is not a built native runtime/coordinator artifact. It binds
source and lockfile bytes, not installed dependency/image/configuration identities.
The review packet has no deployment commands because host inspection is incomplete.

Private evidence is retained in
`results/integration-evidence/protected-runtime-20261021/`:

| Record | SHA-256 |
| --- | --- |
| Initial raw host collection | `c7dfb40561aa03a92e48cbd10c2eb24df967fb8c0ba58ca4ccf47d3e36b91a01` |
| Refreshed raw host collection | `84b7f20a2248a9435b204dd06ad53eba21cb29963386bff7a053e32771d886bf` |
| Refreshed collector source | `3f81ea33168f06c8dc63da8080d732e041495c1f63f76170f9652dea19b7834a` |
| Host-bound blocked packet | `e7fa8e0292f0a96c7773b74308a45043cbdb2fdc982957fac5a2ee8c11e263f4` |

Collection succeeded twice through the pinned existing identity. Private packet
commands are empty and it grants no execution authority. Raw reports, initial
fixture setup failures and successful rerun logs are retained together. No bulky
trial archive was created; no active installation or historical record was changed.
The [readiness disposition](protected-runtime-readiness-20261021.md) lists remaining
implementation work, owner-assisted facts and separate authorization gates.
