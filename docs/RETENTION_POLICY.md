# Lean-launch retention

Adopted by the owner on 2026-10-19, with immediate cleanup authorized. This is the
current policy for deployment trials and infrastructure rehearsals. It supersedes
older instructions to retain every trial environment, all failed material, all
source contexts, or every image archive indefinitely. Dated acceptance receipts
remain historical statements; do not rewrite their original outcomes.

## What survives a trial

Keep a small permanent private record of its purpose, source/configuration and
image identities, protocol, result (including failure or incompleteness), relevant
logs, cleanup disposition, and a manifest of removed and retained artifacts.
Keep secrets private; public summaries contain no credentials, private inputs or
raw sensitive evidence. A failed trial must never become a passing record because
its bulky files were removed.

After the question has been answered, delete stopped trial Docker stores,
rebuildable caches, temporary files, redundant source copies and obsolete image
archives. A trial is answered when its declared test has a recorded disposition;
that may be a failed gate or a useful negative result. It need not have passed.
Retain existing reference/source identities needed to explain that disposition.
Do not create another large archive simply to replace every deleted directory.

Keep the running deployment and one verified compatible rollback, including its
required source/configuration, immutable images or verified image archives and
recovery instructions. Do not delete an active mount, active process workspace,
current symlink target, shared live Docker store, private staging database or
production configuration. A trial image still required for the next authorized
investigation is a named temporary retention exception, not an extra deployment.

Unresolved failures retain only the evidence needed for their open question: for
example relevant logs and one offline database snapshot, rather than a whole
stopped daemon store. Each exception records its question/owner and review date.
Revisit at question closure or within seven days, whichever comes first; an
expired date prompts review, never blind deletion. Unknown ownership or uncertain
scientific relevance means preserve and record an exception until classified.

Scientific benchmark evidence is separate. Keep private inputs, verified outputs,
reference costs, audit/seal data and provenance needed to substantiate retained
scientific results. Deployment-trial metadata alone is not sufficient to erase
that evidence. This policy does not change scoring, worker/evaluator bytes,
benchmark restrictions or adopted scientific contracts.

## Safe cleanup

Inventory exact paths and identities before removal. Prove the selected trial is
stopped, reconcile current jobs/processes/mounts, and hold its existing operation
lock where one exists. Preserve the compact record before deletion, outside the
removed tree. Use an explicit path allowlist, refuse symlink/root replacement and
mount crossings, and retain a deletion intent so interruption is recoverable.
Do not use broad Docker pruning against the shared live daemon.

Unlink duplicate source files without modifying shared file contents or modes.
Check that required Git history remains available before deleting source copies.
Keep original lifecycle manifests immutable; record retirement separately and
prohibit restarting deleted generations. Verify removed paths, free space,
retained evidence and unchanged live deployment after cleanup. Report partial
failures rather than claiming a completed deletion.

Cleanup is maintenance. It does not consume a scientific evaluation or disposable
rehearsal generation, reset a diagnostic budget, authorize a fresh epoch, reconnect
notifications, activate production, or require off-host backup setup. Existing
ownership and resource safety checks still apply. Backups remain deferred.
