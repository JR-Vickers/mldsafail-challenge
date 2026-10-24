"""Source regressions for fixed native Docker hooks; no native pass claims."""
import copy
import json
from pathlib import Path
import time

import pytest

from deploy.workload_fixture_controls import InertRuntime
from deploy.workload_release import canonical
from mldsafail.evaluator.native_workload import LABEL,birth
from mldsafail.evaluator.workload import WorkloadBlocked


class Native:
    def __init__(self,root):
        self.root=root;self.output=root/'output';self.output.mkdir()
        self.scope=root/'scope';self.scope.mkdir()
        self.config={'worker':{'image':'sha256:'+'a'*64},'python':__import__('sys').executable}
        self.row=None;self.commands=[]
    def record(self,state):return dict(output=str(self.output),scope=birth(self.scope))
    def containers(self,state):
        if self.row is None:return []
        path=self.output/'router'/(self.row['Name'].lstrip('/')+'.json')
        intent=json.loads(path.read_bytes())
        if 'started_at' in intent and self.row['State']['StartedAt']!=intent['started_at']:
            raise WorkloadBlocked('native_container_restarted')
        return [copy.deepcopy(self.row)]
    def docker(self,argv):
        self.commands.append(argv)
        if argv[0]=='create':
            name=argv[argv.index('--name')+1];operation=name.removeprefix('mlwe-fixture-')
            label=argv[argv.index('--label',argv.index('--label')+1)+1].split('=',1)[1]
            self.row=dict(Id='b'*64,Image=self.config['worker']['image'],Name='/'+name,Created='fixture-created',
                Config=dict(Labels={LABEL:operation,'org.mldsafail.fixture-control':label,'org.mldsafail.fixture-generation':'d'*32}),
                HostConfig=dict(CgroupParent=self.scope.name,ReadonlyRootfs=True,NetworkMode='none',Memory=32*1024**2,
                    MemorySwap=32*1024**2,PidsLimit=16,RestartPolicy={'Name':'no'}),State=dict(Running=False,StartedAt=''))
            return self.row['Id'].encode()
        if argv[0]=='inspect':return canonical([self.row])
        if argv[0]=='start':self.row['State']=dict(Running=True,StartedAt='first-start');return b''
        if argv[0]=='kill':self.row['State']['Running']=False;return b''
        if argv[0]=='rm':self.row=None;return b''
        if argv[0]=='ps':return (self.row['Id'] if self.row else '').encode()
        raise AssertionError(argv)


def runtime(tmp_path,scenario):
    root=tmp_path/'control';root.mkdir(mode=0o700)
    from deploy.workload_installation import exclusive
    exclusive(root/'intent.json',canonical(dict(generation='d'*32)))
    native=Native(root)
    return InertRuntime(native,root,scenario,time.monotonic()+10),dict(workload_id='c'*32)


@pytest.mark.parametrize('scenario,expected_state,starts',[
    ('lost_create_ack','create_intent',0),('lost_start_ack','start_intent',1)])
def test_real_creator_call_boundary_withholds_only_acknowledgement(tmp_path,scenario,expected_state,starts):
    adapter,state=runtime(tmp_path,scenario)
    with pytest.raises(OSError,match='fixture_lost_'):adapter.launch(state,{'fixture':'inert'})
    row=adapter.native.row
    intent=json.loads(next((adapter.native.output/'router').glob('*.json')).read_bytes())
    assert intent['state']==expected_state
    assert len(adapter.created)==1 and adapter.created[0]['id']==row['Id']
    assert sum(argv[0]=='create' for argv in adapter.native.commands)==1
    assert sum(argv[0]=='start' for argv in adapter.native.commands)==starts
    assert row['State']['Running']==bool(starts)
    cleanup=adapter.cleanup_owned(state)
    assert cleanup['remaining']==[] and adapter.native.row is None


def test_fixed_creator_cannot_accept_arbitrary_specification(tmp_path):
    adapter,state=runtime(tmp_path,'lost_create_ack')
    with pytest.raises(WorkloadBlocked,match='fixed_creator_required'):adapter.launch(state,{'command':['rm','-rf','/']})
    assert adapter.native.commands==[]


