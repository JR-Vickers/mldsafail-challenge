import copy
import json
from pathlib import Path
import pytest
from deploy import owned_daemon,recovery_terminal as terminal
from deploy.recovery_journal import Journal


def fixture(tmp_path,monkeypatch,shared=False):
    root=tmp_path/'recovery';(root/'journals').mkdir(parents=True,mode=0o700)
    config={'recovery_root':str(root)}
    operation=Journal(root/'journals/operation.json',config)
    manifest=dict(epoch='a'*32,unit='mldsafail-owned-daemon-test.service',socket='/private/socket',roots={name:{'path':'/private/'+name,'uid':1000,'mode':448} for name in ('root_dir','exec_root','rootless_state')},domain={'path':'/owned/daemon'},
        worker_domain={'path':'/owned/worker'},worker_cgroup_parent='owned.slice',provisioning={'id':'fixed'},
        unit_fragment_sha256='u',server_version='v',server_git_commit='g',daemon_executable_sha256='e')
    key=owned_daemon.fingerprint(manifest)
    operation.data.update(daemon_contexts={key:{'manifest':manifest,'manifest_path':'/private/manifest.json'}},
        containers=[{'name':'owned-db','image':'image','label':'owned-db','daemon_context':key}],
        daemon_mutations=[{'acknowledged':False,'daemon_context':key}],clients=[],cleanup_complete=False)
    if shared:operation.data['daemon_mutations'].append({'acknowledged':False,'daemon_context':None})
    operation.save('interrupted')
    barrier={'schema':'mldsafail.owned-daemon-barrier.v1','attempt_id':'driver','errors':[],
        'shutdown_proven':True,'daemon_epoch':manifest['epoch'],'daemon_manifest_sha256':key}
    state={'id':'driver','daemon_kind':'owned','manifest_path':'/private/manifest.json',
        'cleanup':{'schema':'mldsafail.cpu-native-driver-cleanup.v1','id':'driver','cleanup_complete':True,'errors':[],'daemon_barrier':barrier}}
    monkeypatch.setattr(terminal.owned_client,'verify_domain',lambda entry:None)
    monkeypatch.setattr(owned_daemon,'load_manifest',lambda path=None:manifest)
    monkeypatch.setattr(Journal,'command',lambda *args,**kwargs:pytest.fail('retired backend must never start or be queried'))
    return config,operation,state,manifest


def test_terminal_disposable_retirement_never_restarts_dead_backend(tmp_path,monkeypatch):
    config,operation,state,manifest=fixture(tmp_path,monkeypatch)
    result=terminal.terminal_job_cleanup('daily-recovery',config,state)
    assert result['cleanup_complete'] is True
    value=json.loads(operation.path.read_text())
    assert value['containers'][0]['retired_by_terminal_barrier'] is True
    assert value['daemon_mutations'][0]['acknowledged'] is False
    assert value['daemon_mutations'][0]['resolved_by_barrier']['terminal_retirement'] is True


def test_owned_terminal_barrier_cannot_clear_shared_rpc_uncertainty(tmp_path,monkeypatch):
    config,operation,state,manifest=fixture(tmp_path,monkeypatch,shared=True)
    with pytest.raises(RuntimeError,match='cleanup incomplete'):
        terminal.terminal_job_cleanup('daily-recovery',config,state)
    value=json.loads(operation.path.read_text())
    assert value['cleanup_complete'] is False
    assert not value['daemon_mutations'][1].get('resolved_by_barrier')


def test_foreign_root_contract_and_partial_terminal_proof_cannot_retire_context(tmp_path,monkeypatch):
    config,operation,state,manifest=fixture(tmp_path,monkeypatch)
    state['cleanup']['daemon_barrier']['errors']=['failed']
    with pytest.raises(ValueError,match='positive daemon barrier'):
        terminal.terminal_job_cleanup('daily-recovery',config,state)
    state['cleanup']['daemon_barrier']['errors']=[]
    value=operation.data
    value['terminal_retirement']={'manifest':dict(manifest,roots={'root_dir':{'path':'/different'}}),
        'barrier':state['cleanup']['daemon_barrier'],'attempt_id':'driver'}
    with pytest.raises(ValueError):terminal.validate_retirement(value,next(iter(value['daemon_contexts'])))


