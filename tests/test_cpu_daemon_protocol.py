from pathlib import Path
import pytest
from deploy import owned_daemon, owned_client

def fixture_manifest(tmp_path,monkeypatch):
    monkeypatch.setattr(owned_client,'boot_id',lambda:'boot')
    domains=[]
    for name in ('daemon','worker'):
        path=tmp_path/name;path.mkdir()
        for control,value in [('cgroup.events','populated 0\n'),('cgroup.kill','')]: (path/control).write_text(value)
        domains.append(owned_client.domain_identity(path))
    return dict(schema=owned_daemon.SCHEMA,epoch='a'*32,unit='mldsafail-owned-daemon-test.service',
                unit_fragment_sha256='b'*64,domain=domains[0],worker_domain=domains[1],
                leader={'pid':123},roots={})


def test_guardian_receipt_requires_raw_immutable_acknowledgement(monkeypatch,tmp_path):
    import sys
    from research.cpu_measurement import guardian, mutations
    monkeypatch.setattr(owned_daemon,'load_manifest',lambda:{'epoch':'a'*32})
    monkeypatch.setattr(owned_daemon,'verify_environment',lambda manifest:manifest)
    path=tmp_path/'receipt.json'
    guardian.mutate([sys.executable,'-c','print("b"*64)'],path,'a'*32,'create')
    result=mutations.receipt(tmp_path,path.name,operation='create',epoch='a'*32)
    assert result['container_id']=='b'*64
    import json
    result['container_id']='c'*64
    path.write_text(json.dumps(result))
    with pytest.raises(RuntimeError,match='raw response'):
        mutations.receipt(tmp_path,path.name,operation='create',epoch='a'*32)
    guardian.mutate([sys.executable,'-c','print("not an ID")'],path,'a'*32,'create')
    with pytest.raises(RuntimeError,match='incomplete'):
        mutations.receipt(tmp_path,path.name,operation='create',epoch='a'*32)


@pytest.mark.parametrize('malformation',['missing_file','missing_reference','missing_phase','array'])
def test_unknown_guardian_request_barriers_before_client_cancel_and_restart(monkeypatch,tmp_path,malformation):
    from research.cpu_measurement import mutations
    manifest=fixture_manifest(tmp_path,monkeypatch)
    parent=Path(manifest['worker_domain']['path'])
    journal=dict(generation='a'*32,parent_device=manifest['worker_domain']['device'],
                 parent_inode=manifest['worker_domain']['inode'],mutations=[
        dict(operation='dedicated_daemon_verified',manifest=manifest),
        dict(operation='host_client_domain',id='client',phase='create',receipt_file='missing.json'),
        dict(operation='host_client_release_intent',id='client')])
    if malformation=='missing_reference': journal['mutations'][1].pop('receipt_file')
    if malformation=='missing_phase': journal['mutations'][1].pop('phase')
    if malformation=='array':
        (tmp_path/'missing.json').write_text('[]');(tmp_path/'missing.json').chmod(0o600)
    order=[]
    monkeypatch.setenv('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST',str(tmp_path/'manifest.json'))
    monkeypatch.setattr(owned_daemon,'shutdown_barrier',lambda *args,**kwargs:order.append('barrier') or {'schema':'mldsafail.owned-daemon-barrier.v1','attempt_id':journal['generation'],'shutdown_proven':True,'errors':[],'daemon_epoch':manifest['epoch'],'daemon_manifest_sha256':owned_daemon.fingerprint(manifest)})
    monkeypatch.setattr(owned_client,'stop',lambda entry:order.append('client_stop'))
    monkeypatch.setattr(owned_daemon,'restart_and_refresh',lambda *args,**kwargs:order.append('restart') or {'epoch':'new'})
    assert mutations.resolve(journal,tmp_path,parent)['errors']==[]
    assert order==['barrier','client_stop','restart']
    (tmp_path/(journal['generation']+'-mutation-repair.json')).unlink()
    order.clear()
    monkeypatch.setattr(owned_daemon,'shutdown_barrier',lambda *args,**kwargs:order.append('barrier') or {'shutdown_proven':False,'errors':[{'step':'daemon_shutdown_failed'}]})
    assert mutations.resolve(journal,tmp_path,parent)['errors']
    assert order==['barrier']


