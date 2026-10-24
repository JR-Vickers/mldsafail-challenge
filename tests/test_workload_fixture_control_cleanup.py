"""Abrupt case-worker recovery with real private records and inert Docker/kernel.

Only generation-owned files/sockets/cgroup stand-ins are touched. These tests
exercise production reconstruction and identity checks, never native acceptance.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

import deploy.workload_fixture_control_cleanup as cleanup
from deploy.workload_installation import Journal,exclusive,identity,private
from deploy.workload_release import canonical,digest
from mldsafail.evaluator.native_workload import NativeRuntime,LABEL,birth,values
from mldsafail.evaluator.workload import ResourcePolicy,WorkloadBlocked
from tests.test_native_workload import fixture as native_fixture
from tests.test_workload_installation import packet

TOKEN='a'*32;GENERATION='b'*32;WORKLOAD='c'*32
CONTROL='inspected_births';SCENARIO='daemon_replacement'
COMPUTE='d'*64;DATABASE='e'*64;RETAINED='f'*64;PG_IMAGE='sha256:'+'1'*64


@pytest.fixture
def owned(tmp_path,monkeypatch,native_fixture):
    from deploy.workload_configuration import materialize,measured_resources
    import scripts.workload_fixture_worker as worker
    import scripts.rehearse_workload_installation_fixture as rehearsal
    proposal,_,_,_=packet(tmp_path);source=proposal['identities']
    root=tmp_path/'fixture';root.mkdir(mode=0o700);(root/'artifacts').mkdir(mode=0o700)
    journal_root=root/'runtime-journal';journal_root.mkdir(mode=0o700)
    fixture=SimpleNamespace(root=root,lock_fd=9,manifest=dict(generation=GENERATION),binding='9'*64)
    fixture.journal=Journal(journal_root,fixture.binding)
    marker=root/'target';marker.write_bytes(b'owned target')
    def target():assert marker.read_bytes()==b'owned target'
    fixture.require_target=target;fixture.proposal=lambda:(canonical(proposal),proposal)
    def inherited(path,fd):assert path==root and fd==9
    monkeypatch.setattr(worker,'inherited_lock',inherited)
    monkeypatch.setattr(rehearsal,'component_review',lambda actual:target() if actual is fixture else pytest.fail('wrong fixture'))
    config=deepcopy(native_fixture[0].config)
    heavy=native_fixture[3];cgroup=native_fixture[4]
    source['resources']['delegation']=dict(state='proposed',path=str(heavy),
        ancestors=[dict(state='observed',**birth(cgroup))])
    source['resources']['output']['path']=config['output']
    template=deepcopy(config);template['heavy_birth']={'$birth':'delegation'};template['ancestors']={'$ancestor_chain':'delegation'}
    raw=canonical(template);source['recipe']['configuration_templates']['native']=raw.hex()
    source['manifest']['configurations']['native']=dict(path=str(tmp_path/'installed-native.json'),sha256=digest(raw))
    installed=materialize(source,measured_resources(source))['native'];exclusive(tmp_path/'installed-native.json',installed)
    assert installed!=raw  # Cleanup must use actual materialized births.
    control_root=root/'artifacts'/('control-'+TOKEN);control_root.mkdir(mode=0o700)
    exclusive(control_root/'intent.json',canonical(dict(generation=GENERATION,manifest_sha256=fixture.binding,
        control=CONTROL,scenario=SCENARIO,token=TOKEN,envelope=dict(startup=30,case=90,cleanup=45,postflight=15))))
    baseline=dict(verified=True,retained_services=dict(web=RETAINED));exclusive(control_root/'baseline.json',canonical(baseline))
    retained=tmp_path/'retained-service';retained.write_bytes(b'unchanged retained service')
    store=tmp_path/'containers.json';store.write_bytes(canonical({RETAINED:dict(Id=RETAINED,Config=dict(Labels={}),State=dict(Running=True))}))
    calls=[];interruption=[None]
    scope=heavy/('mldsafail-heavy-'+WORKLOAD+'.slice')
    original_rmdir=Path.rmdir
    def remove_cgroup(path):
        if path==scope or path.parent==scope:
            for item in path.iterdir():
                assert item.name in ('cgroup.events','cgroup.kill') and item.is_file()
                item.unlink()
        return original_rmdir(path)
    monkeypatch.setattr(Path,'rmdir',remove_cgroup)
    def run(argv,*,seconds=35,inner_seconds=None):
        assert 0<seconds<=4.65 and inner_seconds==.65
        calls.append(argv);rows=json.loads(store.read_bytes())
        if argv[:2]==['/usr/bin/systemctl','--user']:
            assert argv==['/usr/bin/systemctl','--user','stop',scope.name]
            assert not any(item.is_dir() for item in scope.iterdir());scope.rmdir();return b''
        assert argv[:3]==config['docker'];args=argv[3:]
        if args[0]=='info':return canonical(dict(ID='daemon',CgroupDriver='systemd',CgroupVersion='2',SecurityOptions=['name=rootless']))
        if args[0]=='ps':
            found=[]
            filters=[args[index+1].removeprefix('label=') for index,value in enumerate(args) if value=='--filter']
            for identifier,row in rows.items():
                if all(row['Config'].get('Labels',{}).get(term.split('=',1)[0])==term.split('=',1)[1] for term in filters):found.append(identifier)
            return '\n'.join(found).encode()
        if args[0]=='inspect':return canonical([rows[args[1]]])
        assert args[1] in (COMPUTE,DATABASE)  # Never retained IDs or names.
        if args[0]=='kill':rows[args[1]]['State'].update(Running=False,Pid=0)
        elif args[0]=='rm':del rows[args[1]]
        else:raise AssertionError(args)
        store.write_bytes(canonical(rows))
        if interruption[0]==args[0]:raise InterruptedError('lost '+args[0]+' acknowledgement')
        return b''
    def postflight(proposal):
        assert retained.read_bytes()==b'unchanged retained service'
        return deepcopy(baseline)
    resources=SimpleNamespace(run=run,settings=dict(postgres_image=PG_IMAGE),postflight=postflight)
    configuration=cleanup.prepare_context(fixture,proposal,CONTROL,SCENARIO,TOKEN,baseline)
    native=NativeRuntime(configuration,run=lambda argv:run(argv,seconds=4.65,inner_seconds=.65))
    state=dict(schema='mldsafail.workload.v1',workload_id=WORKLOAD,policy_sha256=ResourcePolicy().sha256,
        kind='administration',reference=dict(fixture=SCENARIO,generation=GENERATION),identity=native.identity(),
        ceiling=1024**2,phase='running',paused=False,resources=[dict(id=COMPUTE)],requests={})
    evidence_root=control_root/'evidence';evidence_root.mkdir(mode=0o700);evidence=Journal(evidence_root,fixture.binding)
    cleanup.acquisition_intent(control_root,state,evidence.append)
    scope.mkdir();leaf=scope/'creators';leaf.mkdir()
    for node in (scope,leaf):
        (node/'cgroup.events').write_text('populated 1\n');(node/'cgroup.kill').write_text('0')
    output=Path(configuration['output'])/WORKLOAD;output.mkdir(mode=0o700)
    record=dict(schema='mldsafail.native-workload.v1',workload_id=WORKLOAD,scope_path=str(scope),scope=birth(scope),
        leaf=birth(leaf),output=str(output),phase='prepared',controllers=[],revoked=False,
        baseline=dict(output=native.output_mount(ResourcePolicy())))
    exclusive(control_root/'runtime'/ (WORKLOAD+'.native.json'),canonical(record))
    cleanup.prepared_scope(control_root,state,native,evidence.append)
    exclusive(control_root/'runtime/workload.json',canonical(state))
    real_values=values
    def kernel_values(path):
        path=Path(path)
        if path.name=='cgroup.events' and (scope/'cgroup.kill').exists() and (scope/'cgroup.kill').read_text()=='1':
            path.write_text('populated 0\n')
        return real_values(path)
    monkeypatch.setattr(cleanup,'values',kernel_values)
    return SimpleNamespace(fixture=fixture,resources=resources,root=control_root,proposal=proposal,configuration=configuration,
        native=native,state=state,record=record,evidence=evidence,scope=scope,leaf=leaf,output=output,store=store,
        calls=calls,retained=retained,interruption=interruption)


def add_compute(owned,*,started=True,router_state=None):
    created=dict(id=COMPUTE,created_at='compute-created',name='mlwe-fixture-'+WORKLOAD,started_at=None,
        operation_id=WORKLOAD,scope=owned.record['scope'])
    exclusive(owned.root/'created-container.json',canonical(created))
    owned.evidence.append('control_container_created',observed=identity(owned.root/'created-container.json'),binding=deepcopy(created))
    if started:
        value=dict(created,started_at='compute-started');exclusive(owned.root/'started-container.json',canonical(value))
        owned.evidence.append('control_container_started',observed=identity(owned.root/'started-container.json'),binding=deepcopy(value))
    router=owned.output/'router';router.mkdir(mode=0o700)
    exclusive(router/(created['name']+'.json'),canonical(dict(operation_id=WORKLOAD,name=created['name'],
        state=router_state or ('running' if started else 'create_intent'),container_id=COMPUTE,created_at=created['created_at'])))
    row=dict(Id=COMPUTE,Created=created['created_at'],Name='/'+created['name'],Image=owned.configuration['worker']['image'],
        Config=dict(Labels={LABEL:WORKLOAD,'org.mldsafail.fixture-control':owned.root.name,'org.mldsafail.fixture-generation':GENERATION}),
        HostConfig=dict(CgroupParent=owned.scope.name,NetworkMode='none',ReadonlyRootfs=True,Memory=32*1024**2,
            MemorySwap=32*1024**2,PidsLimit=16,RestartPolicy=dict(Name='no'),NanoCpus=100000000,
            LogConfig=dict(Type='none'),CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],Binds=[]),
        State=dict(Running=started,Pid=777 if started else 0,StartedAt='compute-started' if started else ''))
    rows=json.loads(owned.store.read_bytes());rows[COMPUTE]=row;owned.store.write_bytes(canonical(rows))


def add_database(owned):
    root=owned.root/'database';root.mkdir(mode=0o700)
    name='mlwe-fixture-database-'+TOKEN
    exclusive(root/'intent.json',canonical(dict(generation=GENERATION,manifest_sha256=owned.fixture.binding,
        token=TOKEN,name=name,image=PG_IMAGE)))
    created=dict(id=DATABASE,created_at='pg-created',started_at=None,image=PG_IMAGE)
    exclusive(root/'created.json',canonical(created));exclusive(root/'started.json',canonical(dict(created,started_at='pg-started')))
    owned.fixture.journal.append('fixture_control_database_created',token=TOKEN,observed=identity(root/'created.json'),binding=deepcopy(created))
    owned.fixture.journal.append('fixture_control_database_started',token=TOKEN,observed=identity(root/'started.json'),binding=dict(created,started_at='pg-started'))
    row=dict(Id=DATABASE,Created='pg-created',Name='/'+name,Image=PG_IMAGE,
        Config=dict(Labels={cleanup.DB_LABEL:TOKEN,'org.mldsafail.fixture-generation':GENERATION}),
        HostConfig=dict(NetworkMode='bridge',ReadonlyRootfs=True,Memory=128*1024**2,MemorySwap=128*1024**2,
            PidsLimit=32,RestartPolicy=dict(Name='no'),Binds=[],NanoCpus=250000000,LogConfig=dict(Type='none'),
            Tmpfs={'/var/lib/postgresql/data':'rw,size=64m','/var/run/postgresql':'rw,size=8m','/tmp':'rw,size=8m'}),
        NetworkSettings=dict(Ports={'5432/tcp':[dict(HostIp='127.0.0.1',HostPort='54321')]}),
        State=dict(Running=True,Pid=888,StartedAt='pg-started'))
    rows=json.loads(owned.store.read_bytes());rows[DATABASE]=row;owned.store.write_bytes(canonical(rows))


def execute(owned,**kwargs):return cleanup.cleanup(owned.fixture,owned.resources,CONTROL,SCENARIO,TOKEN,**kwargs)


def test_abrupt_worker_death_reconstructs_exact_resources_and_postflight(owned):
    add_compute(owned);add_database(owned)
    # Real SIGKILL skips finally. The fresh cleanup has no original gate/runtime
    # object or in-memory created list from that dead worker.
    marker=owned.root/'forbidden-finally'
    code='import os,signal,pathlib\ntry:os.kill(os.getpid(),signal.SIGKILL)\nfinally:pathlib.Path('+repr(str(marker))+').write_text("ran")'
    child=subprocess.run([sys.executable,'-c',code]);assert child.returncode==-signal.SIGKILL and not marker.exists()
    result=execute(owned)
    assert result['remaining']==[] and result['gate_state']['paused'] and result['transactions']=='resolved'
    assert result['scope_termination']['state']=='removed'
    assert set(json.loads(owned.store.read_bytes()))=={RETAINED}
    postflight=cleanup.postflight(owned.fixture,owned.resources,CONTROL,SCENARIO,TOKEN)
    assert postflight['retained_before']==postflight['retained_after'] and postflight['paused']
    assert owned.retained.read_bytes()==b'unchanged retained service'


@pytest.mark.parametrize('change',['container_birth','container_start','container_generation','scope','leaf','context','acquisition',
    'missing_acquisition_ack','missing_create_ack','missing_start_ack','database_birth','database_ack','database_policy','unknown_container'])
def test_replaced_or_unacknowledged_resources_preserve_and_block(owned,change):
    add_compute(owned);add_database(owned)
    rows=json.loads(owned.store.read_bytes())
    if change=='container_birth':rows[COMPUTE]['Created']='replaced'
    elif change=='container_start':rows[COMPUTE]['State']['StartedAt']='restarted'
    elif change=='container_generation':rows[COMPUTE]['Config']['Labels']['org.mldsafail.fixture-generation']='0'*32
    elif change in ('scope','leaf'):
        path=owned.scope if change=='scope' else owned.leaf
        path.rename(path.with_name(path.name+'-preserved'));path.mkdir()
        (path/'cgroup.events').write_text('populated 0\n');(path/'cgroup.kill').write_text('0')
    elif change=='context':(owned.root/'cleanup-context.json').write_bytes(b'{}')
    elif change=='acquisition':
        path=owned.root/'acquisition-intent.json';row=private(path)[1];row['workload_id']='0'*32;path.write_bytes(canonical(row))
    elif change=='missing_acquisition_ack':
        owned.evidence.rows=[];owned.evidence.path.write_bytes(b'')
    elif change=='missing_create_ack':(owned.root/'created-container.json').unlink()
    elif change=='missing_start_ack':(owned.root/'started-container.json').unlink()
    elif change=='database_birth':rows[DATABASE]['Created']='replaced'
    elif change=='database_ack':(owned.root/'database/created.json').unlink()
    elif change=='database_policy':rows[DATABASE]['HostConfig']['NetworkMode']='host'
    elif change=='unknown_container':rows['2'*64]=dict(rows[COMPUTE],Id='2'*64)
    owned.store.write_bytes(canonical(rows))
    with pytest.raises((WorkloadBlocked,FileNotFoundError)):execute(owned)
    assert not any('kill' in argv[3:] or 'rm' in argv[3:] for argv in owned.calls)
    assert json.loads(owned.store.read_bytes())==rows
    assert owned.retained.read_bytes()==b'unchanged retained service'


def test_unacknowledged_async_creator_blocks_even_with_empty_census(owned):
    router=owned.output/'router';router.mkdir(mode=0o700)
    exclusive(router/'pending.json',canonical(dict(state='create_intent',operation_id=WORKLOAD,name='pending')))
    with pytest.raises(WorkloadBlocked,match='router_unacknowledged'):execute(owned)
    assert not any('rm' in argv[3:] for argv in owned.calls)


def test_known_created_but_never_started_lost_ack_is_cleanable(owned):
    add_compute(owned,started=False)
    result=execute(owned)
    assert result['remaining']==[] and set(json.loads(owned.store.read_bytes()))=={RETAINED}
    assert not any('kill' in argv[3:] for argv in owned.calls)


def test_unacknowledged_prepare_does_not_adopt_matching_named_scope(owned):
    path=owned.root/'runtime'/(WORKLOAD+'.native.json');row=private(path)[1];row['scope']=None;path.write_bytes(canonical(row))
    with pytest.raises(WorkloadBlocked,match='prepared_scope_unacknowledged|scope_birth_unacknowledged'):execute(owned)
    assert (owned.scope/'cgroup.kill').read_text()=='0'
    assert not any('stop' in argv for argv in owned.calls)


def test_partial_evidence_still_safety_stops_acknowledged_scope_then_blocks(owned):
    with owned.evidence.path.open('ab') as stream:stream.write(b'{"partial":')
    with pytest.raises(WorkloadBlocked,match='partial_evidence'):execute(owned)
    assert (owned.scope/'cgroup.kill').read_text()=='1'
    assert not any('rm' in argv[3:] for argv in owned.calls)


def test_interrupted_removal_preserves_receipts_for_fresh_reconstruction(owned):
    add_compute(owned);owned.interruption[0]='rm'
    with pytest.raises(InterruptedError):execute(owned)
    assert private(owned.root/'runtime/workload.json')[1]['paused'] is True
    assert COMPUTE not in json.loads(owned.store.read_bytes())
    owned.interruption[0]=None
    result=execute(owned)
    assert result['remaining']==[]
    assert len([argv for argv in owned.calls if argv[3:]==['rm',COMPUTE]])==1


def test_cleanup_of_already_removed_case_resources_uses_absence_not_native_record(owned):
    add_compute(owned);rows=json.loads(owned.store.read_bytes());del rows[COMPUTE];owned.store.write_bytes(canonical(rows))
    owned.leaf.rmdir();owned.scope.rmdir()
    result=execute(owned)
    assert result['scope_termination']['state']=='removed'
    assert not any('rm' in argv[3:] or 'stop' in argv for argv in owned.calls)


def test_missing_database_create_ack_blocks_even_without_a_current_container(owned):
    root=owned.root/'database';root.mkdir(mode=0o700)
    exclusive(root/'intent.json',canonical(dict(generation=GENERATION,manifest_sha256=owned.fixture.binding,
        token=TOKEN,name='mlwe-fixture-database-'+TOKEN,image=PG_IMAGE)))
    with pytest.raises(WorkloadBlocked,match='database_ack_missing'):execute(owned)
    assert set(json.loads(owned.store.read_bytes()))=={RETAINED}


def test_missing_start_ack_blocks_even_when_start_has_not_yet_become_visible(owned):
    add_compute(owned,started=False,router_state='start_intent')
    with pytest.raises(WorkloadBlocked,match='start_ack_missing'):execute(owned)
    assert COMPUTE in json.loads(owned.store.read_bytes())


def test_expired_cleanup_never_starts_effects(owned):
    with pytest.raises(WorkloadBlocked,match='cleanup_expired'):execute(owned,deadline=time.monotonic()-1)
    assert (owned.scope/'cgroup.kill').read_text()=='0'
    assert not (owned.root/'independent-cleanup.json').exists()


def test_live_case_gate_lock_blocks_independent_effects(owned):
    from mldsafail.evaluator.workload import HostGate
    gate=HostGate(owned.root/'runtime',owned.native)
    with gate.locked(),pytest.raises(WorkloadBlocked,match='host_busy'):execute(owned)
    assert (owned.scope/'cgroup.kill').read_text()=='0'


def test_known_extra_cgroup_and_quota_are_removed_only_from_bound_births(owned):
    extra=owned.scope/'fixture-writer';extra.mkdir()
    for name,value in [('cgroup.events','populated 0\n'),('cgroup.kill','0')]: (extra/name).write_text(value)
    owned.evidence.append('control_cgroup_created',observed=birth(extra))
    quota=owned.output/'fixture-quota.bin';exclusive(quota,b'x'*64)
    owned.evidence.append('control_quota_file_created',observed=identity(quota,content=False))
    assert execute(owned)['verified'] is True
    assert not extra.exists() and not quota.exists()


@pytest.mark.parametrize('replacement',['quota','extra'])
def test_replaced_case_files_or_cgroups_remain_preserved(owned,replacement):
    if replacement=='quota':
        path=owned.output/'fixture-quota.bin';exclusive(path,b'original')
        owned.evidence.append('control_quota_file_created',observed=identity(path,content=False))
        path.rename(owned.output/'preserved');exclusive(path,b'unknown')
    else:
        path=owned.scope/'fixture-writer';path.mkdir()
        (path/'cgroup.events').write_text('populated 0\n');(path/'cgroup.kill').write_text('0')
        owned.evidence.append('control_cgroup_created',observed=birth(path))
        path.rename(owned.scope/'preserved-extra');path.mkdir()
        (path/'cgroup.events').write_text('populated 0\n');(path/'cgroup.kill').write_text('0')
    with pytest.raises(WorkloadBlocked):execute(owned)
    assert path.exists() and not (owned.root/'independent-cleanup.json').exists()


def test_natural_owned_stop_transition_does_not_masquerade_as_replacement(owned):
    add_compute(owned);original=owned.resources.run;inspections=[0]
    def run(argv,**kwargs):
        if argv[3:]==['inspect',COMPUTE]:
            inspections[0]+=1
            if inspections[0]==2:
                rows=json.loads(owned.store.read_bytes());rows[COMPUTE]['State'].update(Running=False,Pid=0)
                owned.store.write_bytes(canonical(rows))
        return original(argv,**kwargs)
    owned.resources.run=run
    assert execute(owned)['verified'] is True
    assert not any(argv[3:]==['kill',COMPUTE] for argv in owned.calls)


def test_postflight_rejects_reappeared_known_container_or_replaced_scope(owned):
    add_compute(owned);assert execute(owned)['verified']
    rows=json.loads(owned.store.read_bytes());rows[COMPUTE]=dict(Id=COMPUTE,Config=dict(Labels={}),State=dict(Running=False))
    owned.store.write_bytes(canonical(rows))
    with pytest.raises(WorkloadBlocked,match='container_survives'):
        cleanup.postflight(owned.fixture,owned.resources,CONTROL,SCENARIO,TOKEN)
    del rows[COMPUTE];owned.store.write_bytes(canonical(rows));owned.scope.mkdir()
    (owned.scope/'cgroup.events').write_text('populated 0\n')
    with pytest.raises(WorkloadBlocked,match='scope_changed'):
        cleanup.postflight(owned.fixture,owned.resources,CONTROL,SCENARIO,TOKEN)


def test_legacy_name_adoption_runtime_termination_is_never_called(owned,monkeypatch):
    add_compute(owned)
    monkeypatch.setattr(NativeRuntime,'terminate',lambda *args:pytest.fail('name-adoption cleanup forbidden'))
    assert execute(owned)['verified'] is True


@pytest.mark.parametrize('receipt',['created-container.json','started-container.json','database/created.json','database/started.json','prepared-scope.json'])
def test_identical_receipt_bytes_with_substituted_birth_do_not_establish_ownership(owned,receipt):
    add_compute(owned);add_database(owned)
    path=owned.root/receipt;data=path.read_bytes();path.rename(path.with_name(path.name+'.preserved'));exclusive(path,data)
    with pytest.raises(WorkloadBlocked):execute(owned)
    assert not any('rm' in argv[3:] or 'kill' in argv[3:] for argv in owned.calls)
    assert set(json.loads(owned.store.read_bytes()))=={RETAINED,COMPUTE,DATABASE}


def test_another_valid_workload_record_cannot_replace_this_case_acquisition(owned):
    other='3'*32;scope=owned.scope.parent/('mldsafail-heavy-'+other+'.slice');scope.mkdir()
    leaf=scope/'creators';leaf.mkdir()
    for node in (scope,leaf):
        (node/'cgroup.events').write_text('populated 0\n');(node/'cgroup.kill').write_text('0')
    state=deepcopy(owned.state);state['workload_id']=other
    (owned.root/'runtime/workload.json').write_bytes(canonical(state))
    record=dict(owned.record,workload_id=other,scope_path=str(scope),scope=birth(scope),leaf=birth(leaf),
        output=str(Path(owned.configuration['output'])/other))
    exclusive(owned.root/'runtime'/(other+'.native.json'),canonical(record))
    with pytest.raises(WorkloadBlocked,match='acquisition_unacknowledged_or_changed'):execute(owned)
    assert (scope/'cgroup.kill').read_text()=='0' and (owned.scope/'cgroup.kill').read_text()=='0'


def test_missing_prepared_scope_ack_never_adopts_even_empty_matching_scope(owned):
    # Rewrite a valid hash chain without the ACK, representing interruption
    # after the private receipt write but before its acknowledgement.
    rows=[row for row in owned.evidence.rows if row['event']!='control_native_prepared']
    owned.evidence.path.unlink();fresh=Journal(owned.evidence.root,owned.fixture.binding)
    for row in rows:fresh.append(row['event'],**{key:value for key,value in row.items() if key not in ('event','proposal_sha256','previous')})
    with pytest.raises(WorkloadBlocked,match='prepared_scope_unacknowledged_or_changed'):execute(owned)
    assert (owned.scope/'cgroup.kill').read_text()=='0'


@pytest.mark.parametrize('transaction',['commit_intent','request_intent','postflight'])
def test_unresolved_physical_transaction_preserves_database_and_case_evidence(owned,transaction):
    add_compute(owned);add_database(owned)
    quota=owned.output/'fixture-quota.bin';exclusive(quota,b'evidence')
    owned.evidence.append('control_quota_file_created',observed=identity(quota,content=False))
    path=owned.root/'runtime/workload.json';state=private(path)[1]
    if transaction=='commit_intent':state.update(phase='commit_intent',database_commit=dict(transaction='unresolved'))
    elif transaction=='request_intent':state['requests']={'unresolved':dict(phase='intent',sha256='0'*64)}
    else:state['phase']='postflight'
    path.write_bytes(canonical(state))
    with pytest.raises(WorkloadBlocked,match='transaction_unresolved_preserve'):execute(owned)
    assert (owned.scope/'cgroup.kill').read_text()=='1'
    assert quota.read_bytes()==b'evidence' and owned.scope.exists() and owned.leaf.exists()
    assert set(json.loads(owned.store.read_bytes()))=={RETAINED,COMPUTE,DATABASE}
    assert not any('kill' in argv[3:] or 'rm' in argv[3:] or 'stop' in argv for argv in owned.calls)


@pytest.mark.parametrize('container,field,value',[
    (COMPUTE,'NanoCpus',1000000000),(COMPUTE,'LogConfig',{'Type':'json-file'}),
    (COMPUTE,'CapDrop',[]),(COMPUTE,'SecurityOpt',[]),(COMPUTE,'Binds',['/retained:/app']),
    (DATABASE,'NanoCpus',1000000000),(DATABASE,'Tmpfs',{}),(DATABASE,'LogConfig',{'Type':'json-file'}),
])
def test_bound_creator_policy_drift_is_preserved_before_any_docker_mutation(owned,container,field,value):
    add_compute(owned);add_database(owned)
    rows=json.loads(owned.store.read_bytes());rows[container]['HostConfig'][field]=value;owned.store.write_bytes(canonical(rows))
    with pytest.raises(WorkloadBlocked,match='birth_or_policy_changed_preserve'):execute(owned)
    assert json.loads(owned.store.read_bytes())==rows
    assert not any('kill' in argv[3:] or 'rm' in argv[3:] for argv in owned.calls)
