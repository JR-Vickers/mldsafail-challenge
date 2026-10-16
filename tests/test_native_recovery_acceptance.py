import fcntl
from types import SimpleNamespace

import pytest

from deploy.native_recovery_acceptance import child, run


def test_fixture_requires_preloaded_immutable_image(tmp_path, monkeypatch):
    monkeypatch.setattr('deploy.native_recovery_acceptance.command',
                        lambda _: pytest.fail('Docker must not run with unpinned image'))
    with pytest.raises(ValueError, match='immutable'):
        run(SimpleNamespace(output=tmp_path / 'new', image='alpine:latest'))


def test_competing_child_cannot_touch_services(tmp_path, monkeypatch):
    lock = (tmp_path / 'lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    monkeypatch.setattr('deploy.native_recovery_acceptance.command',
                        lambda _: pytest.fail('Competing owner must not touch Docker'))
    with pytest.raises(BlockingIOError):
        child(tmp_path, 'race', False)


def test_owned_child_cleanup_is_idempotent_after_exit(tmp_path, monkeypatch):
    import json
    from deploy.native_recovery_acceptance import stop_owned_child
    (tmp_path / 'owner-process.json').write_text(json.dumps({'pid': 123}))
    def missing(pid):
        raise FileNotFoundError()
    monkeypatch.setattr('deploy.native_recovery_acceptance.process_identity', missing)
    assert stop_owned_child(tmp_path) == {'already_stopped': True}
    assert stop_owned_child(tmp_path) == {'already_stopped': True}


def test_reused_child_identity_never_signalled(tmp_path, monkeypatch):
    import json
    from deploy.native_recovery_acceptance import stop_owned_child
    (tmp_path / 'owner-process.json').write_text(json.dumps({'pid': 123, 'start_ticks': 10}))
    monkeypatch.setattr('deploy.native_recovery_acceptance.process_identity',
                        lambda _: {'pid': 123, 'start_ticks': 11})
    with pytest.raises(RuntimeError, match='ownership mismatch'):
        stop_owned_child(tmp_path)


def test_pidfd_identity_change_prevents_signal_and_closes_descriptor(tmp_path, monkeypatch):
    import json
    import os
    from deploy.native_recovery_acceptance import stop_owned_child
    identity = {'pid': 123, 'start_ticks': 10, 'uid': os.getuid(),
                'cmdline': '00', 'boot_id': 'fixture-boot'}
    (tmp_path / 'owner-process.json').write_text(json.dumps(identity))
    records = iter([identity, dict(identity, start_ticks=11)])
    closed = []
    monkeypatch.setattr('deploy.native_recovery_acceptance.process_identity', lambda _: next(records))
    monkeypatch.setattr('deploy.native_recovery_acceptance.os.pidfd_open', lambda _: 99, raising=False)
    monkeypatch.setattr('deploy.native_recovery_acceptance.signal.pidfd_send_signal',
                        lambda *args: pytest.fail('Changed owner must never receive signal'), raising=False)
    monkeypatch.setattr('deploy.native_recovery_acceptance.os.close', lambda descriptor: closed.append(descriptor))
    with pytest.raises(RuntimeError, match='changed before cancellation'):
        stop_owned_child(tmp_path)
    assert closed == [99]


def test_native_fixture_requires_explicit_disposable_daemon_before_docker(tmp_path, monkeypatch):
    monkeypatch.setattr('deploy.native_recovery_acceptance.sys.platform', 'linux')
    monkeypatch.delenv('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST', raising=False)
    monkeypatch.setattr('deploy.native_recovery_acceptance.command', lambda _: pytest.fail('must not run Docker'))
    with pytest.raises(ValueError, match='dedicated disposable'):
        run(SimpleNamespace(output=tmp_path/'fresh', image='alpine@sha256:'+'a'*64))


def test_cleanup_requires_owner_exit_before_daemon_repair(tmp_path, monkeypatch):
    from deploy.native_recovery_acceptance import cleanup_fixture
    (tmp_path/'owner-process.json').write_text('{}')
    def failed(root): raise RuntimeError('unproven owner')
    monkeypatch.setattr('deploy.native_recovery_acceptance.quiesce_owned_child', failed)
    monkeypatch.setattr('deploy.native_recovery_acceptance.Journal', lambda *args: pytest.fail('unfenced owner prohibits daemon restart'))
    with pytest.raises(RuntimeError, match='quiescence'):
        cleanup_fixture(tmp_path, {}, [])
    assert list(tmp_path.glob('*-owner-fence.json'))


def test_cleanup_failure_does_not_skip_independent_resource_inventories(tmp_path, monkeypatch):
    from deploy.native_recovery_acceptance import cleanup_fixture
    import json
    calls = []
    class Journal:
        def __init__(self, path, config): self.path=path
        def cleanup(self): calls.append('journal:'+self.path.name)
    monkeypatch.setattr('deploy.native_recovery_acceptance.Journal', Journal)
    def command(argv):
        calls.append(argv)
        if 'down' in argv: raise OSError('synthetic failed Docker response')
        return ''
    monkeypatch.setattr('deploy.native_recovery_acceptance.command', command)
    ownership = dict(project='recovery-test-'+'a'*32, source='source', source_script_sha256='script',
                     daemon_fingerprint='daemon', image='immutable')
    with pytest.raises(RuntimeError, match='cleanup incomplete'):
        cleanup_fixture(tmp_path, ownership, [])
    assert any(isinstance(item,list) and item[:3]==['docker','volume','ls'] for item in calls)
    assert any(isinstance(item,list) and item[:3]==['docker','network','ls'] for item in calls)
    report=json.loads((tmp_path/'results.json').read_text())
    assert report['cleanup_complete'] is False
    assert report['cleanup_errors']==[{'step':'project_removal','error_type':'OSError'}]


