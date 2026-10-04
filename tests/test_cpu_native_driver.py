from pathlib import Path
import pytest
from research.cpu_measurement import native_driver


def test_unit_rendering_requires_literal_complete_fresh_paths():
    fields=dict(PIDFILE='/private/dockerd.pid',DAEMON_CONFIG='/private/daemon.json',ROOTLESS_STATE='/private/state',DOCKERD_ROOTLESS='/usr/bin/dockerd-rootless.sh',SOCKET='/private/docker.sock',DATA_ROOT='/private/data',EXEC_ROOT='/private/exec',WORKER_SLICE='mldsafail-cpu-workers-nonce.slice')
    text=native_driver.render(fields)
    assert '--live-restore=false' in text and 'Restart=no' in text and 'Delegate=yes' in text
    assert '@' not in text
    with pytest.raises(ValueError,match='literal'): native_driver.render(dict(fields,SOCKET='/bad %n'))
    with pytest.raises(ValueError,match='Complete'): native_driver.render({})


def test_unit_install_never_overwrites_existing_service(tmp_path):
    path=tmp_path/'dedicated.service'
    receipt=native_driver.install(path,'[Service]\nRestart=no\n')
    assert receipt['path']==str(path) and path.stat().st_mode&0o777==0o600
    with pytest.raises(FileExistsError): native_driver.install(path,'different')
    assert path.read_text()=='[Service]\nRestart=no\n'


def test_cleanup_barrier_failure_retains_clients_and_worker_fence(tmp_path,monkeypatch):
    from deploy import owned_client,owned_daemon
    manifest_path=tmp_path/'manifest';manifest_path.write_text('{}')
    data=dict(id='attempt',commands=[],clients=[{'id':'possible-creator'}],units=[],config={},start_intent=True,image_load_intent=True,manifest_path=str(manifest_path),daemon_unit='mldsafail-cpu-daemon-test.service')
    journal=native_driver.Journal(tmp_path/'driver.json',data)
    order=[]
    monkeypatch.setattr(owned_daemon,'load_manifest',lambda path:{'epoch':'old'})
    monkeypatch.setattr(owned_daemon,'shutdown_barrier',lambda *args,**kwargs:order.append('barrier') or {'shutdown_proven':False,'errors':[{'step':'failed'}]})
    monkeypatch.setattr(owned_client,'stop',lambda entry:order.append('client_stop'))
    result=native_driver.cleanup(journal)
    assert not result['cleanup_complete'] and order==['barrier']
    assert data['state']=='cleanup_incomplete'


def test_failed_worker_start_still_stops_exact_fresh_slice(tmp_path,monkeypatch):
    fragment=native_driver.install(tmp_path/'mldsafail-cpu-workers-fresh.slice','[Slice]\n')
    data=dict(id='attempt',commands=[],clients=[],units=[fragment],config={},worker_slice=Path(fragment['path']).name,worker_start_intent=True)
    journal=native_driver.Journal(tmp_path/'driver.json',data)
    commands=[]
    monkeypatch.setattr(journal,'command',lambda argv,**kwargs:commands.append(argv))
    receipt=native_driver.cleanup(journal)
    assert receipt['cleanup_complete'] and commands==[['systemctl','--user','stop',data['worker_slice']]]


def test_command_publication_failure_preserves_original(tmp_path,monkeypatch):
    from deploy import owned_client
    journal=native_driver.Journal(tmp_path/'driver.json',dict(commands=[],clients=[]))
    calls=[]
    def save():
        calls.append('save')
        if len(calls)>1: raise OSError('publication')
    monkeypatch.setattr(journal,'save',save)
    monkeypatch.setattr(owned_client,'run',lambda *args,**kwargs:(_ for _ in ()).throw(RuntimeError('original')))
    with pytest.raises(RuntimeError,match='original') as failure: journal.command(['docker','start'],kind='start')
    assert 'publication' in failure.value.__notes__[0]


def test_corrupt_cleanup_state_still_attempts_positive_barrier(tmp_path,monkeypatch):
    from deploy import owned_daemon
    manifest=tmp_path/'manifest';manifest.write_text('{}')
    journal=native_driver.Journal(tmp_path/'driver.json',dict(id='attempt',worker_parent='/invalid',clients=None,commands=None,manifest_path=str(manifest),start_intent=True))
    order=[]
    monkeypatch.setattr(native_driver,'canonical_directory',lambda path:(_ for _ in ()).throw(ValueError('bad parent')))
    monkeypatch.setattr(owned_daemon,'load_manifest',lambda path:{'epoch':'old'})
    monkeypatch.setattr(owned_daemon,'shutdown_barrier',lambda *args,**kwargs:order.append('barrier') or {'shutdown_proven':True,'errors':[]})
    receipt=native_driver.cleanup(journal,terminal=True)
    assert order==['barrier'] and not receipt['cleanup_complete']
    assert {'measurement_directory','command_receipts','client_receipts'} <= {row['step'] for row in receipt['errors']}


