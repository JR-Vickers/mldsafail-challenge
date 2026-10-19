# Bounded diagnostic findings — 2026-10-19

**Decision: unresolved findings; no full-rehearsal approval packet.** The fresh
native admission attempt failed strict SSH server-identity verification before
its remote command executed. Neither diagnostic generation started. Existing
remote deployment identities, jobs, resources and cleanup state were not freshly
verified; historical receipts must not be substituted for current observations.

## Implemented and verified

Local checkpoints `a29c553339a5c499b07cedecc1205a5fb4ede942` and `544dead`
implement the separate no-epoch controller/callback, supervisor deadlines,
identity-bound cancellation/cleanup, durable consumed-slot ledger, actual artifact
validation, canonical fixture restoration, unchanged sequential public worker,
rendered monitor integration, sanitized HTTP/component instrumentation, frozen
historical scheduler execution and corrected final load phases. Production
fresh-epoch requirements remain intact. Compose rendering overrides every frozen
substitution and checks effective images/environments before startup.

Independent executable-source review passed after correcting identified defects.
All 22 focused native diagnostic tests passed independently. Final `make check`
passed: 1,170 tests, 14 skipped, plus eight MLWE contract checks. Real disposable
local PostgreSQL fixture round trips passed separately. These checks establish
local engineering behavior, not native performance or release acceptance. Actual
native artifact/configuration packet review did not complete: admission stopped
before obtaining current host identity and inventory.

## Failed admission and budget

The sole initial SSH attempt to the retained VPS address returned 255 with
`REMOTE HOST IDENTIFICATION HAS CHANGED` and empty stdout. The offered ED25519
fingerprint was `SHA256:hUWnKjbrr1VltVIJ7tldViMnUKi+xIzF4qD3P3BcecQ`.
This is an unverified observation, not an accepted replacement identity. The
trusted known-hosts entry was left unchanged; no bypass or retry was used.

The durable initial-preflight start preceded SSH. Independent review matched
payload/transport hashes and verified rejection before remote execution. The
start-bound independent receipt explicitly does not claim remote identity or
existing remote resource absence was inspected. Preflight terminal status is
`complete:false`, `cleanup_verified:true`; elapsed 32.858124166 seconds, rounded
charge 33 seconds. Existing debit 900 + new preflight charge 33 = **933 seconds**.
Baseline and post-fix slots remain unstarted and fenced by failed preflight.
Do not reset the ledger or repeat admission under this consumed slot.

Private evidence root:
`results/production-diagnostics/20261019/native-session/`.
It retains the exact bootstrap payload, transport stdout/stderr and hashes,
immutable budget start/terminal, independent cleanup receipt, check log and
canonical fixture. No credentials are published here.

## Measurement dispositions

| Question | Disposition | Required evidence |
|---|---|---|
| Monitor failures and owned-client/Docker/import/connect/query overhead | Unmeasurable in this attempt | Admitted native idle/loaded monitor runs with component classifications |
| HTTP authentication/readiness latency and failures | Unmeasurable in this attempt | Comparable restored-fixture idle/loaded HTTP and sanitized server timing records |
| Historical scheduler elapsed time and dispatch lag | Unmeasurable in this attempt | Exact frozen historical scheduler invocation and partial/unfinished records |
| Corrected final idle/loaded pacing and latency acceptance | Unmeasurable in this attempt | Both complete 1,560-request phases with valid observations and pacing |
| Worker contention/prefix comparability | Unmeasurable in this attempt | Sequential unchanged worker invocation/prefix journals |

No new monitor/application mechanism was established. No evidence-based
monitor/application fix, image rebuild or baseline/post-fix comparison was made.
The existing pacing correction remains locally tested and natively unvalidated.

## Cleanup, retention and next evidence

No native service, daemon, worker, monitor unit, volume or source environment was
created by this attempt; independent transport evidence establishes that limited
claim. Existing native resources were neither changed nor freshly audited.
The local disposable PostgreSQL process was stopped; PID file, socket and TCP
listener absence were verified before deleting only its inventoried temporary
root. The canonical private fixture/export survives unchanged, SHA-256
`04fa195ff541d8c8dc2199152f610054e984836fca4ec365c5765f7833b335b0`.
Its fixed expiry remains **2026-10-20 07:20:54.815946 UTC**. Do not recreate or renew
it for this investigation. Local cleanup intent/receipt and check evidence remain
private. Retained unresolved evidence has owner **jarrett**, review date
**2026-10-26**. No remote caches were removed without current ownership proof.

The next required evidence is an independently authenticated VPS identity, such
as a provider-console fingerprint and confirmation of whether the machine was
replaced. Only after identity reconciliation can a revised bounded continuation
explicitly address the consumed failed preflight, preserve the 933-second debit
and original fixture expiry, and obtain current ownership/resources plus exact
artifact review. The current ledger correctly rejects continuation. This report
does not authorize a retry, new fixture, private epoch or full rehearsal.

Additional spending: $0. No notification delivery, public activation, publication,
recruitment or Measurement 0.6.0 adoption occurred. Backups remain a separate
workstream. Commits remain local and unpushed.