def test_child_cli_reports_exact_lock_contention_marker(tmp_path):
    import json
    import subprocess
    import sys
    lock=(tmp_path/'lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    result=subprocess.run([sys.executable,'-m','deploy.native_recovery_acceptance','--child',
                           '--output',str(tmp_path)],capture_output=True,timeout=10)
    assert result.returncode==73
    assert json.loads(result.stdout)=={'ownership_rejected':'run_lock_contended'}


def test_fault_owner_exit_before_injection_cannot_pass_signal_gate(tmp_path, monkeypatch):
    from deploy.native_recovery_acceptance import signal_owned_fork
    import os
    import select
    import signal
    identity={'pid':123,'start_ticks':1}
    monkeypatch.setattr('deploy.native_recovery_acceptance.process_identity',lambda _:identity)
    monkeypatch.setattr(os,'pidfd_open',lambda _:99,raising=False)
    closed=[]
    monkeypatch.setattr(os,'close',lambda fd:closed.append(fd))
    class Poller:
        def register(self,*args):pass
        def poll(self,*args):return [(99,select.POLLIN)]
    monkeypatch.setattr(select,'poll',Poller,raising=False)
    monkeypatch.setattr(signal,'pidfd_send_signal',lambda *args:pytest.fail('dead fault owner cannot be signaled'),raising=False)
    with pytest.raises(RuntimeError,match='exited before'):
        signal_owned_fork(123,identity,signal.SIGKILL)
    assert closed==[99]


def test_complete_fault_cases_cannot_override_retained_execution_failure(tmp_path, monkeypatch):
    from deploy.native_recovery_acceptance import cleanup_fixture
    class Journal:
        def __init__(self,*args):pass
        def cleanup(self):pass
    monkeypatch.setattr('deploy.native_recovery_acceptance.Journal',Journal)
    monkeypatch.setattr('deploy.native_recovery_acceptance.command',lambda argv:'')
    ownership=dict(project='recovery-test-'+'a'*32,source='source',source_script_sha256='script',
                   daemon_fingerprint='daemon',image='immutable')
    cases=[{'fault':name,'passed':True} for name in ('SIGTERM','SIGKILL','connection_loss','cleanup_failure')]
    report=cleanup_fixture(tmp_path,ownership,cases,execution_error='OSError')
    assert report['cleanup_complete'] is True
    assert report['native_service_suite_passed'] is False
    assert report['execution_error']=='OSError'


def test_owned_fork_cleanup_failure_cannot_publish_successful_native_receipt(tmp_path, monkeypatch):
    from deploy.native_recovery_acceptance import cleanup_fixture
    import json
    class Journal:
        def __init__(self,*args):pass
        def cleanup(self):pass
    monkeypatch.setattr('deploy.native_recovery_acceptance.Journal',Journal)
    monkeypatch.setattr('deploy.native_recovery_acceptance.command',lambda argv:'')
    ownership=dict(project='recovery-test-'+'a'*32,source='source',source_script_sha256='script',
                   daemon_fingerprint='daemon',image='immutable')
    cases=[{'fault':name,'passed':True} for name in ('SIGTERM','SIGKILL','connection_loss','cleanup_failure')]
    with pytest.raises(RuntimeError,match='cleanup incomplete'):
        cleanup_fixture(tmp_path,ownership,cases,owned_child_errors=['TimeoutError'])
    report=json.loads((tmp_path/'results.json').read_text())
    assert report['cleanup_complete'] is False and report['native_service_suite_passed'] is False
    assert report['cleanup_errors']==[{'step':'owned_fork_quiescence','error_type':'TimeoutError'}]


@pytest.mark.parametrize('retry_fails',[False,True])
def test_final_receipt_rename_then_fsync_failure_retracts_success(tmp_path,monkeypatch,retry_fails):
    import json
    from deploy import native_recovery_acceptance as native
    class Journal:
        def __init__(self,*args):pass
        def cleanup(self):pass
    monkeypatch.setattr(native,'Journal',Journal)
    monkeypatch.setattr(native,'command',lambda argv:'')
    actual=native.atomic_json; original=OSError('results directory fsync failed');records=[]
    def publish(path,value):
        if path.name=='results.json':
            records.append(dict(value))
            if len(records)==1:
                actual(path,value)
                raise original
            if retry_fails:raise OSError('negative receipt write failed')
        actual(path,value)
    monkeypatch.setattr(native,'atomic_json',publish)
    ownership=dict(project='recovery-test-'+'a'*32,source='source',source_script_sha256='script',
        daemon_fingerprint='daemon',image='immutable')
    cases=[dict(fault=name,passed=True) for name in ('SIGTERM','SIGKILL','connection_loss','cleanup_failure')]
    with pytest.raises(OSError) as caught:native.cleanup_fixture(tmp_path,ownership,cases)
    assert caught.value is original
    assert len(records)==2 and records[0]['native_service_suite_passed'] is True
    assert records[1]['native_service_suite_passed'] is False
    assert records[1]['cleanup_complete'] is False and records[1]['evidence_publication_failed'] is True
    intermediate=json.loads(next(tmp_path.glob('*-cleanup.json')).read_text())
    assert intermediate['native_service_suite_passed'] is False and intermediate['provisional'] is True
    if retry_fails:assert 'Negative recovery receipt publication failed' in original.__notes__[0]
    else:
        receipt=json.loads((tmp_path/'results.json').read_text())
        assert receipt['native_service_suite_passed'] is False and receipt['cleanup_complete'] is False