@pytest.mark.parametrize('field',['Id','Created','Name','StartedAt','generation_label'])
def test_cleanup_preserves_substituted_container_identity(tmp_path,field):
    adapter,state=runtime(tmp_path,'normal');adapter.launch(state,{'fixture':'inert'})
    if field=='StartedAt':adapter.native.row['State'][field]='replacement'
    elif field=='generation_label':adapter.native.row['Config']['Labels']['org.mldsafail.fixture-control']='other'
    else:adapter.native.row[field]='replacement'
    commands=len(adapter.native.commands)
    with pytest.raises(WorkloadBlocked,match='changed|preserve'):adapter.cleanup_owned(state)
    assert not any(argv[0] in ('kill','rm') for argv in adapter.native.commands[commands:])
    assert adapter.native.row is not None


def test_restart_cleanup_requires_exact_recorded_injected_new_birth(tmp_path):
    adapter,state=runtime(tmp_path,'normal');adapter.launch(state,{'fixture':'inert'})
    before=copy.deepcopy(adapter.native.row);adapter.native.row['State']['StartedAt']='fixture-restart'
    with pytest.raises(WorkloadBlocked,match='restarted'):adapter.native.containers(state)
    with pytest.raises(WorkloadBlocked,match='start_changed'):adapter.cleanup_owned(state)
    from deploy.workload_installation import exclusive
    exclusive(adapter.root/'restart-injection.json',canonical(dict(before=before,after=adapter.native.row)))
    assert adapter.cleanup_owned(state)['remaining']==[]


