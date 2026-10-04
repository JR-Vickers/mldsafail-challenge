"""Positive isolated-daemon shutdown before creator cancellation and inventory."""
from pathlib import Path
import uuid

from deploy import owned_client, owned_daemon


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
    receipt = None
    attempt = 'operator-' + uuid.uuid4().hex
    try:
        if manifest is None:
            raise RuntimeError('Durable dedicated daemon binding missing')
        receipt = owned_daemon.shutdown_barrier(manifest, evidence_directory=Path(root), attempt_id=attempt)
        if receipt['shutdown_proven'] is not True:
            raise RuntimeError('Dedicated daemon shutdown remains unproved')
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
            publish()
        except Exception as error:
            errors.append({'step': 'daemon_restart_publication', 'error_type': type(error).__name__})
    return errors
