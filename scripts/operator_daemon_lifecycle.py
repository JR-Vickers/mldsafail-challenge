"""Positive isolated-daemon shutdown before creator cancellation and inventory."""
from pathlib import Path
import fcntl
import os
import uuid

from deploy import owned_client, owned_daemon


def lock_daemon(manifest):
    """Hold for the entire consumer run and cleanup, across distinct run roots."""
    base = Path(manifest['provisioning']['base']['path'])
    if owned_daemon._private_directory(base) != manifest['provisioning']['base']:
        raise RuntimeError('Dedicated daemon provisioning root changed')
    descriptor = os.open(base/'operator.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise RuntimeError('Private exclusive daemon operator lock required')
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def bind(journal, publish):
    manifest = owned_daemon.load_manifest()
    owned_daemon.verify_environment(manifest)
    previous = journal.get('dedicated_daemon')
    if previous is not None and previous != manifest:
        raise RuntimeError('Run is bound to a different dedicated daemon epoch')
    journal['dedicated_daemon'] = manifest
    publish()
    return manifest


def settle(journal, clients, root, publish):
    """Fail closed; independent creator stops still run after barrier failure."""
    errors = []
    manifest = journal.get('dedicated_daemon')
    pending = journal.get('daemon_reconciliation')
    receipt = pending.get('receipt') if isinstance(pending, dict) else None
    attempt = pending.get('attempt') if isinstance(pending, dict) else 'operator-' + uuid.uuid4().hex
    try:
        if manifest is None:
            raise RuntimeError('Durable dedicated daemon binding missing')
        if receipt is None:
            receipt = owned_daemon.shutdown_barrier(manifest, evidence_directory=Path(root), attempt_id=attempt)
        if receipt['shutdown_proven'] is not True:
            raise RuntimeError('Dedicated daemon shutdown remains unproved')
        journal['daemon_reconciliation'] = {'attempt': attempt, 'receipt': receipt}
        publish()  # Positive barrier must survive loss after restart publication.
    except Exception as error:
        errors.append({'step': 'daemon_barrier', 'error_type': type(error).__name__})
    for entry in clients:
        try:
            owned_client.stop(entry)
        except Exception as error:
            errors.append({'step': 'creator_stop', 'error_type': type(error).__name__})
    if not errors:
        try:
            import os
            path = os.environ.get('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST')
            if not path:
                raise RuntimeError('Explicit operator daemon manifest path required')
            refreshed = owned_daemon.restart_and_refresh(manifest, receipt, manifest_path=path,
                            client_entries=clients, evidence_directory=Path(root), attempt_id=attempt)
            journal['dedicated_daemon'] = refreshed
            journal.setdefault('daemon_barriers', []).append(receipt)
            journal.pop('daemon_reconciliation', None)
            publish()
        except Exception as error:
            errors.append({'step': 'daemon_restart_publication', 'error_type': type(error).__name__})
    return errors
