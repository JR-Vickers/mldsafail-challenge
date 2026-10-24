"""Owned service identity/resource regressions; no native PostgreSQL claim."""
from types import SimpleNamespace
import time
import pytest
from deploy.workload_fixture_database import OwnedDatabase,LABEL
from deploy.workload_release import canonical
from mldsafail.evaluator.workload import WorkloadBlocked


class Resources:
    def __init__(self):
        self.settings=dict(postgres_image='sha256:'+'a'*64);self.calls=[];self.row=None
    def docker(self,args,**kwargs):
        self.calls.append(args)
        if args[:2]==['image','inspect']:return canonical([dict(Id=self.settings['postgres_image'])])
        if args[0]=='create':
            labels={args[i+1].split('=',1)[0]:args[i+1].split('=',1)[1] for i,item in enumerate(args) if item=='--label'}
            self.row=dict(Id='b'*64,Name='/'+args[args.index('--name')+1],Created='created',Image=self.settings['postgres_image'],
                Config=dict(Labels=labels),HostConfig=dict(NetworkMode='bridge',ReadonlyRootfs=True,Memory=128*1024**2,
                MemorySwap=128*1024**2,PidsLimit=32,RestartPolicy=dict(Name='no')),
                State=dict(Running=False,StartedAt=''),NetworkSettings=dict(Ports={'5432/tcp':[dict(HostIp='127.0.0.1',HostPort='54321')]}))
            return self.row['Id'].encode()
        if args[0]=='inspect':return canonical([self.row])
        if args[0]=='start':self.row['State']=dict(Running=True,StartedAt='started');return b''
        if args[0]=='rm':self.row=None;return b''
        if args[0]=='ps':return (self.row['Id'] if self.row else '').encode()
        raise AssertionError(args)


def database(tmp_path,monkeypatch):
    import scripts.workload_fixture_worker as worker
    import scripts.rehearse_workload_installation_fixture as review
    monkeypatch.setattr(worker,'inherited_lock',lambda *args:None)
    monkeypatch.setattr(review,'component_review',lambda *args:None)
    fixture=SimpleNamespace(root=tmp_path,lock_fd=5,require_target=lambda:None,binding='f'*64,manifest=dict(generation='c'*32))
    native=SimpleNamespace(config=dict(retained_services={'database':'retained'}));resources=Resources()
    control_root=tmp_path/'artifacts'/('control-'+'d'*32);control_root.mkdir(mode=0o700,parents=True)
    (control_root/'intent.json').write_bytes(canonical(dict(generation='c'*32,manifest_sha256='f'*64,token='d'*32)))
    (control_root/'intent.json').chmod(0o600)
    db=OwnedDatabase(fixture,resources,native,control_root,'d'*32,time.monotonic()+10)
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,*args):return self
        def fetchone(self):return ('mldsafail_acceptance_'+'d'*32,123)
    monkeypatch.setattr(db,'connect',lambda *args:Connection())
    return db,resources,native


def test_owned_database_fixed_create_and_cleanup_preserve_retained_binding(tmp_path,monkeypatch):
    db,resources,native=database(tmp_path,monkeypatch);db.start()
    assert native.config['retained_services']['database']=='retained'
    create=next(args for args in resources.calls if args[0]=='create')
    assert create[create.index('--publish')+1]=='127.0.0.1::5432'
    assert '--pids-limit=32' in create
    assert db.password not in ' '.join(create)
    assert db.credentials_file.stat().st_mode&0o777==0o600
    result=db.cleanup(time.monotonic()+10)
    assert result['remaining']==[] and result['retained_database_touched'] is False
    assert native.config['retained_services']=={'database':'retained'}


@pytest.mark.parametrize('change',[
    lambda row:row.update(Created='replacement'),
    lambda row:row['State'].update(StartedAt='replacement'),
    lambda row:row['Config']['Labels'].update({LABEL:'replacement'}),
    lambda row:row['HostConfig'].update(NetworkMode='host'),
])
def test_substituted_resource_blocks_cleanup_without_rm(tmp_path,monkeypatch,change):
    db,resources,_=database(tmp_path,monkeypatch);db.start();change(resources.row)
    with pytest.raises(WorkloadBlocked):db.cleanup(time.monotonic()+10)
    assert resources.row is not None and not any(args[0]=='rm' for args in resources.calls)


def test_missing_create_ack_never_adopts_name_or_label(tmp_path,monkeypatch):
    db,resources,_=database(tmp_path,monkeypatch)
    with pytest.raises(WorkloadBlocked,match='unacknowledged_preserve'):db.cleanup(time.monotonic()+10)
    assert not resources.calls


def test_database_oid_replacement_closes_connection_and_blocks(tmp_path,monkeypatch):
    db,resources,_=database(tmp_path,monkeypatch);db.start()
    del db.connect
    class Connection:
        closed=False
        def execute(self,*args):return self
        def fetchone(self):return ('mldsafail_acceptance_'+'d'*32,999)
        def close(self):self.closed=True
    connection=Connection()
    import psycopg
    monkeypatch.setattr(psycopg,'connect',lambda **kwargs:connection)
    with pytest.raises(WorkloadBlocked,match='oid_changed_preserve'):db.connect()
    assert connection.closed
