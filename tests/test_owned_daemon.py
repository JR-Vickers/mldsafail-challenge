from pathlib import Path
import os
import pytest
from deploy import owned_daemon, owned_client


def test_default_staging_unit_is_ineligible_before_any_control(monkeypatch):
    def forbidden(*args,**kwargs): raise AssertionError('No shared daemon control permitted')
    monkeypatch.setattr(owned_daemon.subprocess,'check_output',forbidden)
    with pytest.raises(RuntimeError,match='dedicated'): owned_daemon._unit('docker.service')


def test_provision_requires_fresh_private_disjoint_roots(monkeypatch,tmp_path):
    monkeypatch.setattr(owned_client,'boot_id',lambda:'boot')
    tmp_path.chmod(0o700)
    protected=tmp_path/'staging';protected.mkdir(mode=0o700)
    with pytest.raises(RuntimeError,match='overlap'):
        owned_daemon.provision(protected/'nested',unit='mldsafail-owned-daemon-test.service',protected_roots=[protected])
    receipt=owned_daemon.provision(tmp_path/'fresh',unit='mldsafail-owned-daemon-test.service',protected_roots=[protected])
    assert set(receipt['roots'])=={'root_dir','exec_root','rootless_state'}
    assert (tmp_path/'fresh/provision.json').stat().st_mode&0o777==0o600
    with pytest.raises(FileExistsError):
        owned_daemon.provision(tmp_path/'fresh',unit=receipt['unit'],protected_roots=[protected])
    root=Path(receipt['roots']['root_dir']['path'])
    root.rmdir();root.mkdir(mode=0o700)
    with pytest.raises(RuntimeError,match='fresh provisioning'):
        owned_daemon._provisioning(receipt,receipt['unit'],{name:owned_daemon._private_directory(value['path']) for name,value in receipt['roots'].items()})


def fixture_manifest(tmp_path,monkeypatch):
    monkeypatch.setattr(owned_client,'boot_id',lambda:'boot')
    domains=[]
    for name in ('daemon','worker'):
        path=tmp_path/name;path.mkdir()
        for control,value in [('cgroup.events','populated 0\n'),('cgroup.kill','')]: (path/control).write_text(value)
        domains.append(owned_client.domain_identity(path))
    manifest=dict(schema=owned_daemon.SCHEMA,epoch='a'*32,unit='mldsafail-owned-daemon-test.service',
                unit_fragment_sha256='b'*64,domain=domains[0],worker_domain=domains[1],
                leader={'pid':123},roots={})
    monkeypatch.setattr(owned_daemon,'load_manifest',lambda:manifest)
    return manifest


def test_barrier_kills_entire_registered_worker_parent_and_preserves_identity_failures(tmp_path,monkeypatch):
    manifest=fixture_manifest(tmp_path,monkeypatch)
    monkeypatch.setattr(owned_daemon,'_unit',lambda unit:{'ActiveState':'inactive','unit_fragment_sha256':'b'*64})
    monkeypatch.setattr(owned_client,'stop',lambda entry:None)
    result=owned_daemon.shutdown_barrier(manifest,evidence_directory=tmp_path,attempt_id='attempt')
    assert result['shutdown_proven'] is True
    assert (tmp_path/'worker/cgroup.kill').read_text()=='1'
    assert (tmp_path/result['receipt_file']).exists()
    manifest['worker_domain']=dict(manifest['worker_domain'],inode=-1)
    result=owned_daemon.shutdown_barrier(manifest,evidence_directory=tmp_path,attempt_id='attempt')
    assert result['shutdown_proven'] is False
    assert any(item['step']=='dedicated_worker_domain_stop' for item in result['errors'])


def test_wrong_unit_epoch_prohibits_daemon_and_worker_control(tmp_path,monkeypatch):
    manifest=fixture_manifest(tmp_path,monkeypatch)
    monkeypatch.setattr(owned_daemon,'_unit',lambda unit:{'ActiveState':'active','MainPID':'456',
                    'domain_path':manifest['domain']['path'],'unit_fragment_sha256':'b'*64})
    killed=[]
    monkeypatch.setattr(owned_client,'stop',lambda entry:killed.append(entry))
    receipt=owned_daemon.shutdown_barrier(manifest,evidence_directory=tmp_path,attempt_id='attempt')
    assert not receipt['shutdown_proven'] and killed==[]
    assert (tmp_path/'worker/cgroup.kill').read_text()==''


