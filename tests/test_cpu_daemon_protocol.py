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


def test_unknown_guardian_request_barriers_before_client_cancel_and_restart(monkeypatch,tmp_path):
    from research.cpu_measurement import mutations
    manifest=fixture_manifest(tmp_path,monkeypatch)
    parent=Path(manifest['worker_domain']['path'])
    journal=dict(generation='a'*32,parent_device=manifest['worker_domain']['device'],
                 parent_inode=manifest['worker_domain']['inode'],mutations=[
        dict(operation='dedicated_daemon_verified',manifest=manifest),
        dict(operation='host_client_domain',id='client',phase='create',receipt_file='missing.json'),
        dict(operation='host_client_release_intent',id='client')])
    order=[]
    monkeypatch.setenv('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST',str(tmp_path/'manifest.json'))
    monkeypatch.setattr(owned_daemon,'shutdown_barrier',lambda *args,**kwargs:order.append('barrier') or {'shutdown_proven':True,'errors':[]})
    monkeypatch.setattr(owned_client,'stop',lambda entry:order.append('client_stop'))
    monkeypatch.setattr(owned_daemon,'restart_and_refresh',lambda *args,**kwargs:order.append('restart') or {'epoch':'new'})
    assert mutations.resolve(journal,tmp_path,parent)['errors']==[]
    assert order==['barrier','client_stop','restart']
    order.clear()
    monkeypatch.setattr(owned_daemon,'shutdown_barrier',lambda *args,**kwargs:order.append('barrier') or {'shutdown_proven':False,'errors':[{'step':'daemon_shutdown_failed'}]})
    assert mutations.resolve(journal,tmp_path,parent)['errors']
    assert order==['barrier']
