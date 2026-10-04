import fcntl
import json
import os
from types import SimpleNamespace

import pytest

from scripts import native_postgres_acceptance as runner


def receipt():
    return dict(schema_version=1, run_id='a' * 32, name='launch-postgres-' + 'a' * 32,
                database_image='sha256:' + 'b' * 64, clients=[], cleanup_complete=False)


def test_cleanup_retry_preserves_failed_receipt_and_checks_exact_ownership(tmp_path, monkeypatch):
    value = receipt()
    present = [True]
    failing = [True]
    identifier = 'c' * 64
    def command(argv, output, record, **kwargs):
        if argv[:2] == ['docker', 'ps']:
            return identifier if present[0] else ''
        if argv[:2] == ['docker', 'inspect']:
            return json.dumps([dict(Id=identifier, Name='/' + value['name'],
                                   Image=value['database_image'], Config={'Labels': {runner.LABEL: value['run_id']}})])
        if failing[0]:
            raise RuntimeError('synthetic removal failure')
        present[0] = False
        return ''
    monkeypatch.setattr(runner, 'command', command)
    monkeypatch.setattr(runner.time, 'sleep', lambda _: None)
    assert not runner.cleanup(tmp_path, value)
    failed = json.loads((tmp_path / 'ownership.json').read_text())
    assert failed['phase'] == 'cleanup_incomplete' and failed['cleanup_errors']
    failing[0] = False
    assert runner.cleanup(tmp_path, value)
    assert runner.cleanup(tmp_path, value)
    assert value['cleanup_complete']
    attempts = [json.loads((tmp_path / name).read_text()) for name in value['cleanup_attempts']]
    assert len(attempts) == 3 and any(not attempt['cleanup_complete'] for attempt in attempts)


def test_cleanup_never_removes_mismatched_resource(tmp_path, monkeypatch):
    value = receipt()
    calls = []
    def command(argv, *args, **kwargs):
        calls.append(argv)
        if argv[:2] == ['docker', 'ps']:
            return 'c' * 64
        return json.dumps([dict(Id='c' * 64, Name='/another-database', Image=value['database_image'],
                               Config={'Labels': {runner.LABEL: value['run_id']}})])
    monkeypatch.setattr(runner, 'command', command)
    assert not runner.cleanup(tmp_path, value)
    assert not any(argv[:3] == ['docker', 'rm', '-f'] for argv in calls)


def test_command_delegates_durable_client_receipt(tmp_path, monkeypatch):
    value = receipt()
    def interrupted(argv, entries, save, directory, **kwargs):
        entries.append({'id': 'owned', 'finished': False})
        save()
        raise InterruptedError('injected interruption')
    from deploy import owned_client
    monkeypatch.setattr(owned_client, 'run', interrupted)
    with pytest.raises(InterruptedError):
        runner.command(['docker', 'run'], tmp_path, value)
    assert json.loads((tmp_path / 'ownership.json').read_text())['clients'] == [{'id': 'owned', 'finished': False, 'daemon_context': None}]


def test_execute_and_cleanup_share_exclusive_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.sys, 'platform', 'linux')
    output = tmp_path / 'run'
    descriptor = os.open(tmp_path / '.run.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            runner.run(None, output, cleanup_only=True)
    finally:
        os.close(descriptor)


def test_output_symlink_and_public_parent_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.sys, 'platform', 'linux')
    target = tmp_path / 'target'
    target.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match='non-symlink'):
        runner.run(None, link / 'run', True)
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match='Private evidence parent'):
        runner.run(None, tmp_path / 'run', True)


def test_lost_daemon_run_request_empty_inventory_never_clears_fence(tmp_path, monkeypatch):
    identity = 'a' * 32
    receipt = {'run_id': identity, 'name': 'launch-postgres-' + identity,
               'database_image': 'sha256:' + 'b' * 64, 'clients': []}
    def lost(*args, **kwargs): raise TimeoutError('daemon accepted, response lost')
    monkeypatch.setattr('deploy.owned_client.run', lost)
    with pytest.raises(TimeoutError):
        runner.command(['docker', 'run', '--name', receipt['name'], receipt['database_image']], tmp_path, receipt)
    monkeypatch.setattr(runner, 'command', lambda *args, **kwargs: '')
    monkeypatch.setattr(runner.time, 'sleep', lambda _: None)
    for _ in range(2):
        assert not runner.cleanup(tmp_path, receipt)
        assert any(e['step'] == 'daemon_mutation_uncertainty' for e in receipt['cleanup_errors'])


def test_cleanup_receipt_failure_still_publishes_fenced_ownership(tmp_path, monkeypatch):
    value=receipt()
    monkeypatch.setattr(runner,'command',lambda *args,**kwargs:'')
    monkeypatch.setattr(runner.time,'sleep',lambda _:None)
    original=runner.atomic_json
    published=[]
    def fail_receipt(path,data):
        published.append(path.name)
        if path.name.endswith('-cleanup.json'): raise OSError('private disk fault')
        original(path,data)
    monkeypatch.setattr(runner,'atomic_json',fail_receipt)
    assert runner.cleanup(tmp_path,value) is False
    retained=json.loads((tmp_path/'ownership.json').read_text())
    assert retained['cleanup_complete'] is False
    assert any(e['step']=='cleanup_receipt_publication' for e in retained['cleanup_errors'])
    assert published[-1]=='ownership.json'


def test_execution_preserves_original_failure_and_independently_attempts_cleanup_and_final_report(tmp_path,monkeypatch):
    import subprocess
    output=tmp_path/'run'
    primary=ValueError('original native admission failure')
    calls=[]
    monkeypatch.setenv('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST','/private/manifest.json')
    monkeypatch.setattr('deploy.recovery_daemon.bind',lambda *args:None)
    monkeypatch.setattr(runner.subprocess,'check_output',lambda argv,**kwargs:'a'*40 if argv[-1]=='HEAD' else '')
    def command(*args,**kwargs): raise primary
    monkeypatch.setattr(runner,'command',command)
    def cleanup(*args): calls.append('cleanup');raise RuntimeError('secondary cleanup failure')
    monkeypatch.setattr(runner,'cleanup',cleanup)
    real=runner.atomic_json
    reports=[0]
    def publish(path,value):
        if path.name=='report.json':
            reports[0]+=1
            calls.append('report:'+str(reports[0]))
            if reports[0]>1:raise OSError('report disk failure')
        real(path,value)
    monkeypatch.setattr(runner,'atomic_json',publish)
    with pytest.raises(ValueError) as caught:
        runner.execute('sha256:'+'b'*64,output,False)
    assert caught.value is primary
    assert calls==['report:1','report:2','cleanup','report:3']
    assert len(primary.__notes__)==3
