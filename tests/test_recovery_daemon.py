from contextlib import contextmanager
import copy
import os
import pytest
from deploy import recovery_daemon as daemon


def fixture(tmp_path, monkeypatch):
    old = {'epoch': 'a'*32, 'unit': 'mldsafail-owned-daemon-test.service'}
    new = dict(old, epoch='b'*32)
    key = daemon.owned_daemon.fingerprint(old)
    record = {'daemon_contexts': {key: {'manifest': old, 'manifest_path': str(tmp_path/'manifest.json')}},
              'daemon_mutations': [{'acknowledged': False, 'daemon_context': key}],
              'clients': [{'id': 'creator', 'daemon_context': key}]}
    @contextmanager
    def scope(path, **kwargs): yield old
    monkeypatch.setattr(daemon, 'scope', scope)
    calls = []
    def barrier(manifest, **kwargs):
        calls.append('shutdown')
        return {'schema': 'mldsafail.owned-daemon-barrier.v1', 'attempt_id': kwargs['attempt_id'],
                'shutdown_proven': True, 'errors': [], 'daemon_epoch': old['epoch'],
                'daemon_manifest_sha256': key}
    monkeypatch.setattr(daemon.owned_daemon, 'shutdown_barrier', barrier)
    monkeypatch.setattr(daemon.owned_client, 'stop', lambda entry: calls.append('stop'))
    def restart(*args, **kwargs): calls.append('restart'); return new
    monkeypatch.setattr(daemon.owned_daemon, 'restart_and_refresh', restart)
    return record, old, new, calls


def test_barrier_precedes_cancel_restart_and_never_settles_shared_maintenance(tmp_path, monkeypatch):
    record, old, new, calls = fixture(tmp_path, monkeypatch)
    record['daemon_mutations'].append({'acknowledged': False, 'daemon_context': None})
    errors = daemon.repair(record, tmp_path, lambda: calls.append('publish'))
    assert calls == ['shutdown', 'stop', 'restart', 'publish']
    assert errors == [{'step': 'shared_maintenance_uncertainty', 'required': 'primary_manual_quiescent_repair'}]
    assert record['daemon_mutations'][0]['resolved_by_barrier']['new_epoch'] == new['epoch']
    assert not record['daemon_mutations'][0]['acknowledged']  # Preserve lost-response evidence.
    assert not record['daemon_mutations'][1].get('resolved_by_barrier')


def test_resume_after_manifest_refresh_before_journal_publication_reuses_durable_proof(tmp_path, monkeypatch):
    record, old, new, calls = fixture(tmp_path, monkeypatch)
    durable = copy.deepcopy(record)
    def failed(): raise OSError('journal publication interrupted')
    assert daemon.repair(record, tmp_path, failed)
    calls.clear()
    errors = daemon.repair(durable, tmp_path, lambda: calls.append('publish'))
    assert errors == []
    assert calls == ['stop', 'restart', 'publish']  # No shutdown of the newer epoch.
    assert durable['daemon_mutations'][0]['resolved_by_barrier']['new_epoch'] == new['epoch']


@pytest.mark.parametrize('field,value', [('schema','old'), ('errors',['failed']), ('attempt_id','other')])
def test_invalid_positive_proof_cannot_cancel_creator_or_restart(tmp_path, monkeypatch, field, value):
    record, old, new, calls = fixture(tmp_path, monkeypatch)
    original = daemon.owned_daemon.shutdown_barrier
    def corrupt(*args, **kwargs):
        receipt = original(*args, **kwargs); receipt[field] = value; return receipt
    monkeypatch.setattr(daemon.owned_daemon, 'shutdown_barrier', corrupt)
    assert daemon.repair(record, tmp_path, lambda: None)
    assert calls == ['shutdown']
    assert not record['daemon_mutations'][0].get('resolved_by_barrier')


def test_scope_restores_shared_environment_and_rejects_accounting_daemon(tmp_path, monkeypatch):
    monkeypatch.setenv('MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT', '/operator')
    monkeypatch.setenv('DOCKER_HOST', 'unix:///staging')
    monkeypatch.setenv('DOCKER_CONTEXT', 'original')
    manifest = {'unit': 'mldsafail-owned-daemon-test.service', 'socket': '/isolated',
                'provisioning': {'operator_domain': {'path': '/operator'}}}
    monkeypatch.setattr(daemon.owned_daemon, 'load_manifest', lambda path: manifest)
    monkeypatch.setattr(daemon.owned_daemon, 'verify_environment', lambda value: None)
    with daemon.scope(tmp_path/'manifest.json'):
        assert os.environ['DOCKER_HOST'] == 'unix:///isolated'
        assert 'DOCKER_CONTEXT' not in os.environ
    assert os.environ['DOCKER_HOST'] == 'unix:///staging'
    assert os.environ['DOCKER_CONTEXT'] == 'original'
    manifest['unit'] = 'mldsafail-cpu-daemon-test.service'
    with pytest.raises(ValueError, match='separate from accounting'):
        with daemon.scope(tmp_path/'manifest.json'): pass


