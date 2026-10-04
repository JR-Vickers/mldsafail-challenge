import json
from pathlib import Path
import pytest
from scripts.staging_load_orchestrator import Operator,FIXTURE


@pytest.fixture(autouse=True)
def synthetic_boot(monkeypatch):
    from deploy import owned_client
    monkeypatch.setattr(owned_client,'boot_id',lambda:'synthetic-test-boot')


def operator(tmp_path):
    value=object.__new__(Operator);value.root=tmp_path;value.path=tmp_path/'journal.json'
    value.c={'fixture_repository':'https://github.com/owner/reviewed-fixtures','user_id':'owner'}
    value.j={'run_id':'owned-run','clients':[]};return value


def test_submission_identity_is_durable_before_first_post(tmp_path):
    value=operator(tmp_path);seen=[]
    def api(route,payload,key):
        retained=json.loads(value.path.read_text())['submission_intent']
        assert retained['key']==key and retained['request']==payload
        assert payload['commit_sha']==FIXTURE and payload['solver_path']=='reference'
        seen.append(key);return {'submission':{'id':'owned-submission'}}
    value.api=api
    assert value.submit_once()=='owned-submission'
    assert seen==['owned-run-reference-load']


def test_lost_response_reconciles_once_without_reposting(tmp_path):
    value=operator(tmp_path);posts=[]
    def api(*args,**kwargs):posts.append(args);raise TimeoutError('lost response')
    value.api=api;value.probe=lambda *args,**kwargs:{'submission':'already-committed'}
    assert value.submit_once()=='already-committed'
    assert value.submit_once()=='already-committed'
    assert len(posts)==1
    assert json.loads(value.path.read_text())['submission']=='already-committed'


def test_unresolved_durable_intent_never_blindly_resubmits(tmp_path):
    value=operator(tmp_path);value.j['submission_intent']={'key':'retained-key'}
    value.api=lambda *args,**kwargs:pytest.fail('POST must not repeat')
    value.probe=lambda *args,**kwargs:{'submission':None}
    with pytest.raises(RuntimeError,match='never resubmit'):value.submit_once()


def test_failed_lookup_preserves_original_post_failure(tmp_path):
    value=operator(tmp_path);original=TimeoutError('original response loss')
    def api(*args,**kwargs):raise original
    def probe(*args,**kwargs):raise RuntimeError('lookup failed')
    value.api=api;value.probe=probe
    with pytest.raises(TimeoutError) as caught:value.submit_once()
    assert caught.value is original and 'lookup failed' in caught.value.__notes__[0].lower()


def test_partial_request_evidence_survives_normal_close_without_credentials(tmp_path):
    from scripts.staging_load_orchestrator import Progress
    path=tmp_path/'partial.jsonl';writer=Progress(path)
    writer.record({'route':'/api/v1/me','seconds':.01,'failed':False})
    writer.record({'route':'/health/ready','seconds':2,'failed':True})
    writer.close()
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows)==2 and rows[1]['failed'] is True
    assert path.stat().st_mode&0o777==0o600
    assert not writer.thread.is_alive()


def test_interrupted_measurement_is_not_repeated(tmp_path,monkeypatch):
    from scripts import staging_read_load
    value=operator(tmp_path);value.c['gate']='idle-read-load';value.j['state']='measuring'
    value.reconcile=lambda:None
    monkeypatch.setattr(staging_read_load,'run',lambda *args,**kwargs:pytest.fail('Measurement must not repeat'))
    with pytest.raises(RuntimeError,match='do not repeat'):value.execute()


def cleanup_ready(value):
    value.j.update(passed=True,identity={'epoch':'unchanged'})
    value.reconcile=lambda:None
    value.guard=lambda:True
    value.containers=lambda:[]
    value.identity=lambda:{'epoch':'unchanged'}


def test_cleanup_publication_after_rename_failure_retracts_positive(tmp_path):
    value=operator(tmp_path);cleanup_ready(value);original=OSError('directory fsync failed');calls=[]
    def save():
        value.path.write_text(json.dumps(value.j));calls.append(value.j['passed'])
        if len(calls)==1:raise original
    value.save=save
    with pytest.raises(OSError) as caught:value.cleanup()
    assert caught.value is original and calls==[True,False]
    retained=json.loads(value.path.read_text())
    assert retained['passed'] is False and retained['cleanup_complete'] is False
    assert retained['evidence_publication_failed'] is True


def test_corrupt_clients_keeps_known_cleanup_and_persistent_fence(tmp_path,monkeypatch):
    from deploy import owned_client
    value=operator(tmp_path);cleanup_ready(value);entry={'known':'identity'}
    value.j['clients']=[entry,None];stopped=[]
    monkeypatch.setattr(owned_client,'stop',lambda row:stopped.append(row))
    assert value.cleanup() is False
    assert stopped==[entry] and value.j['passed'] is False
    assert value.j['corrupt_clients_receipt']==[entry,None]
    assert value.cleanup() is False
    assert value.j['cleanup_complete'] is False


def health_inventory(value,monkeypatch):
    from deploy import owned_daemon
    from scripts.staging_load_orchestrator import SOURCE
    value.c.update(web_container='web',coordinator_container='coordinator',database_container='db',
        service_images={name:name+'-image' for name in ('web','db','coordinator','proxy')},release_manifest='private')
    monkeypatch.setattr(owned_daemon,'read_private_json',lambda path:{'source_commit':SOURCE,
        'images':{role:{'id':role+'-image'} for role in ('web','coordinator','worker')}})
    rows=[{'Name':'/'+name,'Image':image,'State':{'Running':True},'Config':{}} for name,image in value.c['service_images'].items()]
    for row in rows[:2]:row['Config']['Healthcheck']={'Test':['CMD','true']};row['State']['Health']={'Status':'healthy'}
    value.containers=lambda:rows;value.probe=lambda action:{'worker':'worker-image'}
    calls=[];value.api=lambda route,**kwargs:calls.append((route,kwargs))
    return rows,calls


def test_native_absent_coordinator_proxy_health_is_valid(tmp_path,monkeypatch):
    value=operator(tmp_path);rows,calls=health_inventory(value,monkeypatch)
    assert value.identity()=={'worker':'worker-image'}
    assert calls==[('/health/ready',{'json_response':False})]


@pytest.mark.parametrize('status',['unhealthy','starting','invalid'])
def test_present_health_must_be_healthy(tmp_path,monkeypatch,status):
    value=operator(tmp_path);rows,_=health_inventory(value,monkeypatch)
    rows[2]['State']['Health']={'Status':status}
    with pytest.raises(RuntimeError,match='Health not healthy'):value.identity()


@pytest.mark.parametrize('index',[0,1])
def test_web_database_missing_required_health_is_rejected(tmp_path,monkeypatch,index):
    value=operator(tmp_path);rows,_=health_inventory(value,monkeypatch)
    rows[index]['State'].pop('Health')
    with pytest.raises(RuntimeError,match='Health missing'):value.identity()
