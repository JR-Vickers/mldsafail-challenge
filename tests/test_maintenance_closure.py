import json
import shutil
import subprocess

import pytest

from deploy.maintenance_transport import admit_helper, helper_identity, InspectedAuthority
from deploy.maintenance_bundle import materialize, validate, sha
from scripts.maintenance_service_context import inspect


def container():
    return dict(Id='id', Image='config-image',Name='/helper',State=dict(StartedAt='birth',Pid=10,Running=True),
        Config=dict(Image='image',Labels={'org.mldsafail.maintenance-helper':'helper'}),
        HostConfig=dict(NetworkMode='container:db',PortBindings={},ReadonlyRootfs=True,Memory=64*1024**2,
                        MemorySwap=64*1024**2,NanoCpus=100000000,PidsLimit=16,CgroupParent='operation.slice',
                        Privileged=False,CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],LogConfig={'Type':'none'}),
        Mounts=[dict(Destination='/maintenance_transport.py',Source='/source.py',RW=False)])


def test_helper_exact_admission_and_birth():
    row=container()
    assert admit_helper(row,name='helper',image='image',database='db',parent='operation.slice',source='/source.py')['started_at']=='birth'
    for mutation in ('network','ports','mount','memory'):
        changed=container()
        if mutation=='network': changed['HostConfig']['NetworkMode']='host'
        if mutation=='ports': changed['HostConfig']['PortBindings']={'5432/tcp':[{}]}
        if mutation=='mount': changed['Mounts'][0]['RW']=True
        if mutation=='memory': changed['HostConfig']['Memory']=128*1024**2
        with pytest.raises(RuntimeError):
            admit_helper(changed,name='helper',image='image',database='db',parent='operation.slice',source='/source.py')


def test_inspected_authority_rejects_database_replacement(tmp_path):
    source=tmp_path/'source.py';source.write_text('source')
    expected=dict(database_container='db',daemon='daemon',database_started_at='birth',database_image='image',
                  operator_sha256=sha(source),connection_authority=dict(host='localhost',port=5432,dbname='db',user='u'))
    row=dict(Id='db',Image='image',State=dict(Running=True,StartedAt='birth'))
    def command(args):
        return json.dumps({'ID':'daemon'} if args[0]=='info' else [row]).encode()
    probe=InspectedAuthority(command,expected,str(source))
    assert probe()==expected
    row['State']['StartedAt']='restart'
    with pytest.raises(RuntimeError): probe()


def test_bundle_relative_receipts_survive_relocation_and_reject_missing(tmp_path):
    source=tmp_path/'inputs';source.mkdir()
    (source/'raw').write_text('raw evidence')
    (source/'receipt.json').write_text(json.dumps({'measurement':'../raw'}))
    files={'raw':dict(source=str(source/'raw'),sha256=sha(source/'raw')),
           'records/receipt.json':dict(source=str(source/'receipt.json'),sha256=sha(source/'receipt.json'))}
    refs=[dict(source='records/receipt.json',pointer='/measurement',relative_target='../raw',sha256=sha(source/'raw'))]
    materialize(tmp_path/'bundle',files,refs,unresolved=['runtime context pending'])
    shutil.copytree(tmp_path/'bundle',tmp_path/'relocated')
    assert validate(tmp_path/'relocated')['dependencies_complete'] is False
    (tmp_path/'relocated/raw').unlink()
    with pytest.raises(ValueError): validate(tmp_path/'relocated')


def test_service_context_strips_secrets_and_does_not_infer_path():
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args,0,stdout=b'Id=test.service\nLoadState=loaded\nEnvironment="PASSWORD=secret" "PATH=/service/bin:/usr/bin"\n',stderr=b'')
    value=inspect(runner=run)
    assert 'secret' not in json.dumps(value)
    assert all(row['properties']['EnvironmentPATH']==['/service/bin:/usr/bin'] for row in value['units'].values())
    assert all(not row['service_path_complete'] for row in value['units'].values())
    assert all('show' in args for args in calls)


def test_supervisor_full_lifecycle_and_context(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from contextvars import ContextVar
    import threading
    from deploy.maintenance_supervisor import Supervisor
    active=ContextVar('test-active',default=False)
    class Fence:
        intent={'ceilings':dict(stop=1,create=1,audit=1,inspection=1,cleanup=1,restoration=1)}
        phase_deadline=None
        failed=threading.Event()
        def acquire(self): pass
        def verify(self): return True
        def release(self): pass
        def resources_stopped(self,check): assert check() is True
        @contextmanager
        def phase(self,name,terminate): yield
    @contextmanager
    def bind(*args):
        token=active.set(True)
        try: yield
        finally: active.reset(token)
    monkeypatch.setattr('deploy.maintenance_supervisor.bind_operation',bind)
    order=[]
    def action(name):
        def run():
            if name in ('create','audit','inspection'): assert active.get()
            order.append(name)
            return True
        return run
    names=('exclude_scheduling','stop_coordinator','create','audit','inspection','terminate','resources_stopped','postflight','restore','watch_state')
    supervisor=Supervisor(tmp_path,Fence(),dict(operation_id='o',state='execution_ready'),{name:action(name) for name in names})
    supervisor.run(dict(purpose='production_maintenance',state='execution_ready'))
    assert order[:5]==['exclude_scheduling','stop_coordinator','create','audit','inspection']
    assert order[-1]=='restore'
    assert json.loads((tmp_path/'supervisor.json').read_text())['phase']=='complete'


def test_supervisor_hung_action_cannot_certify_cleanup(tmp_path):
    import threading
    from deploy.maintenance_supervisor import Supervisor
    gate=threading.Event()
    class Fence:
        intent={'ceilings':{'cleanup':.05}}
        phase_deadline=None
        failed=threading.Event()
    supervisor=Supervisor(tmp_path,Fence(),dict(operation_id='o'),{'terminate':lambda:gate.wait(5)})
    try:
        with pytest.raises(RuntimeError,match='deadline'):
            supervisor.call('terminate',cleanup=True)
        with pytest.raises(RuntimeError,match='reconciliation'):
            supervisor.stop_watch()
    finally:
        gate.set()
        for thread in supervisor.pending: thread.join(timeout=1)


def test_helper_journal_keeps_cleanup_authority(tmp_path):
    from deploy.maintenance_transport import OwnedHelper
    helper=object.__new__(OwnedHelper)
    helper.root=tmp_path
    tmp_path.chmod(0o700)
    helper._persist(dict(state='create_intent',name='helper',image='image',parent='parent',source='source'))
    helper._persist(dict(state='started',container='container',birth={'pid':1}))
    value=json.loads((tmp_path/'helper.json').read_text())
    assert value['image']=='image' and value['parent']=='parent' and value['source']=='source'


def test_transport_reconcile_attempts_every_owned_helper(tmp_path,monkeypatch):
    from deploy.maintenance_transport import OwnedHelper,reconcile_transport
    for index in range(2): (tmp_path/f'connection-{index}').mkdir()
    seen=[]
    def reconcile(*args):
        seen.append(args[0].name)
        if args[0].name=='connection-0':raise RuntimeError('ambiguous')
    monkeypatch.setattr(OwnedHelper,'reconcile',reconcile)
    with pytest.raises(RuntimeError,match='incomplete'):
        reconcile_transport(tmp_path,{},None,[],'image','source')
    assert seen==['connection-0','connection-1']