def test_restart_rejects_unproved_shutdown_before_any_start(tmp_path,monkeypatch):
    manifest=fixture_manifest(tmp_path,monkeypatch)
    with pytest.raises(RuntimeError,match='Positive exact'):
        owned_daemon.restart_and_refresh(manifest,{'shutdown_proven':False},manifest_path=tmp_path/'manifest',
                evidence_directory=tmp_path,attempt_id='attempt')


def test_arbitrary_worker_slice_rejected_before_native_identity():
    with pytest.raises(RuntimeError,match='birth identity'):
        owned_daemon._worker_binding(dict(unit='mldsafail-owned-daemon-test.service',id='a'*32),{'path':'/sys/fs/cgroup/staging.slice'},'staging.slice')


def test_worker_birth_rejects_arbitrary_slice(tmp_path):
    with pytest.raises(RuntimeError,match='nonce-named'):
        owned_daemon.bind_worker(dict(unit='mldsafail-owned-daemon-test.service',id='a'*32),worker_parent=tmp_path/'staging.slice',worker_cgroup_parent='staging.slice',operator_parent=tmp_path/'operator',protected_domains=[])


def test_worker_birth_is_durable_empty_and_disjoint(tmp_path,monkeypatch):
    monkeypatch.setattr(owned_client,'boot_id',lambda:'boot')
    tmp_path.chmod(0o700)
    provisioning=owned_daemon.provision(tmp_path/'fresh',unit='mldsafail-owned-daemon-test.service',protected_roots=[tmp_path/'staging'])
    worker=tmp_path/('mldsafail-owned-workers-'+provisioning['id']+'.slice');worker.mkdir()
    operator=tmp_path/'operator';operator.mkdir()
    monkeypatch.setattr(owned_client,'prepare_domain',lambda *args:None)
    monkeypatch.setattr(owned_client,'populated',lambda path:True)
    with pytest.raises(RuntimeError,match='empty'):
        owned_daemon.bind_worker(provisioning,worker_parent=worker,worker_cgroup_parent=worker.name,operator_parent=operator,protected_domains=[])
    monkeypatch.setattr(owned_client,'populated',lambda path:False)
    with pytest.raises(RuntimeError,match='disjoint'):
        owned_daemon.bind_worker(provisioning,worker_parent=worker,worker_cgroup_parent=worker.name,operator_parent=operator,protected_domains=[worker])
    receipt=owned_daemon.bind_worker(provisioning,worker_parent=worker,worker_cgroup_parent=worker.name,operator_parent=operator,protected_domains=[])
    assert receipt['worker_birth']==owned_client.domain_identity(worker)
    monkeypatch.setenv('MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT',str(operator))
    owned_daemon._worker_binding(receipt,receipt['worker_birth'],worker.name)
    with pytest.raises(RuntimeError,match='disjoint'):
        owned_daemon._worker_binding(receipt,receipt['worker_birth'],worker.name,receipt['operator_domain'])


def test_stale_inactive_manifest_cannot_control_new_epoch(tmp_path,monkeypatch):
    manifest=fixture_manifest(tmp_path,monkeypatch)
    monkeypatch.setattr(owned_daemon,'load_manifest',lambda:dict(manifest,epoch='c'*32))
    monkeypatch.setattr(owned_daemon,'_unit',lambda unit:dict(ActiveState='inactive',unit_fragment_sha256='b'*64))
    killed=[]
    monkeypatch.setattr(owned_client,'stop',lambda entry:killed.append(entry))
    receipt=owned_daemon.shutdown_barrier(manifest,evidence_directory=tmp_path,attempt_id='attempt')
    assert not receipt['shutdown_proven'] and not killed
    assert (tmp_path/'worker/cgroup.kill').read_text()==''


def test_fifo_manifest_rejected_without_waiting_for_writer(tmp_path):
    os.mkfifo(tmp_path/'fifo',0o600)
    with pytest.raises(RuntimeError,match='Private owner'):
        owned_daemon.load_manifest(tmp_path/'fifo')


