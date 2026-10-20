"""Synthetic-only production operation verification; no Docker/evaluation resources."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

import pytest

from deploy.production_preparation import SOURCE, IMAGES, FINGERPRINT
from deploy.production_receipts import digest, validate_receipt, render
from scripts import production_epoch_operation as op
from test_production_preparation import prepared


def private(path, value):
    path.write_text(json.dumps(value)); path.chmod(0o600)
    return path


@pytest.fixture
def packet(tmp_path, monkeypatch):
    original_output = subprocess.check_output
    revision = original_output(['git','rev-parse','HEAD'],text=True).strip()
    def source_output(args, **kwargs):
        if args[:2] == ['git','show'] and args[2].startswith(revision + ':'):
            source = args[2].split(':', 1)[1]
            if source in (*op.OPERATOR_FILES, 'scripts/production_epoch_operation.py', 'docs/PRODUCTION_EPOCH_PROCEDURE.md'):
                return Path(source).read_bytes()
        return original_output(args, **kwargs)
    monkeypatch.setattr(subprocess, 'check_output', source_output)
    tmp_path.chmod(0o700)
    env, staging, manifest = prepared(tmp_path)
    env['ROOTLESS_DOCKER_SOCKET'] = '/run/user/1000/docker.sock'
    paths = {}
    for name, values in [('candidate', env), ('staging', staging), ('retained', {'POSTGRES_PASSWORD': 'r'*40, 'MLDSAFAIL_SECRET_KEY': 's'*40})]:
        p = tmp_path / (name + '.env')
        p.write_text(''.join(k+'='+v+'\n' for k,v in values.items())); p.chmod(0o600); paths[name] = str(p)
    images = {k: {'index': 'sha256:'+v, 'platform_manifest': 'sha256:'+'d'*64, 'configuration': 'sha256:'+'e'*64} for k,v in IMAGES.items()}
    roots = [env[k] for k in ('PRODUCTION_EVALUATOR_ROOT','PRODUCTION_TLS_ROOT','PRODUCTION_ACME_WEBROOT')]
    expected_paths = roots + [roots[0]+'/jobs', roots[0]+'/secrets/signing.key']
    inventory = private(tmp_path/'retained-inventory.json', [dict(root='/tmp/'+n+'/state',exists=True,environment='POSTGRES_PASSWORD=retained-fixture\n',compose={'name':'trial','services':{},'volumes':{}}) for n in ('pr-261016-a','pr-261017-b','pr-261017-c','pr-261018-c')])
    host = dict(time=time.time(), uid=1000, account='mldsafail', info={'ID':'daemon','SecurityOptions':['name=rootless']},
        images=[dict(Id='sha256:'+v, Os='linux', Architecture='amd64', Config={'Labels':{'org.mldsafail.source':SOURCE,'org.mldsafail.trusted':FINGERPRINT}}) for v in IMAGES.values()],
        paths=[dict(path=p,resolved=p,symlinks=[]) for p in expected_paths] + [dict(path=env['ROOTLESS_DOCKER_SOCKET'],resolved=env['ROOTLESS_DOCKER_SOCKET'],uid=1000,mode=0o140600,symlinks=[])],
        containers=[],volumes=[],mountinfo='1 2 0:1 / / rw - ext4 /dev/root rw\n')
    artifact_inventory = private(tmp_path/'artifacts.json', [dict(image=i['index'],whole_hash_matches=True,bad_blobs=[],descriptor_errors=[],descriptors=[dict(digest=i['platform_manifest'],platform=dict(architecture='amd64',os='linux'))],configs=[dict(digest='blobs/sha256/'+i['configuration'].split(':')[1],architecture='amd64',os='linux')]) for i in images.values()])
    inspection = private(tmp_path/'inspection.json',host)
    receipt = dict(inspection_helper_sha256=digest('deploy/production_inspection.py'),schema='mldsafail.production-inspection.v1',candidate_sha256=digest(paths['candidate']),inspection=str(inspection),inspection_sha256=digest(inspection),source=SOURCE,daemon_id='daemon',images=images,artifact_inventory=str(artifact_inventory),artifact_inventory_sha256=digest(artifact_inventory),retained_inventory=str(inventory),retained_inventory_sha256=digest(inventory),
        retained_environments=[paths['retained']],retained_sha256={paths['retained']:digest(paths['retained'])},retained_roots=[str(tmp_path/'retained-root')],compose_sha256=digest('compose.production.yaml'))
    receipt_path = private(tmp_path/'receipt.json',receipt)
    manifest_path = private(tmp_path/'manifest.json',manifest)
    operation = tmp_path/'operation'
    p = dict(operator_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),schema='mldsafail.production-operation.v1',purpose=op.PURPOSE,source=SOURCE,helper_hashes=op.source_hashes(),operator_hashes={p:digest(p) for p in op.OPERATOR_FILES},wrapper_sha256=digest(op.__file__),runbook_sha256=digest('docs/PRODUCTION_EPOCH_PROCEDURE.md'),benchmark_version='0.5.0',
        host={'address':'178.128.17.58','account':'mldsafail','uid':1000,'socket':'/run/user/1000/docker.sock','host_key':'SHA256:OtjIfXCrqewb9FTJ8jpU7Rq7aZL4P8P7U0dKZ8DoB5w'},
        controller=images['COORDINATOR_IMAGE'],worker=images['WORKER_IMAGE'],candidate=paths['candidate'],candidate_sha256=digest(paths['candidate']),staging=paths['staging'],receipt=str(receipt_path),receipt_sha256=digest(receipt_path),manifest=str(manifest_path),manifest_sha256=digest(manifest_path),
        limits=dict(memory='512m',cpus='1',pids='256',create_timeout=5400,audit_timeout=600,inspection_timeout=20,process_timeout=10),operation_id='a'*32,worker_cgroup='reviewed.slice',operation=str(operation),final_destination=str(tmp_path/'final'),epoch=env['PRODUCTION_EVALUATOR_ROOT']+'/epoch',lock=str(tmp_path/'production-epoch.lock'),attempt=str(tmp_path/'production-epoch.attempt.json'),remote_bundle=str(tmp_path),hostname='fixture',daemon_id='daemon',coordinator_ids=['coordinator'],allowed_running_services=['web','db'])
    path = private(tmp_path/'packet.json',p)
    return path, p, env, receipt


def test_receipt_and_synthetic_render(packet):
    path,p,env,r = packet
    assert validate_receipt(env,p['candidate'],p['receipt'],preparation=True) == []
    seen = []
    def runner(args, **kw):
        seen.append((args,kw))
        return subprocess.CompletedProcess(args,0,stdout=json.dumps({'name':'mldsafail-production','volumes':{n:{'name':'mldsafail-production_'+n} for n in ('postgres_data','caddy_data','caddy_config')},'services':{'db':{'environment':{'POSTGRES_DB':'mldsafail'}},'web':{'environment':{'MLDSAFAIL_DATABASE_URL':'postgresql://hidden@db/mldsafail'}}}}))
    assert render(env,preparation=True,runner=runner) == []
    assert 'SYNTHETIC_RENDER_ONLY' in seen[0][1]['env']['MLDSAFAIL_MLWE_EPOCH_ID']
    assert 'MLDSAFAIL_MLWE_EPOCH_ID' not in env
    assert 'config' in seen[0][0] and 'up' not in seen[0][0]


@pytest.mark.parametrize('mutation', ['stale','daemon','image','secret','volume','mount','symlink','candidate','missing_epoch'])
def test_receipt_rejects_invalid_evidence(packet,mutation):
    _,p,env,r = packet
    host=json.loads(Path(r['inspection']).read_text())
    if mutation=='stale':host['time']-=86401
    if mutation=='daemon':host['info']['ID']='other'
    if mutation=='image':host['images'][0]['Id']='sha256:'+'0'*64
    if mutation=='secret':Path(r['retained_environments'][0]).write_text('POSTGRES_PASSWORD='+env['POSTGRES_PASSWORD']+'\n')
    if mutation=='volume':host['volumes']=[{'Name':'mldsafail-production_postgres_data'}]
    if mutation=='mount':host['mountinfo']='1 2 0:1 / '+env['PRODUCTION_EVALUATOR_ROOT']+' rw - ext4 /dev/root rw'
    if mutation=='symlink':host['paths'][0]['symlinks']=['alias']
    if mutation=='candidate':Path(p['candidate']).write_text('changed')
    private(Path(r['inspection']),host);r['inspection_sha256']=digest(r['inspection']);private(Path(p['receipt']),r)
    assert validate_receipt(env,p['candidate'],p['receipt'],preparation=mutation!='missing_epoch') == ['inspection_receipt_invalid_or_stale']


@pytest.mark.parametrize('key', ['purpose','source','helper_hashes','wrapper_sha256','controller','limits','host','candidate_sha256'])
def test_packet_mismatches(packet,key):
    path,p,_,_=packet;p[key]='wrong';private(path,p)
    with pytest.raises((ValueError,TypeError)):op.prepare(path)


def test_prepare_requires_no_evaluation(packet,monkeypatch):
    path,p,_,_=packet
    monkeypatch.setattr(op,'render',lambda *a,**k:[])
    monkeypatch.setattr(op,'stream',lambda *a,**k:pytest.fail('evaluation during preparation'))
    assert op.prepare(path)['epoch_pending']
    assert not Path(p['operation']).exists() and not Path(p['attempt']).exists()
    with pytest.raises((ValueError,TypeError)):op.execute(path,None)
    auth=private(path.parent/'authorization.json',{'purpose':'disposable_rehearsal_only','review_file':str(private(path.parent/'review.json',{'decision':'pending'}))})
    with pytest.raises(ValueError):op.execute(path,auth)


def mock_execution(packet,monkeypatch):
    path,p,_,_=packet
    monkeypatch.setattr(op,'render',lambda *a,**k:[])
    monkeypatch.setattr(op,'live_gate',lambda p:{'fixture':True})
    review=private(path.parent/'review.json',dict(packet_sha256=digest(path),decision='approved',reviewer='independent_fixture'))
    auth=private(path.parent/'authorization.json',dict(review_file=str(review),review_sha256=digest(review),purpose=op.PURPOSE,packet_sha256=digest(path),authorized_by='owner'))
    return path,p,auth


@pytest.mark.parametrize('failure',[None,'before','creation','timeout','interrupt','audit'])
def test_single_attempt_and_terminal_failures(packet,monkeypatch,failure):
    path,p,auth=mock_execution(packet,monkeypatch)
    calls=[]
    def stream(p,audit=False):
        calls.append(audit)
        operation=Path(p['operation'])
        (operation/('audit.stdout' if audit else 'create.stdout')).write_text('partial')
        (operation/('audit.stdout' if audit else 'create.stdout')).chmod(0o600)
        if failure in ('creation','timeout','interrupt') and not audit:
            raise {'creation':RuntimeError,'timeout':subprocess.TimeoutExpired,'interrupt':KeyboardInterrupt}[failure](*(['fixture',1] if failure=='timeout' else []))
        if audit:
            if failure=='audit':raise RuntimeError('audit failed')
            private(operation/'audit.stdout',dict(epoch_id='actual',reference_cases=100,environment={'image_id':p['worker']['index'],'trusted_fingerprint':FINGERPRINT,'host':{'ID':p['daemon_id']}}))
        else:
            epoch=Path(p['epoch']);epoch.mkdir()
            private(epoch/'manifest.json',dict(id='actual',environment={'image_id':p['worker']['index'],'trusted_fingerprint':FINGERPRINT,'host':{'ID':p['daemon_id']}}))
            private(epoch/'reference-costs.json',{'fixture':True})
            private(epoch/'COMPLETE.json',{'benchmark_version':'0.5.0','files':{x.name:digest(x) for x in epoch.iterdir()}})
    monkeypatch.setattr(op,'stream',stream)
    if failure=='before':
        monkeypatch.setattr(op,'live_gate',lambda p:(_ for _ in ()).throw(RuntimeError()))
        with pytest.raises(RuntimeError):op.execute(path,auth)
        assert not Path(p['attempt']).exists();assert not calls;return
    if failure in ('creation','timeout','interrupt'):
        with pytest.raises(BaseException):op.execute(path,auth)
        assert json.loads((Path(p['operation'])/'journal.json').read_text())['state']=='creation_failed'
    else:
        op.execute(path,auth)
        if failure=='audit':
            with pytest.raises(RuntimeError):op.audit(path)
        else:
            op.audit(path)
            destination=path.parent/'final'
            op.finalize(path,destination)
            final=json.loads((destination/'binding.json').read_text());assert final['epoch_id']=='actual'
            assert json.loads((destination/'preflight.json').read_text())['ready']
    assert Path(p['attempt']).exists()
    with pytest.raises(ValueError):op.execute(path,auth)
    with pytest.raises(ValueError):op.audit(path)
    assert calls.count(False)==1
    if failure:
        assert (Path(p['operation'])/'create.stdout').read_text()=='partial'
        with pytest.raises(ValueError):op.finalize(path,path.parent/'forbidden-final')


def test_nonblocking_lock(packet):
    _,p,_,_=packet
    with op.locked(p):
        with pytest.raises(BlockingIOError):
            with op.locked(p):pytest.fail('second lock admitted')


def test_stream_preserves_partial_logs_on_timeout(packet,monkeypatch):
    _,p,_,_=packet;Path(p['operation']).mkdir(mode=0o700)
    class Process:
        returncode=None
        def __init__(self,args,stdout,stderr,env):stdout.write(b'partial output');stderr.write(b'partial error')
        def wait(self,timeout):
            if self.returncode is None:raise subprocess.TimeoutExpired('fixture',timeout)
            return self.returncode
        def poll(self):return self.returncode
        def terminate(self):self.returncode=-15
    monkeypatch.setattr(op.subprocess,'Popen',Process)
    stopped=[];monkeypatch.setattr(op,'terminate_owned',lambda p:stopped.append(p['operation_id']))
    with pytest.raises(subprocess.TimeoutExpired):op.stream(p)
    assert stopped==[p['operation_id']]
    assert (Path(p['operation'])/'create.stdout').read_bytes()==b'partial output'
    assert (Path(p['operation'])/'create.stderr').read_bytes()==b'partial error'
    assert json.loads((Path(p['operation'])/'create.exit.json').read_text())['terminal']


def test_audit_mount_is_readonly_and_has_no_socket(packet):
    _,p,_,_=packet
    command=op.controller(p,audit=True)
    assert not any('/var/run/docker.sock' in x for x in command)
    assert any(x.endswith(',readonly') and str(Path(p['epoch']).parent) in x for x in command)
    assert 'audit_epoch' in command[-1] and 'seal(' not in command[-1]


@pytest.mark.parametrize('running,restart', [(True,'no'),(False,'always'),(False,'unless-stopped')])
def test_live_gate_rejects_unfenced_existing_coordinator(packet, monkeypatch, running, restart):
    _,p,_,_=packet
    monkeypatch.setattr(op.os,'getuid',lambda:1000)
    monkeypatch.setattr(op.socket,'gethostname',lambda:'fixture')
    class Endpoint:
        def stat(self):
            return type('Status',(),{'st_mode':0o140600,'st_uid':1000})()
    monkeypatch.setattr(op,'safe_path',lambda _:Endpoint())
    monkeypatch.setattr(op,'read_receipt',lambda _:dict(inspection='fixture'))
    monkeypatch.setattr(op,'read_manifest',lambda _:dict(time=time.time()))
    monkeypatch.setattr('deploy.production_receipts.validate_receipt',lambda *a,**k:[])
    def docker(p,args,**kwargs):
        if args[0]=='info':value={'ID':'daemon','SecurityOptions':['rootless']}
        elif args[0]=='image':value=[{'Id':args[-1],'Os':'linux','Architecture':'amd64'}]
        elif args[0]=='container':value=[{'State':{'Running':running},'HostConfig':{'RestartPolicy':{'Name':restart}}}]
        else:pytest.fail('Unfenced coordinator must be rejected before further work')
        return subprocess.CompletedProcess(args,0,stdout=json.dumps(value))
    monkeypatch.setattr(op,'docker',docker)
    with pytest.raises(ValueError):op.live_gate(p)


def test_changed_sealed_evidence_cannot_finalize(packet,monkeypatch):
    path,p,auth=mock_execution(packet,monkeypatch)
    operation=Path(p['operation']);operation.mkdir(mode=0o700)
    epoch=Path(p['epoch']);epoch.mkdir(parents=True,mode=0o700)
    private(epoch/'manifest.json',{'id':'actual'})
    private(epoch/'COMPLETE.json',{'benchmark_version':'0.5.0','files':{'manifest.json':digest(epoch/'manifest.json')}})
    private(operation/'journal.json',dict(packet_sha256=digest(path),state='audited'))
    private(operation/'audited.json',dict(seal_sha256=digest(epoch/'COMPLETE.json'),packet_sha256=digest(path)))
    private(epoch/'manifest.json',{'id':'altered'})
    with pytest.raises(ValueError):op.finalize(path,Path(p['final_destination']))
    assert not Path(p['final_destination']).exists()


def test_private_records_reject_hardlinks_symlinks_and_duplicate_fields(tmp_path):
    from deploy.production_preparation import read_manifest
    tmp_path.chmod(0o700)
    path=private(tmp_path/'receipt.json',{})
    alias=tmp_path/'alias.json';os.link(path,alias)
    with pytest.raises(ValueError):read_manifest(path)
    alias.unlink();alias.symlink_to(path)
    with pytest.raises(ValueError):read_manifest(alias)
    path.write_text('{"schema":1,"schema":2}')
    with pytest.raises(ValueError):read_manifest(path)


def test_unavailable_retained_record_does_not_become_readiness_boolean(packet):
    _,p,env,r=packet
    inventory=json.loads(Path(r['retained_inventory']).read_text());inventory[0]['exists']=False
    private(Path(r['retained_inventory']),inventory)
    r['retained_inventory_sha256']=digest(r['retained_inventory']);r['images_locally_resolved']=True
    private(Path(p['receipt']),r)
    assert validate_receipt(env,p['candidate'],p['receipt'],preparation=True)


def test_relative_bundle_bindings_survive_relocation(packet,monkeypatch):
    import shutil
    path,p,env,r=packet
    for key in ('inspection','artifact_inventory','retained_inventory'):
        r[key]=Path(r[key]).name
    r['retained_environments']=[Path(x).name for x in r['retained_environments']]
    r['retained_sha256']={Path(k).name:v for k,v in r['retained_sha256'].items()}
    private(Path(p['receipt']),r)
    p['receipt_sha256']=digest(p['receipt'])
    for key in ('candidate','manifest','receipt','staging'):p[key]=Path(p[key]).name
    private(path,p)
    moved=path.parent/'bundle-copy';shutil.copytree(path.parent,moved,ignore=lambda root,names:['bundle-copy'])
    moved.chmod(0o700)
    assert digest(path)==digest(moved/path.name)
    loaded=op.read_packet(moved/path.name)
    assert op.validate(loaded)
    assert validate_receipt(env,loaded['candidate'],loaded['receipt'],preparation=True)==[]


def test_unexecuted_trial_requires_bound_withdrawal_and_empty_lifecycle(packet):
    _,p,env,r=packet
    inventory=json.loads(Path(r['retained_inventory']).read_text())
    inventory[2]['exists']=False
    private(Path(r['retained_inventory']),inventory);r['retained_inventory_sha256']=digest(r['retained_inventory'])
    cleanup=private(Path(p['receipt']).parent/'cleanup.json',{'trial_roots':[{'path':'/home/mldsafail/.mlf-production-rehearsal-20261017-c','journals':[],'daemon_roots':[]}]})
    withdrawal=private(Path(p['receipt']).parent/'withdrawal.json',{'text':'approval was withdrawn before execution. No C epoch has been generated.'})
    r['unstarted_trial_evidence']=dict(cleanup_inventory=str(cleanup),cleanup_sha256=digest(cleanup),withdrawal_record=str(withdrawal),withdrawal_sha256=digest(withdrawal))
    private(Path(p['receipt']),r)
    assert not validate_receipt(env,p['candidate'],p['receipt'],preparation=True)
    private(cleanup,{'trial_roots':[{'path':'/home/mldsafail/.mlf-production-rehearsal-20261017-c','journals':['started'],'daemon_roots':[]}]})
    r['unstarted_trial_evidence']['cleanup_sha256']=digest(cleanup);private(Path(p['receipt']),r)
    assert validate_receipt(env,p['candidate'],p['receipt'],preparation=True)


def test_only_verified_upstream_non_amd64_absences_are_allowed(packet):
    _,p,env,r=packet
    artifacts=json.loads(Path(r['artifact_inventory']).read_text())
    caddy=next(a for a in artifacts if a['image']=='sha256:'+IMAGES['CADDY_IMAGE'])
    caddy['descriptor_errors']=[{'digest':'sha256:'+'f'*64,'mediaType':'application/vnd.oci.image.manifest.v1+json','platform':{'architecture':'arm64','os':'linux'}} for _ in range(12)]
    private(Path(r['artifact_inventory']),artifacts);r['artifact_inventory_sha256']=digest(r['artifact_inventory']);private(Path(p['receipt']),r)
    assert not validate_receipt(env,p['candidate'],p['receipt'],preparation=True)
    caddy['descriptor_errors'][0]['platform']['architecture']='amd64'
    private(Path(r['artifact_inventory']),artifacts);r['artifact_inventory_sha256']=digest(r['artifact_inventory']);private(Path(p['receipt']),r)
    assert validate_receipt(env,p['candidate'],p['receipt'],preparation=True)


def test_preflight_cli_reports_only_future_epoch_for_valid_preparation(packet,monkeypatch,capsys):
    from deploy.production_preflight import main
    _,p,env,_=packet
    monkeypatch.setattr('deploy.production_receipts.render',lambda *a,**k:[])
    args=['preflight','--production-env',p['candidate'],'--staging-env',p['staging'],
          '--preparation-manifest',p['manifest'],'--inspection-receipt',p['receipt']]
    monkeypatch.setattr('sys.argv',args+['--preparation'])
    assert not main()
    result=capsys.readouterr().out
    assert result=='unresolved_dependency:MLDSAFAIL_MLWE_EPOCH_ID\npreparation_checks_passed_full_readiness_pending_epoch\n'
    assert all(env[k] not in result for k in ('POSTGRES_PASSWORD','MLDSAFAIL_SECRET_KEY'))
    monkeypatch.setattr('sys.argv',args)
    assert main()
    assert 'epoch_binding_not_finalized' in capsys.readouterr().out


def test_timeout_cleanup_skips_stopped_owned_resources(packet,monkeypatch):
    _,p,_,_=packet
    killed=[]
    def docker(p,args,**kwargs):
        if args[0]=='ps':value='stopped\nrunning\n'
        elif args[0]=='container':
            value=json.dumps([{'Config':{'Labels':{'org.mldsafail.production-epoch':p['operation_id']}},'State':{'Running':args[-1]=='running'}}])
        else:
            assert args==['kill','running'];killed.append('running');value=''
        return subprocess.CompletedProcess(args,0,stdout=value)
    monkeypatch.setattr(op,'docker',docker)
    op.terminate_owned(p)
    assert killed==['running']


def test_final_destination_cannot_alias_scientific_evidence(packet):
    path,p,_,_=packet
    p['final_destination']=str(Path(p['epoch'])/'final-config')
    private(path,p)
    with pytest.raises(ValueError):op.prepare(path)