def test_complete_operation_lock_rejects_cross_process_consumer_and_reuses_nested_lock(tmp_path, monkeypatch):
    import subprocess
    import sys
    tmp_path.chmod(0o700)
    identity = daemon.owned_daemon._private_directory(tmp_path)
    manifest = {'provisioning': {'base': identity}}
    monkeypatch.setattr(daemon.owned_daemon, 'load_manifest', lambda path: manifest)
    with daemon.operation_lock(tmp_path/'manifest.json'):
        with daemon.operation_lock(tmp_path/'manifest.json'):
            child = subprocess.run([sys.executable, '-c',
                'import fcntl,sys; f=open(sys.argv[1],"a"); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)',
                str(tmp_path/'operator.lock')], capture_output=True)
            assert child.returncode != 0
            assert b'BlockingIOError' in child.stderr
    with daemon.operation_lock(tmp_path/'manifest.json'): pass


def test_complete_operation_lock_rejects_unsafe_lock_before_action(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    manifest = {'provisioning': {'base': daemon.owned_daemon._private_directory(tmp_path)}}
    monkeypatch.setattr(daemon.owned_daemon, 'load_manifest', lambda path: manifest)
    lock = tmp_path/'operator.lock'
    lock.write_text('')
    lock.chmod(0o644)
    with pytest.raises(ValueError, match='Private exclusive'):
        with daemon.operation_lock(tmp_path/'manifest.json'): pytest.fail('unsafe lock admitted')


@pytest.mark.parametrize('field,value', [('clients', None), ('clients', ['invalid']), ('daemon_mutations', 'invalid'), ('daemon_mutations', [None])])
def test_corrupt_creator_authority_prevents_restart_even_with_pending_mutation(tmp_path, monkeypatch, field, value):
    record, old, new, calls = fixture(tmp_path, monkeypatch)
    record[field] = value
    errors = daemon.repair(record, tmp_path, lambda: calls.append('publish'))
    assert errors and calls == []
    entries = daemon.cleanup_entries(record, field, errors)
    assert entries == [] and record['corrupt_fields'][field] == value
    assert daemon.repair(record, tmp_path, lambda: calls.append('publish'))
    assert calls == []  # Sanitizing a registry cannot recover lost creator authority.


def test_fork_cannot_reuse_parent_operation_lock(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    manifest = {'provisioning': {'base': daemon.owned_daemon._private_directory(tmp_path)}}
    monkeypatch.setattr(daemon.owned_daemon, 'load_manifest', lambda path: manifest)
    with daemon.operation_lock(tmp_path/'manifest.json'):
        pid = os.fork()
        if pid == 0:
            try:
                with daemon.operation_lock(tmp_path/'manifest.json'): os._exit(2)
            except BlockingIOError: os._exit(0)
            except BaseException: os._exit(3)
        assert os.waitpid(pid, 0)[1] == 0


def test_dedicated_service_cleanup_uses_recorded_context_instead_of_shared_endpoint(tmp_path, monkeypatch):
    from deploy.recovery_journal import Journal
    from types import SimpleNamespace
    operation=Journal(tmp_path/'operation.json',{})
    key='c'*64
    def bind(record,path):
        record.setdefault('daemon_contexts',{})[key]={'manifest_path':str(path)}
        return key
    monkeypatch.setattr(daemon,'bind',bind)
    scopes=[]
    @contextmanager
    def scope(path,**kwargs):
        scopes.append(str(path)); yield {}
    monkeypatch.setattr(daemon,'scope',scope)
    operation.services([],{'web':True},{'web':'d'*64},daemon_manifest_path='/private/manifest.json')
    calls=[]
    def command(argv,**kwargs):
        calls.append((argv,kwargs.get('daemon_manifest_path')))
        return SimpleNamespace(returncode=0,stdout='')
    monkeypatch.setattr(operation,'command',command)
    def restore(identifier,running,runner):
        assert identifier=='d'*64 and running is True
        runner(['docker','start',identifier])
    monkeypatch.setattr('deploy.recovery_journal.restore_service',restore)
    operation.cleanup()
    assert operation.data['cleanup_complete'] is True
    assert scopes==['/private/manifest.json']
    assert calls==[(['docker','start','d'*64],'/private/manifest.json')]


def test_corrupt_corruption_metadata_cannot_bypass_fence_or_abort_safe_registry_cleanup(tmp_path, monkeypatch):
    record, old, new, calls=fixture(tmp_path,monkeypatch)
    record.update(corrupt_fields=None,clients=None)
    errors=daemon.repair(record,tmp_path,lambda:None)
    assert errors and calls==[]
    assert daemon.cleanup_entries(record,'clients',errors)==[]
    assert record['invalid_corrupt_fields'] is None
    assert daemon.repair(record,tmp_path,lambda:None) and calls==[]


def test_provision_lock_covers_registration_and_nested_manifest_consumer(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    provisioning={'base':daemon.owned_daemon._private_directory(tmp_path)}
    monkeypatch.setattr(daemon.owned_daemon,'load_manifest',lambda path:{'provisioning':provisioning})
    with daemon.provision_lock(provisioning):
        with daemon.operation_lock(tmp_path/'later-manifest.json'):
            assert len(daemon.operation_lock._active)==1
    assert not daemon.operation_lock._active