def test_fixture_control_requires_inherited_lifecycle_lock_before_effect(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from deploy.workload_fixture_controls import execute
    fixture=SimpleNamespace(root=tmp_path,lock_fd=None)
    with pytest.raises(WorkloadBlocked,match='inherited_lock_required'):
        execute(fixture,None,'durable_launch_intent','lost_create_ack','a'*32)
    assert not list(tmp_path.iterdir())


def context(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from deploy import workload_fixture_controls as controls
    import scripts.workload_fixture_worker as worker
    import scripts.rehearse_workload_installation_fixture as rehearsal
    (tmp_path/'artifacts').mkdir(mode=0o700)
    token='a'*32;generation='b'*32
    fixture=SimpleNamespace(root=tmp_path,lock_fd=3,require_target=lambda:None,
        deadline=lambda:1800,binding='c'*64,manifest={'generation':generation},
        lifecycle_journal=SimpleNamespace(rows=[dict(event='fixture_control_requested',control='durable_launch_intent',
            scenario='lost_create_ack',started_monotonic=time.monotonic(),packet_deadline=time.monotonic()+180)]),
        journal=SimpleNamespace(rows=[dict(event='fixture_control_case_claim',token=token,generation=generation,
            control='durable_launch_intent',scenario='lost_create_ack')]))
    monkeypatch.setattr(worker,'inherited_lock',lambda *args:None)
    monkeypatch.setattr(rehearsal,'component_review',lambda *args:None)
    calls=[]
    def run(argv,*,seconds=35,inner_seconds=None):calls.append((argv,seconds,inner_seconds));return b'raw'
    resources=SimpleNamespace(run=run)
    return controls,fixture,resources,calls,token


def test_early_context_failure_retains_blocking_receipt_and_raw_command_trace(tmp_path,monkeypatch):
    controls,fixture,resources,calls,token=context(tmp_path,monkeypatch)
    original=resources.run
    def fail(*args):
        assert resources.run(['fixed-read'])==b'raw'
        raise RuntimeError('startup failure before any injection')
    monkeypatch.setattr(controls,'_run',fail)
    with pytest.raises(RuntimeError,match='startup failure'):
        controls.execute(fixture,resources,'durable_launch_intent','lost_create_ack',token)
    root=tmp_path/'artifacts'/('control-'+token)
    blocked=json.loads((root/'blocked.json').read_bytes())
    assert blocked['passed'] is False and blocked['phase']=='startup'
    assert resources.run is original
    assert len(calls)==1 and calls[0][0]==['fixed-read'] and 4<calls[0][1]<=4.65 and calls[0][2]==.65
    events=[json.loads(line)['event'] for line in (root/'evidence/installation.jsonl').read_text().splitlines()]
    assert events==['control_command_intent','control_command_observed','control_blocked']


def test_expired_startup_cannot_enter_a_late_command(tmp_path,monkeypatch):
    controls,fixture,resources,calls,token=context(tmp_path,monkeypatch)
    clock=[0.0];monkeypatch.setattr(controls.time,'monotonic',lambda:clock[0])
    fixture.lifecycle_journal.rows[0].update(started_monotonic=0,packet_deadline=180)
    def late(*args):clock[0]=31;resources.run(['late-read'])
    monkeypatch.setattr(controls,'_run',late)
    with pytest.raises(WorkloadBlocked,match='startup_expired'):
        controls.execute(fixture,resources,'durable_launch_intent','lost_create_ack',token)
    assert calls==[]
    assert (tmp_path/'artifacts'/('control-'+token)/'blocked.json').exists()


def test_unclaimed_case_cannot_create_control_namespace(tmp_path,monkeypatch):
    controls,fixture,resources,calls,token=context(tmp_path,monkeypatch)
    fixture.journal.rows=[]
    with pytest.raises(WorkloadBlocked,match='worker_claim_required'):
        controls.execute(fixture,resources,'durable_launch_intent','lost_create_ack',token)
    assert not list((tmp_path/'artifacts').iterdir())


@pytest.mark.parametrize('field',['Id','Created','Name','StartedAt','generation_label'])
def test_substitution_is_blocked_before_production_termination(tmp_path,field):
    adapter,state=runtime(tmp_path,'lost_create_ack')
    with pytest.raises(OSError):adapter.launch(state,{'fixture':'inert'})
    calls=[];adapter.native.terminate=lambda state:calls.append('unsafe termination')
    if field=='StartedAt':adapter.native.row['State'][field]='replacement'
    elif field=='generation_label':adapter.native.row['Config']['Labels']['org.mldsafail.fixture-control']='other'
    else:adapter.native.row[field]='replacement'
    with pytest.raises(WorkloadBlocked,match='preserve'):adapter.terminate(state)
    assert calls==[] and adapter.native.row is not None


@pytest.mark.parametrize('field',['mode','hostname','boot_id','machine_id','review'])
def test_execution_mode_cannot_be_inferred_or_relabelled(field):
    from deploy.workload_fixture_controls import execution_mode
    fact=dict(schema='mldsafail.fixture-execution-mode.v1',mode='emulated',hostname='fixture',boot_id='boot',machine_id='machine')
    source={'host':{'hostname':'fixture','boot_id':'boot'}}
    review={'execution_facts':{'native_execution_fact':'a'*64}}
    if field=='review':review={}
    else:fact[field]='unknown-or-substituted'
    with pytest.raises(WorkloadBlocked,match='fact_not_reviewed'):
        execution_mode(fact,source,review,'a'*64,'machine')


def test_reviewed_emulation_fact_stays_emulated():
    from deploy.workload_fixture_controls import execution_mode
    fact=dict(schema='mldsafail.fixture-execution-mode.v1',mode='emulated',hostname='fixture',boot_id='boot',machine_id='machine')
    assert execution_mode(fact,{'host':{'hostname':'fixture','boot_id':'boot'}},
        {'execution_facts':{'native_execution_fact':'a'*64}},'a'*64,'machine')=='emulated'


@pytest.mark.parametrize('intended',['native_log_budget_exhausted','generation_budget_exhausted',
    'native_container_restarted','native_controller_disconnected','native_controller_limits_changed'])
def test_unrelated_transport_failure_cannot_satisfy_injection_causality(tmp_path,intended):
    adapter,state=runtime(tmp_path,'normal')
    def sample(state):raise WorkloadBlocked('native_io_deadline')
    adapter.native.sample=sample
    with pytest.raises(WorkloadBlocked,match='native_io_deadline'):adapter.sample(state)
    with pytest.raises(WorkloadBlocked,match='intended_rejection_not_observed'):adapter.require_sample_rejection(intended)
    assert adapter.sample_rejections==['native_io_deadline']


def test_oom_monitor_uses_counter_delta_and_exact_child_identity(tmp_path):
    adapter,state=runtime(tmp_path,'normal')
    pressure=tmp_path/'pressure';pressure.mkdir();events=pressure/'memory.events';events.write_text('oom_kill 1\n')
    adapter.native.sample=lambda state:{'oom_events':0}
    observed=birth(pressure);adapter.oom_monitors=[(observed,{'oom_kill':0})]
    assert adapter.sample(state)['oom_events']==1
    pressure.rename(tmp_path/'preserved-pressure');pressure.mkdir();events.write_text('oom_kill 1\n')
    with pytest.raises(WorkloadBlocked,match='oom_scope_replaced'):adapter.sample(state)


def test_all_scenarios_have_fixed_owned_contexts_and_distinct_origins():
    from deploy.workload_control_registry import registry,OWNED_FIXTURE_CASES
    from deploy.workload_controls import SCENARIOS
    assert OWNED_FIXTURE_CASES=={(control,scenario) for control,cases in SCENARIOS.items() for scenario in cases}
    for row in registry():
        assert row['owned_fixture_runner']=='deploy.workload_fixture_controls:execute'
        assert row['owned_fixture_context']['origin']=='local_linux'
        assert row['owned_fixture_context']['installed_native_eligible'] is False
        assert row['owned_fixture_context']['injection']


def test_exact_router_transactions_are_resolved_after_lost_create_ack(tmp_path):
    adapter,state=runtime(tmp_path,'lost_create_ack')
    with pytest.raises(OSError):adapter.launch(state,{'fixture':'inert'})
    adapter.cleanup_owned(state)
    row=json.loads(next((adapter.native.output/'router').glob('*.json')).read_bytes())
    assert row['state']=='removed' and row['container_id']=='b'*64 and row['created_at']=='fixture-created'


def test_owned_cgroup_replacement_blocks_limits_before_any_write(tmp_path,monkeypatch):
    from deploy import workload_fixture_controls as controls
    adapter,state=runtime(tmp_path,'normal');original=birth(adapter.native.scope)
    real=controls.birth
    monkeypatch.setattr(controls,'birth',lambda path:dict(original,inode=original['inode']+1)
        if Path(path)==adapter.native.scope else real(path))
    with pytest.raises(WorkloadBlocked,match='replaced_before_limit'):adapter.owned_cgroup(state,'owned')
    assert list((adapter.native.scope/'owned').iterdir())==[]


def test_replaced_process_scope_cannot_receive_child_pid(tmp_path,monkeypatch):
    from deploy import workload_fixture_controls as controls
    adapter,state=runtime(tmp_path,'normal')
    def replaced(*args,**kwargs):
        group=adapter.native.scope/'fixture-test';group.rename(adapter.native.scope/'preserved')
        group.mkdir();kwargs['preexec_fn']()
        raise AssertionError('replaced scope was accepted')
    monkeypatch.setattr(controls.subprocess,'Popen',replaced)
    with pytest.raises(WorkloadBlocked,match='replaced_before_entry'):
        adapter.spawn(state,'test','raise RuntimeError("must not run")')
    assert not (adapter.native.scope/'fixture-test/cgroup.procs').exists()
    assert (adapter.native.scope/'preserved/memory.max').read_text()==str(64*1024**2)


@pytest.mark.parametrize('field,value',[('abort_latency_ms',1101),('control_read_ms',851),
    ('abort_latency_ms',True),('control_read_ms',float('nan')),('control_read_ms',None)])
def test_native_monitor_hook_requires_measured_frozen_deadlines(field,value):
    from deploy.workload_fixture_controls import require_observations
    observations=dict(monitor_continued=True,results=0,abort_latency_ms=1000,control_read_ms=650)
    observations[field]=value
    with pytest.raises(WorkloadBlocked,match='monitor_deadline_not_observed'):
        require_observations('continuous_monitor','stuck_control_io',observations)


@pytest.mark.parametrize('field,value',[('enforcement','periodic'),('log_rlimit_bytes',0),
    ('max_log_streams',9),('generation_filesystem_bytes',1024**3+1)])
def test_native_output_hook_cannot_accept_unmeasured_or_broadened_kernel_limits(field,value):
    from deploy.workload_fixture_controls import require_observations
    observations=dict(results=0,paused=True,enforcement='kernel',log_rlimit_bytes=16*1024**2,
        max_log_streams=2,generation_filesystem_bytes=64*1024**2)
    observations[field]=value
    with pytest.raises(WorkloadBlocked,match='kernel_limits_not_observed'):
        require_observations('bounded_output','generation_quota_exhaustion',observations)


@pytest.mark.skipif(__import__('sys').platform!='linux' or not __import__('os').environ.get('MLDSAFAIL_CONTROL_QUOTA_TEST_ROOT'),
    reason='explicit empty disposable <=8MiB Linux tmpfs required')
def test_generation_injector_observes_real_kernel_enospc_and_preserves_other_owned_file(tmp_path):
    import errno
    import os
    import uuid
    mount=Path(os.environ['MLDSAFAIL_CONTROL_QUOTA_TEST_ROOT'])
    assert not mount.is_symlink() and mount.stat().st_uid==os.getuid() and mount.stat().st_mode&0o077==0
    assert not list(mount.iterdir())
    mounts=Path('/proc/self/mountinfo').read_text().splitlines()
    assert any(row.split()[4]==str(mount) and row.split(' - ',1)[1].split()[0]=='tmpfs' for row in mounts)
    filesystem=os.statvfs(mount);size=filesystem.f_blocks*filesystem.f_frsize
    assert 0<size<=8*1024**2
    adapter,state=runtime(tmp_path,'generation_quota_exhaustion')
    adapter.native.output.rmdir();output=mount/uuid.uuid4().hex;output.mkdir(mode=0o700);adapter.native.output=output
    sentinel=output/'preserved';sentinel.write_bytes(b'retained owned test evidence');before=__import__('hashlib').sha256(sentinel.read_bytes()).hexdigest()
    adapter.native.output_mount=lambda policy:dict(bytes=size,filesystem='tmpfs',path=str(mount))
    try:
        raw=adapter.exhaust_generation(state)
        assert raw['kernel_errno']==errno.ENOSPC and raw['allocated_bytes']<=size
        assert raw['after_available_bytes']==0
        adapter.release_quota()
        assert __import__('hashlib').sha256(sentinel.read_bytes()).hexdigest()==before
    finally:
        if adapter.quota_files:adapter.release_quota()
        sentinel.unlink();output.rmdir()


@pytest.mark.parametrize('change',['hardlink','replacement'])
def test_quota_allocation_stops_before_mutating_shared_or_replaced_file(tmp_path,monkeypatch,change):
    import os
    adapter,state=runtime(tmp_path,'generation_quota_exhaustion')
    adapter.native.output_mount=lambda policy:dict(bytes=8*1024**2,path=str(adapter.native.output))
    path=adapter.native.output/'fixture-quota.bin';preserved=tmp_path/'preserved';calls=[]
    def allocate(descriptor,offset,amount):
        calls.append((offset,amount));os.ftruncate(descriptor,amount)
        if change=='hardlink':os.link(path,preserved)
        else:path.rename(preserved);path.write_bytes(b'unknown replacement')
    monkeypatch.setattr(os,'posix_fallocate',allocate,raising=False)
    with pytest.raises(WorkloadBlocked,match='quota_file_replaced_or_shared'):adapter.exhaust_generation(state)
    assert len(calls)==1 and preserved.stat().st_size==1024**2
    if change=='replacement':assert path.read_bytes()==b'unknown replacement'
    with pytest.raises(WorkloadBlocked,match='quota_file_replaced_preserve'):adapter.release_quota()
