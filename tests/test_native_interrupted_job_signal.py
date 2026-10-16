from copy import deepcopy
from pathlib import Path
import pytest
from deploy.operator_activation import configuration_digest
from scripts.native_interrupted_job_signal import admitted


def test_admission_requires_real_running_job_and_exact_bound_manifest(monkeypatch):
    from scripts import native_interrupted_job_signal as gate
    effective=dict(backup_state='/private/check/state.json')
    state=dict(daemon_kind='owned',manifest_path='/private/owned/manifest.json',
        operator_job=dict(job='recovery-check',state='running',journal_created=True,
        effective_config_digest=configuration_digest(effective),
        journal_path='/private/check/.mldsafail-restic-operation/operation.json'))
    monkeypatch.setattr(gate.owned_daemon,'load_manifest',lambda path:{'epoch':'exact'})
    monkeypatch.setattr(gate.owned_daemon,'fingerprint',lambda manifest:'fingerprint')
    operation=dict(cleanup_complete=False,daemon_contexts={'fingerprint':{}})
    assert admitted(state,operation,effective)==state['operator_job']
    for field,value in [('state','passed'),('job','fixture'),('journal_created',False),
                        ('journal_path','/private/unrelated/operation.json'),
                        ('effective_config_digest','substituted')]:
        bad=deepcopy(state);bad['operator_job'][field]=value
        with pytest.raises(RuntimeError,match='Actual admitted'):
            admitted(bad,operation,effective)
    with pytest.raises(RuntimeError,match='exact owned daemon'):
        admitted(state,dict(cleanup_complete=False,daemon_contexts={}),effective)


def test_pid_descriptor_rechecks_birth_before_signal(monkeypatch):
    from scripts import native_interrupted_job_signal as gate
    calls=[]
    monkeypatch.setattr(gate.os,'pidfd_open',lambda pid:calls.append(('open',pid)) or 77,raising=False)
    monkeypatch.setattr(gate.os,'close',lambda fd:calls.append(('close',fd)))
    monkeypatch.setattr(gate.owned_client,'identity',lambda pid:{'start_ticks':2})
    monkeypatch.setattr(gate.owned_client,'domain_identity',lambda parent:{'inode':1})
    monkeypatch.setattr(gate.signal,'pidfd_send_signal',lambda *args:calls.append(('signal',args)),raising=False)
    with pytest.raises(RuntimeError,match='PID descriptor'):
        gate.signal_exact_owner(12,{'start_ticks':1},Path('/owned'),{'inode':1})
    assert calls==[('open',12),('close',77)]


def test_ambiguous_final_positive_publication_retries_negative():
    from scripts.native_interrupted_job_signal import publish_final
    report={'signal_sent':True}
    persisted=[]
    def publish():
        persisted.append(dict(report))
        if len(persisted)==1:raise OSError('after rename before directory fsync')
    with pytest.raises(OSError,match='after rename'):
        publish_final(report,publish,None,[])
    assert persisted[0]['passed'] is True
    assert persisted[-1]['passed'] is False
    assert persisted[-1]['final_publication_failed'] is True


def test_original_failure_retained_after_publication_failure():
    from scripts.native_interrupted_job_signal import publish_final
    report={'signal_sent':False}
    original=ValueError('original signal failure')
    def publish():raise OSError('publication')
    publish_final(report,publish,original,[])
    assert report['passed'] is False
    assert any('Signal evidence' in note for note in original.__notes__)