def test_malformed_receipt_shape_is_uncertain_not_unhandled(tmp_path):
    from research.cpu_measurement.mutations import receipt
    import pytest
    path=tmp_path/'bad.json'
    path.write_text('[]');path.chmod(0o600)
    with pytest.raises(RuntimeError,match='object'):
        receipt(tmp_path,'bad.json',operation='create',epoch='a'*32)


def test_incomplete_guardian_closes_parent_pipes_without_cancelling_mutator(tmp_path,monkeypatch):
    import io
    from types import SimpleNamespace
    from research.cpu_measurement import client
    streams=[io.BytesIO() for _ in range(3)]
    process=SimpleNamespace(stdin=streams[0],stdout=streams[1],stderr=streams[2],poll=lambda:0)
    monkeypatch.setattr(client,'spawn',lambda *args,**kwargs:(process,{'id':'client'}))
    monkeypatch.setattr(owned_client,'stop',lambda entry: (_ for _ in ()).throw(AssertionError('Uncertain guardian must survive until barrier')))
    owner=SimpleNamespace(record={'generation':'a'*32},directory=tmp_path,mutation=lambda *args,**kwargs:None)
    with pytest.raises(RuntimeError,match='incomplete'):
        client.mutation(['docker','create'],owner,tmp_path,{'epoch':'b'*32},'create')
    assert all(stream.closed for stream in streams)


def test_fifo_guardian_receipt_rejected_without_waiting_for_writer(tmp_path):
    import os
    from research.cpu_measurement.mutations import receipt
    os.mkfifo(tmp_path/'fifo',0o600)
    with pytest.raises(RuntimeError,match='Private guardian'):
        receipt(tmp_path,'fifo',operation='create',epoch='a'*32)


def test_live_proxy_fence_allows_shutdown_cleanup_but_prohibits_new_epoch(tmp_path,monkeypatch):
    import os
    from research.cpu_measurement import mutations
    manifest=fixture_manifest(tmp_path,monkeypatch)
    parent=Path(manifest['worker_domain']['path'])
    journal=dict(generation='a'*32,parent_device=manifest['worker_domain']['device'],parent_inode=manifest['worker_domain']['inode'],mutations=[
        dict(operation='dedicated_daemon_verified',manifest=manifest),
        dict(operation='host_client_domain',id='client',phase='create',receipt_file='missing.json'),
        dict(operation='host_client_release_intent',id='client')])
    executor=dict(pid=123,start_ticks=456,uid=os.getuid(),session=123,group=123,cmdline_sha256='c'*64,boot_id='boot')
    guard=dict(schema='mldsafail.cpu-native-transport-guard.v1',generation=journal['generation'],daemon_epoch=manifest['epoch'],executor=executor,state='pending')
    owned_daemon.publish(tmp_path/(journal['generation']+'-native-transport.json'),guard)
    order=[]
    monkeypatch.setenv('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST',str(tmp_path/'manifest'))
    monkeypatch.setattr(owned_client,'identity',lambda pid:executor)
    monkeypatch.setattr(owned_client,'stop',lambda entry:order.append('client_stop'))
    monkeypatch.setattr(owned_daemon,'shutdown_barrier',lambda *args,**kwargs:order.append('barrier') or dict(schema='mldsafail.owned-daemon-barrier.v1',attempt_id=journal['generation'],errors=[],shutdown_proven=True,daemon_epoch=manifest['epoch'],daemon_manifest_sha256=owned_daemon.fingerprint(manifest)))
    monkeypatch.setattr(owned_daemon,'restart_and_refresh',lambda *args,**kwargs:order.append('restart') or {'epoch':'new'})
    result=mutations.resolve(journal,tmp_path,parent)
    assert any(row['step']=='native_transport_fence' for row in result['errors'])
    assert order==['barrier','client_stop']
    # Once the exact executor has exited, every thread is gone; retry reuses
    # retained positive old barrier instead of signaling a newer daemon epoch.
    monkeypatch.setattr(owned_client,'identity',lambda pid: (_ for _ in ()).throw(ProcessLookupError()))
    order.clear()
    assert mutations.resolve(journal,tmp_path,parent)['errors']==[]
    assert order==['client_stop','restart']
