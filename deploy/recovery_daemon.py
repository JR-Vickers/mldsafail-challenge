"""Explicit isolated-daemon contexts and durable operator RPC repair.

Shared staging maintenance is never authorized by a disposable daemon receipt.
Callers serialize their complete operation and retain failed private evidence.
"""
from contextlib import contextmanager
import os
import fcntl
import stat
from functools import wraps
from pathlib import Path
import threading
import uuid
from deploy import owned_client, owned_daemon

_ENVIRONMENT = ('DOCKER_HOST', 'DOCKER_CONTEXT', 'MLDSAFAIL_OPERATOR_DAEMON_MANIFEST', 'MLDSAFAIL_CPU_DAEMON_MANIFEST')
_CONTEXT_LOCK = threading.RLock()


@contextmanager
def operation_lock(path):
    """Serialize complete consumers sharing one provisioned daemon, across processes."""
    if path is None:
        yield
        return
    manifest = owned_daemon.load_manifest(path)
    with provision_lock(manifest['provisioning']):
        yield


@contextmanager
def provision_lock(provisioning):
    """Lock the fresh daemon base before manifest registration and through teardown."""
    base_identity = provisioning['base']
    base = Path(base_identity['path'])
    if owned_daemon._private_directory(base) != base_identity:
        raise ValueError('Dedicated daemon provisioning root changed')
    # A whole-operation process-local lock also prevents environment races. Nested
    # verification/cleanup reuse the already-held flock without releasing it.
    with _CONTEXT_LOCK:
        active = getattr(operation_lock, '_active', {})
        key = (os.getpid(), str(base))
        if key in active:
            yield
            return
        descriptor = os.open(base / 'operator.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                    info.st_mode & 0o077 or info.st_nlink != 1):
                raise ValueError('Private exclusive daemon operator lock required')
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if owned_daemon._private_directory(base) != base_identity:
                raise ValueError('Dedicated daemon provisioning root changed during locking')
            active[key] = descriptor
            operation_lock._active = active
            try:
                yield
            finally:
                del active[key]
        finally:
            os.close(descriptor)


def locked_config_operation(function):
    @wraps(function)
    def wrapped(config, *args, **kwargs):
        backup = config.get('backup', config)
        selected = backup.get('owned_daemon_manifest') or os.environ.get('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST')
        with operation_lock(selected):
            return function(config, *args, **kwargs)
    return wrapped


@contextmanager
def scope(path, *, verify=True):
    path = Path(path)
    manifest = owned_daemon.load_manifest(path)
    if not manifest['unit'].startswith('mldsafail-owned-daemon-'):
        raise ValueError('Operational recovery requires its own isolated daemon, separate from accounting')
    if os.environ.get('MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT') != manifest['provisioning']['operator_domain']['path']:
        raise ValueError('Recovery operator domain differs from provisioned daemon ownership')
    with _CONTEXT_LOCK:
        original = {key: os.environ.get(key) for key in _ENVIRONMENT}
        try:
            os.environ['DOCKER_HOST'] = 'unix://' + manifest['socket']
            os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST'] = str(path)
            for key in ('DOCKER_CONTEXT', 'MLDSAFAIL_CPU_DAEMON_MANIFEST'):
                os.environ.pop(key, None)
            if verify: owned_daemon.verify_environment(manifest)
            yield manifest
        finally:
            for key, value in original.items():
                if value is None: os.environ.pop(key, None)
                else: os.environ[key] = value


def bind(record, path):
    with scope(path) as manifest:
        key = owned_daemon.fingerprint(manifest)
        contexts = record.setdefault('daemon_contexts', {})
        contexts.setdefault(key, {'manifest': manifest, 'manifest_path': str(path)})
        return key


def _positive(barrier, manifest, attempt):
    if (not isinstance(barrier, dict) or barrier.get('schema') != 'mldsafail.owned-daemon-barrier.v1' or
            barrier.get('shutdown_proven') is not True or barrier.get('errors') != [] or
            barrier.get('attempt_id') != attempt or barrier.get('daemon_epoch') != manifest['epoch'] or
            barrier.get('daemon_manifest_sha256') != owned_daemon.fingerprint(manifest)):
        raise ValueError('Exact versioned positive daemon barrier required')


def repair(record, directory, publish):
    """Prove old epoch dead before creator cancellation/restart; retain uncertainty."""
    errors = []
    pending = {}
    corruption = record.get('corrupt_fields', {})
    if (not isinstance(corruption, dict) or 'invalid_corrupt_fields' in record or
            any(field in corruption for field in ('clients', 'daemon_mutations'))):
        return [{'step': 'retained_corrupt_creator_authority', 'required': 'manual_creator_authority_reconciliation'}]
    for field in ('daemon_mutations', 'clients'):
        value = record.get(field, [])
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            return [{'step': 'corrupt_' + field, 'required': 'manual_creator_authority_reconciliation'}]
    for mutation in record.get('daemon_mutations', []):
        resolution=mutation.get('resolved_by_barrier')
        if isinstance(resolution,dict) and resolution.get('terminal_retirement') is True:
            try:
                from deploy.recovery_terminal import validate_retirement
                validate_retirement(record,mutation['daemon_context'])
            except BaseException as error:
                errors.append({'step':'terminal_retirement_invalid','error':type(error).__name__})
            continue
        if mutation.get('acknowledged') is True or resolution:
            continue
        key = mutation.get('daemon_context')
        if key is None:
            errors.append({'step': 'shared_maintenance_uncertainty', 'required': 'primary_manual_quiescent_repair'})
        else:
            pending.setdefault(key, []).append(mutation)
    if record.get('terminal_no_restart') is True:
        return errors + [{'step': 'terminal_context_unproved', 'context': key} for key in pending]
    for key, mutations in pending.items():
        try:
            context = record['daemon_contexts'][key]
            manifest = context['manifest']
            if owned_daemon.fingerprint(manifest) != key:
                raise ValueError('Recovery daemon context identity changed')
            attempt = 'recovery-' + key[:32]
            proof_path = Path(directory) / (attempt + '-rpc-repair.json')
            with scope(context['manifest_path'], verify=False):
                if proof_path.exists():
                    proof = owned_daemon.read_private_json(proof_path)
                    if (proof.get('schema') != 'mldsafail.recovery-rpc-repair.v1' or
                            proof.get('context') != key or proof.get('attempt_id') != attempt):
                        raise ValueError('Recovery RPC repair identity changed')
                    barrier = proof['barrier']
                    _positive(barrier, manifest, attempt)
                else:
                    barrier = owned_daemon.shutdown_barrier(manifest,
                        evidence_directory=directory, attempt_id=attempt)
                    _positive(barrier, manifest, attempt)
                    owned_daemon.publish(proof_path, {'schema': 'mldsafail.recovery-rpc-repair.v1',
                        'context': key, 'attempt_id': attempt, 'barrier': barrier})
                clients = [entry for entry in record.get('clients', []) if entry.get('daemon_context') == key]
                stop_errors = []
                for entry in clients:
                    try: owned_client.stop(entry)
                    except BaseException as error: stop_errors.append(type(error).__name__)
                if stop_errors: raise RuntimeError('Independent creator cancellation incomplete: ' + repr(stop_errors))
                refreshed = owned_daemon.restart_and_refresh(manifest, barrier,
                    manifest_path=context['manifest_path'], client_entries=clients,
                    evidence_directory=directory, attempt_id=attempt)
                new_key = owned_daemon.fingerprint(refreshed)
                record['daemon_contexts'].setdefault(new_key,
                    {'manifest': refreshed, 'manifest_path': context['manifest_path']})
                for mutation in mutations:
                    mutation['resolved_by_barrier'] = {'proof_file': proof_path.name,
                        'old_epoch': manifest['epoch'], 'new_epoch': refreshed['epoch']}
                context['refreshed_context'] = new_key
                publish()  # No new request until repaired epoch identity is durable.
        except BaseException as error:
            errors.append({'step': 'dedicated_daemon_rpc_repair', 'context': key,
                           'error_type': type(error).__name__})
    return errors


@contextmanager
def shared_scope(environment):
    """Restore the original shared endpoint, never inherit disposable settings."""
    with _CONTEXT_LOCK:
        original = {key: os.environ.get(key) for key in _ENVIRONMENT}
        try:
            for key in _ENVIRONMENT:
                value = environment.get(key)
                if value is None: os.environ.pop(key, None)
                else: os.environ[key] = value
            yield
        finally:
            for key, value in original.items():
                if value is None: os.environ.pop(key, None)
                else: os.environ[key] = value


def cleanup_entries(record, field, errors):
    """Retain corruption, use a fresh safe registry, and keep cleanup fenced."""
    value = record.get(field, [])
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    errors.append({'step': 'corrupt_' + field, 'required': 'manual_authority_reconciliation'})
    corruption = record.setdefault('corrupt_fields', {})
    if not isinstance(corruption, dict):
        record.setdefault('invalid_corrupt_fields', corruption)
        corruption = record['corrupt_fields'] = {}
    corruption.setdefault(field, value)
    valid = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    record[field] = valid
    return valid
