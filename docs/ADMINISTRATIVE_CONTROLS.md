# Private operator revocation

The trusted local `mldsafail-admin` command supports `revoke-token` and
`cancel-submission`. These operate through operator-held database access and
require `--github-subject` to identify an existing administrator for audit
attribution, plus `--id` for the exact database record. The subject is not an
authentication mechanism: keep database access within the approved operator
scope. No public administrative endpoint is added.

Token revocation rejects later authentication. Queued cancellation closes the
queued job; running cancellation requests termination and preserves its lease
until coordinator cleanup/reconciliation. Repeating either already reconciled
operation makes no duplicate administrative audit event. Existing participant
ownership checks remain intact. No schema or benchmark semantics change.

`bootstrap-admin --github-subject SUBJECT --login LOGIN` retains its existing
role-provisioning behavior. Provision owner roles only within an explicitly
approved environment. Native acceptance uses disposable synthetic identities.
Production activation remains subject to the launch ledger's owner decisions.

Run `tests/test_native_postgres_admission.py` only through the reviewed owned
native PostgreSQL acceptance driver, which creates and removes a fresh explicitly
named disposable database and preserves failed evidence. Local SQLite tests do
not replace that native gate.