def test_api_version_rejects_prefixed_value_before_native_actions(tmp_path,monkeypatch):
    names=('source_commit supervisor_source_sha256 state_root operator_unit operator_parent protected_roots protected_cgroups image image_archive image_archive_sha256 dockerd_sha256 rootless_script rootless_script_sha256 server_version server_git_commit api_version review_packet').split()
    config={name:'unused' for name in names};config.update(schema='mldsafail.cpu-native-driver.v1',api_version='v1.56')
    monkeypatch.setattr(native_driver.subprocess,'check_output',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('No host action')))
    with pytest.raises(ValueError,match='numeric Docker API'):native_driver.validate(config,tmp_path)


def test_startup_receipt_publication_failure_preserves_fence_and_safe_client_cleanup(tmp_path,monkeypatch):
    from deploy import owned_daemon,owned_client
    fragment=native_driver.install(tmp_path/'mldsafail-cpu-daemon-fresh.service','[Service]\n')
    data=dict(id='attempt',commands=[],clients=[dict(id='acknowledged',finished=True),dict(id='unknown')],units=[fragment],config={},start_intent=True,daemon_unit=Path(fragment['path']).name,manifest_path=str(tmp_path/'absent'))
    journal=native_driver.Journal(tmp_path/'driver.json',data)
    monkeypatch.setattr(native_driver,'register',lambda *a,**kw:(_ for _ in ()).throw(FileNotFoundError('transient rootless state')))
    monkeypatch.setattr(owned_daemon,'_unit',lambda unit:dict(unit_fragment_sha256=fragment['sha256']))
    monkeypatch.setattr(journal,'command',lambda *a,**kw:None)
    monkeypatch.setattr(owned_daemon,'failed_startup_barrier',lambda *a,**kw:(_ for _ in ()).throw(OSError('receipt publication')))
    calls=[];monkeypatch.setattr(owned_client,'stop',lambda entry:calls.append(entry['id']))
    receipt=native_driver.cleanup(journal)
    assert calls==['acknowledged'] and receipt['cleanup_complete'] is False
    assert data['state']=='cleanup_incomplete' and journal.path.exists()
    assert any(row['step']=='failed_startup_proof' for row in receipt['errors'])


def test_terminal_prior_state_archive_precedes_mutation_and_failure_prohibits_cleanup(tmp_path,monkeypatch):
    for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'MLDSAFAIL_OPERATOR_DAEMON_MANIFEST', 'MLDSAFAIL_CPU_DAEMON_MANIFEST'):
        monkeypatch.setenv(key, '')
    from contextlib import nullcontext
    from deploy import owned_daemon,recovery_daemon
    path=tmp_path/'driver.json'
    original=dict(schema='mldsafail.cpu-native-driver-state.v1',provisioning=dict(worker_birth={'path':'/old-worker'},protected_domains=[]),manifest_path=str(tmp_path/'absent'),socket='/old/socket',cleanup={'failed':'preserve'})
    owned_daemon.publish(path,original)
    monkeypatch.setattr(native_driver,'validate',lambda *a:None)
    monkeypatch.setattr(owned_daemon,'_disjoint',lambda *a:None)
    monkeypatch.setattr(recovery_daemon,'provision_lock',lambda *a:nullcontext())
    controller=dict(operator_parent='/new/operator',source_commit='a'*40,supervisor_source_sha256='b'*64)
    calls=[]
    def retire(journal,**kw):
        prior=list(tmp_path.glob('prior-driver-state-*.json'))
        assert len(prior)==1 and owned_daemon.read_private_json(prior[0])==original
        assert 'terminal_controller' not in owned_daemon.read_private_json(prior[0])
        calls.append('cleanup');return {'cleanup_complete':True}
    monkeypatch.setattr(native_driver,'cleanup',retire)
    assert native_driver.cleanup_state(path,controller_config=controller,repository=tmp_path)['cleanup_complete'] is True
    monkeypatch.setattr(owned_daemon,'publish',lambda *a:(_ for _ in ()).throw(OSError('archive failure')))
    with pytest.raises(OSError,match='archive failure'):
        native_driver.cleanup_state(path,controller_config=controller,repository=tmp_path)
    assert calls==['cleanup']