def test_restart_recovers_new_manifest_published_before_journal_ack(tmp_path,monkeypatch):
    manifest=fixture_manifest(tmp_path,monkeypatch)
    manifest.update(socket=str(tmp_path/'socket'),worker_cgroup_parent='owned.slice',provisioning={},server_version='native',server_git_commit='commit',daemon_executable_sha256='d'*64)
    refreshed=dict(manifest,epoch='c'*32,leader={'pid':456})
    monkeypatch.setattr(owned_daemon,'load_manifest',lambda *args:refreshed)
    verified=[]
    monkeypatch.setattr(owned_daemon,'verify_environment',lambda value:verified.append(value))
    intent=dict(schema='mldsafail.owned-daemon-restart-intent.v1',attempt_id='attempt',previous_epoch=manifest['epoch'],manifest_sha256=owned_daemon.fingerprint(manifest),unit=manifest['unit'],next_epoch=refreshed['epoch'])
    owned_daemon.publish(tmp_path/'attempt-daemon-restart-intent.json',intent)
    barrier=dict(schema='mldsafail.owned-daemon-barrier.v1',attempt_id='attempt',errors=[],shutdown_proven=True,daemon_manifest_sha256=owned_daemon.fingerprint(manifest),daemon_epoch=manifest['epoch'])
    result=owned_daemon.restart_and_refresh(manifest,barrier,manifest_path=tmp_path/'manifest',evidence_directory=tmp_path,attempt_id='attempt')
    assert result==refreshed and verified==[refreshed]
    monkeypatch.setattr(owned_daemon,'load_manifest',lambda *args:dict(refreshed,epoch='e'*32))
    with pytest.raises(RuntimeError,match='exact retained'):
        owned_daemon.restart_and_refresh(manifest,barrier,manifest_path=tmp_path/'manifest',evidence_directory=tmp_path,attempt_id='attempt')


@pytest.mark.parametrize('field,value',[('schema','wrong'),('errors',[{'step':'failed'}]),('attempt_id','other')])
def test_restart_rejects_corrupt_positive_barrier(tmp_path,monkeypatch,field,value):
    manifest=fixture_manifest(tmp_path,monkeypatch)
    barrier=dict(schema='mldsafail.owned-daemon-barrier.v1',attempt_id='attempt',errors=[],shutdown_proven=True,daemon_manifest_sha256=owned_daemon.fingerprint(manifest),daemon_epoch=manifest['epoch'])
    barrier[field]=value
    with pytest.raises(RuntimeError,match='Positive exact'):
        owned_daemon.restart_and_refresh(manifest,barrier,manifest_path=tmp_path/'manifest',evidence_directory=tmp_path,attempt_id='attempt')


def test_provisioned_daemon_config_cannot_inherit_or_change_staging_settings(tmp_path,monkeypatch):
    monkeypatch.setattr(owned_client,'boot_id',lambda:'boot')
    tmp_path.chmod(0o700)
    receipt=owned_daemon.provision(tmp_path/'fresh',unit='mldsafail-cpu-daemon-test.service',protected_roots=[tmp_path/'staging'])
    config=Path(receipt['daemon_config']['path'])
    assert owned_daemon.read_private_json(config)=={}
    config.write_text('{"live-restore":true}')
    with pytest.raises(RuntimeError,match='empty dedicated daemon config'):
        owned_daemon._provisioning(receipt,receipt['unit'],receipt['roots'])


def test_teardown_only_birth_capture_does_not_admit_new_operator_for_evaluation(tmp_path,monkeypatch):
    provision=dict(unit='mldsafail-owned-daemon-test.service',id='a'*32)
    worker=dict(path=str(tmp_path/('mldsafail-owned-workers-'+'a'*32+'.slice')))
    provision.update(worker_birth=worker,operator_domain={'path':str(tmp_path/'old-operator')},protected_domains=[])
    monkeypatch.setattr(owned_client,'domain_identity',lambda path: (_ for _ in ()).throw(FileNotFoundError()))
    owned_daemon._worker_binding(provision,worker,Path(worker['path']).name,teardown_only=True)
    with pytest.raises(FileNotFoundError):
        owned_daemon._worker_binding(provision,worker,Path(worker['path']).name)


def test_terminal_authority_cannot_evaluate_or_restart_even_with_valid_operator(tmp_path):
    manifest=dict(terminal_only=True)
    with pytest.raises(RuntimeError,match='Terminal-only'):
        owned_daemon.verify_environment(manifest)
    with pytest.raises(RuntimeError,match='Terminal-only'):
        owned_daemon.restart_and_refresh(manifest,{},manifest_path=tmp_path/'manifest',evidence_directory=tmp_path,attempt_id='terminal')