def test_terminal_invalid_proof_still_attempts_cleanup_without_restart(tmp_path,monkeypatch):
    config,operation,state,manifest=fixture(tmp_path,monkeypatch)
    state['cleanup']['cleanup_complete']=False
    calls=[]
    monkeypatch.setattr(Journal,'cleanup',lambda self:calls.append(self.data.get('terminal_no_restart')))
    with pytest.raises(ValueError):terminal.terminal_job_cleanup('daily-recovery',config,state)
    assert calls==[True]


def test_retirement_rejects_live_domain_before_container_skip(tmp_path,monkeypatch):
    config,operation,state,manifest=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(terminal.owned_client,'verify_domain',lambda entry:Path('/owned/live'))
    with pytest.raises(RuntimeError):terminal.terminal_job_cleanup('daily-recovery',config,state)
    value=json.loads(operation.path.read_text())
    assert not value['containers'][0].get('retired_by_terminal_barrier')
    assert value['terminal_no_restart'] is True


def test_repeated_cleanup_revalidates_retired_epoch_even_without_containers(tmp_path,monkeypatch):
    config,operation,state,manifest=fixture(tmp_path,monkeypatch)
    terminal.terminal_job_cleanup('daily-recovery',config,state)
    current=Journal(operation.path,config)
    current.data['containers']=[]
    monkeypatch.setattr(owned_daemon,'load_manifest',lambda path=None:dict(manifest,epoch='b'*32))
    with pytest.raises(RuntimeError,match='cleanup incomplete'):current.cleanup()
    assert any('terminal_retirement_invalid' in item for item in current.data['cleanup_errors'])


def test_terminal_owned_service_retirement_never_queries_old_backend(tmp_path,monkeypatch):
    config,operation,state,manifest=fixture(tmp_path,monkeypatch)
    key=next(iter(operation.data['daemon_contexts']))
    operation.data.update(services={'database':True},service_daemon_context=key,service_identifiers={'database':'old-db'})
    operation.save('owned service')
    assert terminal.terminal_job_cleanup('daily-recovery',config,state)['cleanup_complete'] is True


def test_missing_interrupted_job_journal_is_not_cleanup_proof(tmp_path):
    with pytest.raises(ValueError,match='journal is missing'):
        terminal.terminal_job_cleanup('daily-recovery',{'recovery_root':str(tmp_path)}, {})


def test_observer_ack_failure_stops_before_trusted_command(tmp_path,monkeypatch):
    path=tmp_path/'operation.json'
    operation=Journal(path,{})
    original=RuntimeError('driver ack publication failed')
    def callback():
        assert path.exists()
        raise original
    def gated_run(argv,entries,publish,*args,**kwargs):
        publish()
        pytest.fail('RPC must wait for durable ack')
    monkeypatch.setattr('deploy.owned_client.run',gated_run)
    with terminal.observe_job_journal(path,callback):
        with pytest.raises(RuntimeError) as caught:operation.command(['docker','ps'])
    assert caught.value is original


def test_observer_exact_path_nested_restore_and_thread_boundary(tmp_path):
    import threading
    path=tmp_path/'operation.json';other=tmp_path/'other.json'
    calls=[]
    with terminal.observe_job_journal(path,lambda:calls.append('outer')):
        Journal(other,{}).save('other')
        thread=threading.Thread(target=lambda:Journal(path,{}).save('foreign thread'))
        thread.start();thread.join()
        with terminal.observe_job_journal(other,lambda:calls.append('inner')):
            Journal(other,{}).save('inner')
        Journal(path,{}).save('outer')
    Journal(path,{}).save('no observer')
    assert calls==['inner','outer']
