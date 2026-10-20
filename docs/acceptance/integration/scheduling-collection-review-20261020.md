# Owner-console scheduling collection — partial review

The owner ran the v2 collector in the existing root console and authorized private
handoff through the application account. Three files were retrieved using the
recorded SSH identity and pinned host key, with matching remote/local hashes and
private ownership/modes. Original root files were preserved. Evidence is retained
under `$HOME/.config/mldsafail-production/scheduling-review-20261020-v1`.

The collection reports complete and contains 353 path entries. Every raw-section
hash verified. Subsequent read-only inspection rechecked 310 regular-file hashes
without drift. Root and application-account crontabs are absent. The at service,
atq and all three inspected spool locations are absent. These facts do not
constitute a complete reviewed receipt or verified scheduling exclusion.

The host-check and database-backup timers are enabled and active; their services
were inactive at inspection. The host-check script matches repository source.
The deployed backup script matches retained commit
`fe44c296089c41f98f5430a7b287e7f16741d94a`, rather than the current checkout.
Both timer settings were preserved. Backup provisioning remains deferred.

The pasted collector is the committed source plus one trailing newline. Its
self-hash matches the collection and the exact pasted source is retained, but it
differs from the committed hash required by the execution validator. Do not edit
the collected evidence or silently normalize that identity into a passing receipt.
A subsequent exact-source collection must bind the reviewed external script paths.

All-path/reference classification and maintenance dispositions remain incomplete.
No privileged receipt is issued; `scheduling_exclusion_verified` remains false.
Drain compatibility, capacity, delegation, approved commands and restoration
remain outstanding as described in the [maintenance handoff](maintenance-inspection-v2-20261020.md).
Only private evidence retrieval and read-only inspection occurred; no service
changes, lock acquisition, database writes, evaluation or operation-bundle transfer.