@pytest.mark.parametrize('terminal',[False,True])
def test_private_manifest_roundtrip_retains_terminal_authority(tmp_path,terminal):
    value={key:{} for key in ('roots','domain','leader','daemon_process','worker_domain','provisioning')}
    value.update(schema=owned_daemon.SCHEMA,epoch='a'*32,unit='fresh',socket='private',server_version='pinned',server_git_commit='pinned',daemon_executable_sha256='b'*64,unit_fragment_sha256='c'*64,worker_cgroup_parent='fresh.slice',terminal_only=terminal)
    path=tmp_path/'manifest.json'
    owned_daemon.publish(path,value)
    assert owned_daemon.load_manifest(path)==value
    value['terminal_only']='false'
    owned_daemon.publish(path,value)
    with pytest.raises(RuntimeError,match='versioned'): owned_daemon.load_manifest(path)


def test_docker_data_710_preserves_birth_identity_and_private_parent(tmp_path,monkeypatch):
    monkeypatch.setattr(owned_daemon.owned_client,'boot_id',lambda:'synthetic-boot')
    base=tmp_path/'owned';base.parent.chmod(0o700)
    provision=owned_daemon.provision(base,unit='mldsafail-cpu-daemon-permission.service',protected_roots=[tmp_path/'protected'])
    data=base/'root_dir';data.chmod(0o710)
    roots={name:owned_daemon._private_directory(row['path'],docker_data=name=='root_dir') for name,row in provision['roots'].items()}
    owned_daemon._provisioning(provision,provision['unit'],roots)
    assert provision['daemon_pidfile']==str(base/'dockerd.pid')
    with pytest.raises(RuntimeError):owned_daemon._private_directory(data)
    data.chmod(0o750)
    with pytest.raises(RuntimeError):owned_daemon._private_directory(data,docker_data=True)
    data.chmod(0o710);data.rename(base/'old-data');data.mkdir(mode=0o700)
    roots['root_dir']=owned_daemon._private_directory(data,docker_data=True)
    with pytest.raises(RuntimeError,match='roots differ'):owned_daemon._provisioning(provision,provision['unit'],roots)


def test_failed_startup_proof_is_distinct_and_rejects_uncertain_manager_request(tmp_path,monkeypatch):
    from deploy import owned_client
    monkeypatch.setattr(owned_client,'boot_id',lambda:'synthetic-boot')
    base=tmp_path/'owned';provision=owned_daemon.provision(base,unit='mldsafail-cpu-daemon-retire.service',protected_roots=[tmp_path/'protected'])
    worker=tmp_path/('mldsafail-cpu-workers-'+provision['id']+'.slice');worker.mkdir();(worker/'cgroup.procs').write_text('')
    provision.update(worker_birth={'path':str(worker)},operator_domain={'path':str(tmp_path/'operator')},protected_domains=[])
    state=dict(id='attempt',worker_slice=worker.name,commands=[dict(kind='daemon_start',state='passed',argv=['systemctl'])],provisioning=provision,daemon_unit=provision['unit'],manifest_path=str(base/'absent-manifest'),socket=str(base/'docker.sock'),units=[dict(path=provision['unit'],sha256='a'*64)])
    monkeypatch.setattr(owned_daemon,'_unit',lambda unit:dict(unit_fragment_sha256='a'*64,ActiveState='failed',MainPID='0',ControlGroup=''))
    monkeypatch.setattr(owned_daemon.subprocess,'check_output',lambda *a,**kw:b'[]')
    monkeypatch.setattr(owned_client,'verify_domain',lambda entry:worker)
    monkeypatch.setattr(owned_client,'populated',lambda domain:False)
    receipt=owned_daemon.failed_startup_barrier(state,evidence_directory=tmp_path,attempt_id='attempt')
    assert receipt['startup_shutdown_proven'] is True and receipt['healthy_daemon_registered'] is False
    state['commands'][0]['state']='uncertain'
    receipt=owned_daemon.failed_startup_barrier(state,evidence_directory=tmp_path,attempt_id='attempt')
    assert receipt['startup_shutdown_proven'] is False
