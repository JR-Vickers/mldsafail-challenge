import subprocess
import pytest
from deploy.recovery_journal import Journal


def test_lost_docker_create_response_remains_fenced_across_retry(tmp_path, monkeypatch):
    journal = Journal(tmp_path / 'operation.json', {})
    def lost(*args, **kwargs):
        raise TimeoutError('accepted daemon request, missing CLI response')
    monkeypatch.setattr('deploy.owned_client.run', lost)
    with pytest.raises(TimeoutError):
        journal.command(['docker', 'create', '--name', 'synthetic', 'image'], timeout=1)
    resumed = Journal(tmp_path / 'operation.json', {})
    for _ in range(2):
        with pytest.raises(RuntimeError, match='cleanup incomplete'):
            resumed.cleanup()
        assert not resumed.data['cleanup_complete']
        assert 'positive_dedicated_daemon_barrier_required' in resumed.data['cleanup_errors'][0]


def test_successful_request_acknowledged_read_only_request_not_mutation(tmp_path, monkeypatch):
    journal = Journal(tmp_path / 'operation.json', {})
    monkeypatch.setattr('deploy.owned_client.run', lambda argv, *args, **kwargs: subprocess.CompletedProcess(argv, 0))
    journal.command(['docker', 'inspect', 'synthetic'], timeout=1)
    assert not journal.data.get('daemon_mutations')
    journal.command(['docker', 'create', '--name', 'synthetic', 'image'], timeout=1)
    assert journal.data['daemon_mutations'][0]['acknowledged'] is True


def test_service_restore_response_loss_is_fenced_even_after_known_state_retry(tmp_path, monkeypatch):
    journal = Journal(tmp_path / 'operation.json', {})
    journal.services(['docker', 'compose'], {'web': True}, {'web': 'pinned'})
    calls = []
    def lost(argv, *args, **kwargs):
        calls.append(argv)
        raise TimeoutError('daemon start response lost')
    monkeypatch.setattr('deploy.owned_client.run', lost)
    with pytest.raises(RuntimeError): journal.cleanup()
    assert calls == [['docker', 'container', 'start', 'pinned']]
    def success(argv, *args, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout='{"Running":true}')
    monkeypatch.setattr('deploy.owned_client.run', success)
    with pytest.raises(RuntimeError): journal.cleanup()
    assert any('positive_dedicated_daemon_barrier_required' in e for e in journal.data['cleanup_errors'])
    assert not journal.data['cleanup_complete']
