# Separate maintenance admission control proposal

Status: design proposal only; implementation and acquisition need separate owner
authorization. It does not authorize stopping services or changing admission.

The inspected deployed queue/admission checkout lacks the mutex expected by the
reviewed diagnostic guard. The coordinator continuously recovers/claims jobs; its
`--once` mode is not a live drain command. An empty queue snapshot cannot close
that race. The diagnostic holder's 3,000-second maximum also cannot cover the
5,400-second create ceiling plus audit, inspection and restoration.

A maintenance-specific control must define one owned session identity (backend
PID, birth and unique operation tag), a server-enforced finite lifetime, bounded
acquisition and continuous independent verification. Before acquisition, establish
exact deployed admission/claim/recovery source identities and all restart owners.
Specify whether the control rejects new admissions or blocks them, and how users
recover from bounded contention. Keep web/database/proxy running.

For a zero-pending fence, acquire the compatible lock set and check queued,
claimed and running rows under that fence; abort immediately if any exist.
Do not wait for workers while holding a lock that prevents their completion or
heartbeats. Draining existing work requires a distinct admission-only phase that
allows claims, heartbeats and recovery to finish, a declared drain deadline and
an atomic transition to the zero-pending fence. Never infer completion from
expired timestamps or erase pending jobs.

Retain and verify fence ownership continuously through the exact coordinator
stop and confirmation that every scheduler/restart owner is excluded. Specify an
atomic handover if the database fence is released after stop; otherwise its finite
lifetime must cover the entire declared operation and cleanup with margin.
Uncertain stop, identity drift, connection loss, lock loss, expiry or timeout must
abort before operation start. After possible launch, first positively terminate
all owned operation resources and obtain fresh postflight; ambiguous launches
require manual reconciliation before any scheduling restoration.

Release only the owned connection, matching PID/birth/tag. Verify lock/backend
absence and control-client termination. Restoration must bind original container
restart policies, exact unit states and exact commands, and verify each restored
identity. Never release exclusion merely because a client timed out.

Required tests before a later approval: concurrent admission/claim/recovery and
heartbeat behavior; nonempty queue rejection; drain-to-fence race; lock contention;
connection loss and server expiry; exact coordinator identity/stop failure;
restart-owner interference; lost acknowledgement; partial launch and owned-resource
termination; cancellation/release absence checks; restoration interruption; and
rejection of proposal-state packets at every execution gate. Use disposable local
infrastructure and synthetic jobs under a separately authorized protocol. This
milestone implements none of that control and acquires no locks.
