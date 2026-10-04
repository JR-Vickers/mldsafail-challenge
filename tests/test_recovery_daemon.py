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
