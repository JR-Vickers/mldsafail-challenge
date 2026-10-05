from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import native_synthetic_operator_interruption as gate


def test_backend_signal_rejects_pid_reuse_before_descriptor(monkeypatch):
    entry=dict(pid=12,uid=1000,start_ticks=1,boot_id='boot',expected_cmdline_sha256='actual')
    monkeypatch.setattr(gate.owned_client,'identity',lambda pid:dict(pid=12,uid=1000,start_ticks=2,boot_id='boot',cmdline_sha256='actual'))
    monkeypatch.setattr(gate.os,'pidfd_open',lambda pid:pytest.fail('Never acquire descriptor for unrelated process'),raising=False)
    with pytest.raises(RuntimeError,match='birth/domain'):gate.backend_signal(entry,19)


def test_backend_signal_rechecks_after_descriptor_and_closes(monkeypatch):
    entry=dict(pid=12,uid=1000,start_ticks=1,boot_id='boot',expected_cmdline_sha256='actual')
    births=iter([dict(pid=12,uid=1000,start_ticks=1,boot_id='boot',cmdline_sha256='actual'),{'pid':99}])
    closed=[]
    monkeypatch.setattr(gate.owned_client,'identity',lambda pid:next(births))
    monkeypatch.setattr(gate.owned_client,'verify_domain',lambda entry:Path('/owned/backend'))
    monkeypatch.setattr(gate.os,'pidfd_open',lambda pid:33,raising=False)
    monkeypatch.setattr(gate.os,'close',closed.append)
    monkeypatch.setattr(gate.signal,'pidfd_send_signal',lambda *args:pytest.fail('Replaced backend must not be signaled'),raising=False)
    with pytest.raises(RuntimeError,match='descriptor'):gate.backend_signal(entry,19)
    assert closed==[33]


def test_units_are_disposable_bounded_no_timer_installation():
    calls=[]
    driver=SimpleNamespace(command=lambda argv,**kw:calls.append((argv,kw)))
    gate.start_unit(driver,'mldsafail-synthetic.service',Path('/source'),Path('/private/activation.json'))
    argv,kw=calls[0]
    assert argv[:2]==['systemd-run','--user']
    assert '--property=RuntimeMaxSec=600' in argv
    assert '--property=KillMode=process' in argv
    assert '--wait' not in argv
    assert kw['timeout']==30
    gate.start_unit(driver,'mldsafail-cleanup.service',Path('/source'),Path('/private/fixture.json'),wait=True,cleanup=True)
    assert '--property=KillMode=control-group' in calls[1][0]
    assert calls[1][0][-1]=='--cleanup'
    assert '--wait' in calls[1][0]


def test_retry_cleanup_rejects_changed_original_source_before_resource_access(monkeypatch,tmp_path):
    tmp_path.chmod(0o700)
    monkeypatch.setattr(gate.owned_daemon,'read_private_json',lambda path:dict(
        schema='mldsafail.synthetic-operator-interruption-result.v1',source_commit='old',acceptance_source_sha256='a'*64))
    driver=SimpleNamespace(command=lambda *a,**k:pytest.fail('No commands under wrong source'))
    with pytest.raises(RuntimeError,match='original fixture source'):
        gate.retry_cleanup(driver,dict(source_commit='new',acceptance_source_sha256='a'*64),tmp_path)


def test_retry_cleanup_does_not_replay_gate_and_rejects_ambiguous_publication(monkeypatch,tmp_path):
    tmp_path.chmod(0o700)
    original=dict(schema='mldsafail.synthetic-operator-interruption-result.v1',source_commit='same',acceptance_source_sha256='a'*64)
    monkeypatch.setattr(gate.owned_daemon,'read_private_json',lambda path:original)
    saved=[]
    def publish(path,outcome):
        saved.append(dict(outcome))
        if len(saved)==2:raise OSError('rename succeeded fsync failed')
    monkeypatch.setattr(gate.owned_daemon,'publish',publish)
    with pytest.raises(OSError,match='rename'):
        gate.retry_cleanup(SimpleNamespace(),dict(source_commit='same',acceptance_source_sha256='a'*64),tmp_path)
    assert saved[0]['cleanup_complete'] is False
    assert saved[1]['cleanup_complete'] is True
    assert saved[-1]['cleanup_complete'] is False
    assert saved[-1]['gate_acceptance_replayed'] is False


def test_terminal_unit_rejects_pending_start_even_with_no_main_pid():
    responses=iter([b'MainPID=0\nActiveState=inactive\nControlGroup=\n',b'42 mldsafail-synthetic.service start waiting\n'])
    driver=SimpleNamespace(command=lambda *a,**k:SimpleNamespace(stdout=next(responses)))
    with pytest.raises(RuntimeError,match='pending job'):
        gate.terminal_unit(driver,'mldsafail-synthetic.service')


def test_terminal_unit_accepts_empty_successful_job_inventory():
    responses=iter([b'MainPID=0\nActiveState=inactive\nControlGroup=\n',b''])
    driver=SimpleNamespace(command=lambda *a,**k:SimpleNamespace(stdout=next(responses)))
    assert gate.terminal_unit(driver,'mldsafail-synthetic.service')['pending_jobs_absent'] is True


def test_artifact_symlink_rejected_before_pin_read(tmp_path):
    tmp_path.chmod(0o700)
    target=tmp_path/'binary';target.write_bytes(b'pinned');target.chmod(0o700)
    (tmp_path/'restic').symlink_to(target)
    with pytest.raises(ValueError,match='private regular'):
        gate.validate_artifacts(tmp_path)


def test_group_readable_binary_rejected_before_fixture_mutations(tmp_path):
    tmp_path.chmod(0o700)
    binary=tmp_path/'restic';binary.write_bytes(b'pinned');binary.chmod(0o750)
    with pytest.raises(ValueError,match='private regular'):
        gate.validate_artifacts(tmp_path)
