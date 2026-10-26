"""Fixed, inherited-lock Docker control injections in a disposable VM fixture.

The existing fixture target marker, component review, parent request, source
manifest and lifecycle descriptor are mandatory. No production/native authority
is manufactured here. These records have local_linux origin, not installed-native
acceptance. Every created container has a recorded ID, birth and generation label.
"""
import copy
import errno
import json
import os
import sys
import resource
import subprocess
import threading
import uuid
from pathlib import Path
import time

from deploy.workload_installation import Journal, exclusive, identity, private
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.native_workload import NativeRuntime, LABEL, birth, process_birth, require, values
from mldsafail.evaluator.workload import HostGate, ResourcePolicy, WorkloadBlocked, WorkloadSession

from deploy.workload_control_registry import OWNED_FIXTURE_CASES as CASES


def execution_mode(fact,source,review,expected_sha256,machine_id):
    require(fact.get('schema')=='mldsafail.fixture-execution-mode.v1' and
        fact.get('mode') in ('native','emulated') and fact.get('hostname')==source['host']['hostname'] and
        fact.get('boot_id')==source['host']['boot_id'] and fact.get('machine_id')==machine_id and
        review.get('execution_facts',{}).get('native_execution_fact')==expected_sha256,
        'fixture_control_execution_mode_fact_not_reviewed')
    return fact['mode']


def require_observations(control,scenario,observations):
    from deploy.workload_controls import SCENARIOS
    expected=SCENARIOS[control][scenario]
    require(all(type(observations.get(key)) is type(value) and observations[key]==value for key,value in expected.items()),
        'fixture_control_observed_assertion_failed')
    if control=='continuous_monitor':
        require(all(type(observations.get(key)) in (int,float) and 0<=observations[key]<=maximum
            for key,maximum in (('abort_latency_ms',1100),('control_read_ms',850))),
            'fixture_control_monitor_deadline_not_observed')
    if control=='bounded_output':
        policy=ResourcePolicy()
        require(observations.get('enforcement')=='kernel' and type(observations.get('log_rlimit_bytes')) is int and
            0<observations['log_rlimit_bytes']<=policy.log_max//2 and type(observations.get('max_log_streams')) is int and
            0<observations['max_log_streams']<=8 and observations['max_log_streams']*observations['log_rlimit_bytes']<=policy.log_max and
            type(observations.get('generation_filesystem_bytes')) is int and
            0<observations['generation_filesystem_bytes']<=policy.generation_max,'fixture_control_kernel_limits_not_observed')
    if control=='native_linux_acceptance':
        require(observations.get('platform')=='linux' and bool(observations.get('retained_before')) and
            observations['retained_before']==observations.get('retained_after'),'fixture_control_native_retention_not_observed')


def placement_program(marker,stop):
    return ('import os,pathlib,subprocess,sys,time\n'
        'child=subprocess.Popen([sys.executable,"-I","-B","-c","import time;time.sleep(90)"])\n'
        'try:\n'
        ' fd=os.open('+repr(str(marker))+',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,str(child.pid).encode());os.close(fd)\n'
        ' while not pathlib.Path('+repr(str(stop))+').exists():time.sleep(.01)\n'
        'finally:\n child.kill();child.wait(timeout=.65)\n')


class InertRuntime:
    """Production native sampling/cleanup with a fixed inert Docker creator."""
    def __init__(self,native,root,scenario,deadline,record=None):
        self.native=native;self.root=Path(root);self.scenario=scenario;self.deadline=deadline
        self.generation=private(self.root/'intent.json')[1]['generation']
        require(type(self.generation) is str and len(self.generation)==32 and
            all(c in '0123456789abcdef' for c in self.generation),'fixture_control_generation_invalid')
        self.calls=[];self.created=[];self.deny_preflight=False;self.replace_binding=False
        self.record_event=record or (lambda *args,**kwargs:None);self.trace=[]
        self.children=[];self.extra_cgroups=[];self.sample_entered=threading.Event();self.sample_release=threading.Event()
        self.block_sample=False;self.leave_survivor=False;self.quota_files=[];self.oom_monitors=[];self.log_monitors=[];self.sample_rejections=[]
    def identity(self):
        row=self.native.identity()
        if self.replace_binding:row=dict(row,daemon_id='fixture-injected-replacement')
        return row
    def preflight(self,policy):return 0 if self.deny_preflight else self.native.preflight(policy)
    def prepare(self,state):
        from deploy.workload_fixture_control_cleanup import acquisition_intent,prepared_scope
        acquisition_intent(self.root,state,self.record_event)
        result=self.native.prepare(state)
        require(result is True,'fixture_control_prepare_unverified')
        prepared_scope(self.root,state,self.native,self.record_event)
        return result
    def sample(self,state):
        try:
            if self.block_sample:
                self.sample_entered.set()
                require(self.sample_release.wait(3),'fixture_control_sample_injection_timeout')
                raise WorkloadBlocked('fixture_control_late_sample_rejected')
            sample=self.native.sample(state)
            for expected,baseline in self.oom_monitors:
                require(birth(expected['path'])==expected,'fixture_control_oom_scope_replaced')
                now=values(Path(expected['path'])/'memory.events')
                require(now['oom_kill']>=baseline['oom_kill'],'fixture_control_oom_counter_reset')
                sample['oom_events']+=now['oom_kill']-baseline['oom_kill']
            for expected,limit in self.log_monitors:
                require(identity(expected['path'],content=False)==expected,'fixture_control_log_replaced')
                require(Path(expected['path']).stat().st_size<limit,'native_log_budget_exhausted')
            return sample
        except BaseException as error:
            reason=str(error);self.sample_rejections.append(reason)
            self.record_event('control_sample_rejected',reason=reason,monotonic_ns=time.monotonic_ns())
            raise

    def require_sample_rejection(self,reason):
        require(reason in self.sample_rejections,'fixture_control_intended_rejection_not_observed:'+reason)

    def emergency(self,state):return self.native.emergency(state)
    def stopped(self,state):return self.native.stopped(state)
    def terminate(self,state):
        self.verify_owned(state)
        result=self.native.terminate(state)
        if self.leave_survivor:
            record=self.native.record(state)
            require(values(Path(record['scope']['path'])/'cgroup.events')['populated']>0 and
                any(child.poll() is None for child,_ in self.children),'fixture_control_survivor_not_observed')
            return False
        return result
    def inspect(self,state,observed):
        rows=self.native.containers(state)
        return any(row['Id']==observed['id'] and row['Created']==observed['created_at'] for row in rows)
    def launch(self,state,specification):
        require(specification=={'fixture':'inert'},'fixture_control_fixed_creator_required')
        require(time.monotonic()<self.deadline,'fixture_control_case_expired')
        record=self.native.record(state);output=Path(record['output']);router=output/'router'
        if not router.exists():router.mkdir(mode=0o700)
        name='mlwe-fixture-'+state['workload_id'];path=router/(name+'.json')
        intent=dict(operation_id=state['workload_id'],name=name,state='create_intent')
        exclusive(path,canonical(intent))
        argv=['create','--name',name,'--label',LABEL+'='+state['workload_id'],
            '--label','org.mldsafail.fixture-control='+self.root.name,
            '--label','org.mldsafail.fixture-generation='+self.generation,'--restart=no',
            '--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
            '--cpus=.1','--memory=32m','--memory-swap=32m','--pids-limit=16','--log-driver=none',
            '--cgroup-parent',Path(record['scope']['path']).name,
            '--entrypoint=/usr/local/bin/python',self.native.config['worker']['image'],
            '-c','import time; time.sleep(90)']
        self.calls.append(dict(operation='create',monotonic_ns=time.monotonic_ns()))
        identifier=self.native.docker(argv).decode().strip()
        row=json.loads(self.native.docker(['inspect',identifier]))[0]
        require(row['Id']==identifier and row['Name']=='/'+name and row['Created'] and
            row['Config']['Labels'][LABEL]==state['workload_id'] and
            row['HostConfig']['CgroupParent']==Path(record['scope']['path']).name,
            'fixture_control_create_identity_changed')
        # This fixture-only observation is independent of the runtime router ACK.
        # It constrains cleanup even when that ACK is deliberately withheld.
        created=dict(id=identifier,created_at=row['Created'],name=name,started_at=None,
            operation_id=state['workload_id'],scope=record['scope'])
        created_path=self.root/'created-container.json';exclusive(created_path,canonical(created))
        self.record_event('control_container_created',observed=identity(created_path),binding=copy.deepcopy(created))
        self.created.append(created)
        if self.scenario=='lost_create_ack':
            self.injection('lost_create_ack',container=created)
            raise OSError('fixture_lost_create_ack')
        from mldsafail.evaluator.native_workload import publish
        intent.update(container_id=identifier,created_at=row['Created'],state='start_intent');publish(path,intent)
        self.calls.append(dict(operation='start',monotonic_ns=time.monotonic_ns()))
        self.native.docker(['start',identifier])
        row=json.loads(self.native.docker(['inspect',identifier]))[0]
        require(row['State']['Running'] and row['Created']==created['created_at'],'fixture_control_start_not_observed')
        created['started_at']=row['State']['StartedAt']
        started_path=self.root/'started-container.json';exclusive(started_path,canonical(created))
        self.record_event('control_container_started',observed=identity(started_path),binding=copy.deepcopy(created))
        if self.scenario=='lost_start_ack':
            self.injection('lost_start_ack',container=created)
            raise OSError('fixture_lost_start_ack')
        intent.update(started_at=row['State']['StartedAt'],state='running');publish(path,intent)
        self.native.containers(state)  # Actual /proc placement, not requested parent alone.
        return dict(id=identifier,created_at=row['Created'])

    def owned_cgroup(self,state,name):
        record=self.native.record(state);group=Path(record['scope']['path'])/name
        group.mkdir()
        observed=birth(group);self.extra_cgroups.append(observed)
        self.record_event('control_cgroup_created',observed=observed)
        for control,value in {'memory.max':64*1024**2,'memory.swap.max':0,'pids.max':32,'cpu.max':'10000 100000'}.items():
            require(birth(group)==observed and birth(group.parent)==record['scope'],
                'fixture_control_owned_cgroup_replaced_before_limit')
            (group/control).write_text(str(value))
        return group

    def spawn(self,state,kind,code,*,log=None,pressure=False):
        group=self.owned_cgroup(state,'fixture-'+kind)
        expected_group=self.extra_cgroups[-1];expected_parent=birth(group.parent)
        def enter():
            require(birth(group)==expected_group and birth(group.parent)==expected_parent,
                'fixture_control_owned_cgroup_replaced_before_entry')
            if not pressure:resource.setrlimit(resource.RLIMIT_AS,(64*1024**2,64*1024**2))
            if log is not None:resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
            (group/'cgroup.procs').write_text(str(os.getpid()))
        stream=None
        if log is not None:
            stream=Path(log).open('xb');os.chmod(log,0o600)
        try:
            child=subprocess.Popen([self.native.config['python'],'-I','-B','-c',code],
                preexec_fn=enter,stdin=subprocess.DEVNULL,stdout=stream or subprocess.DEVNULL,stderr=stream or subprocess.DEVNULL)
        finally:
            if stream is not None:stream.close()
        observed=process_birth(child.pid);self.children.append((child,observed))
        self.record_event('control_process_created',identity=observed,cgroup=birth(group))
        return child

    def spawn_controller(self,state):
        record=self.native.record(state);leaf=Path(record['leaf']['path']);marker=self.root/'controller.exit'
        output=Path(record['output']);out=output/'participant.stdout';err=output/'participant.stderr'
        code=('import os,pathlib,time\nwhile not pathlib.Path('+repr(str(marker))+').exists():time.sleep(.01)\nos._exit(23)')
        def enter():
            require(birth(leaf)==record['leaf'],'fixture_control_controller_leaf_replaced')
            resource.setrlimit(resource.RLIMIT_AS,(64*1024**2,64*1024**2))
            resource.setrlimit(resource.RLIMIT_NPROC,(32,32))
            resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
            (leaf/'cgroup.procs').write_text(str(os.getpid()))
        with out.open('xb') as stdout,err.open('xb') as stderr:
            os.chmod(out,0o600);os.chmod(err,0o600)
            child=subprocess.Popen([self.native.config['python'],'-I','-B','-c',code],preexec_fn=enter,
                stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr)
        observed=process_birth(child.pid);self.children.append((child,observed))
        controller=dict(observed,role='participant',output=str(output),started_at=time.monotonic(),log_limit=16*1024**2)
        record['controllers'].append(controller)
        from mldsafail.evaluator.native_workload import publish
        publish(self.native.record_path(state),record)
        require(self.native.inspect(state,controller),'fixture_control_controller_not_observed')
        self.record_event('control_controller_created',identity=observed,record=controller)
        self.injection('controller_disconnect',process=observed,requested_exit_code=23)
        exclusive(marker,b'exit');return child

    def exhaust_generation(self,state):
        record=self.native.record(state);output=Path(record['output']);mount=self.native.output_mount(ResourcePolicy())
        path=output/'fixture-quota.bin'
        self.record_event('control_quota_file_intent',path=str(path),mount=mount)
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        expected=identity(path,content=False);self.quota_files.append(expected)
        self.record_event('control_quota_file_created',observed=expected)
        before=os.statvfs(output);offset=0;kernel_error=None
        self.injection('generation_quota_exhaustion',path=expected,mount=mount,
            before_available_bytes=before.f_bavail*before.f_frsize)
        try:
            while True:
                require(time.monotonic()<self.deadline,'fixture_control_quota_injection_deadline')
                info=os.fstat(descriptor)
                require(info.st_nlink==1 and (info.st_dev,info.st_ino)==(expected['device'],expected['inode']) and
                    identity(path,content=False)==expected,'fixture_control_quota_file_replaced_or_shared')
                current=os.statvfs(output)
                amount=min(1024**2,max(current.f_frsize,current.f_bavail*current.f_frsize))
                require(offset+amount<=mount['bytes']+current.f_frsize,'fixture_control_quota_pressure_cap')
                try:os.posix_fallocate(descriptor,offset,amount)
                except OSError as error:
                    require(error.errno==errno.ENOSPC,'fixture_control_quota_wrong_kernel_error')
                    if amount>current.f_frsize:
                        # Leave no unmeasured slack: fill the remaining blocks
                        # before requiring the monitor's zero-available reading.
                        amount=current.f_frsize
                        require(os.fstat(descriptor).st_nlink==1 and identity(path,content=False)==expected,
                            'fixture_control_quota_file_replaced_or_shared')
                        try:os.posix_fallocate(descriptor,offset,amount)
                        except OSError as small:
                            require(small.errno==errno.ENOSPC,'fixture_control_quota_wrong_kernel_error')
                            kernel_error=small.errno;break
                    else:kernel_error=error.errno;break
                offset+=amount
            after=os.statvfs(output)
            raw=dict(path=str(path),identity=expected,mount=mount,allocated_bytes=path.stat().st_blocks*512,
                before_available_bytes=before.f_bavail*before.f_frsize,after_available_bytes=after.f_bavail*after.f_frsize,
                kernel_errno=kernel_error)
            self.record_event('control_quota_observed',observation=raw,monotonic_ns=time.monotonic_ns())
            return raw
        finally:os.close(descriptor)

    def release_quota(self):
        for expected in self.quota_files:
            path=Path(expected['path'])
            require(identity(path,content=False)==expected and path.stat().st_nlink==1,
                'fixture_control_quota_file_replaced_preserve')
            path.unlink();self.record_event('control_quota_file_removed',observed=expected)
        self.quota_files=[]

    def results(self,state):
        return [path.name for path in Path(self.native.record(state)['output']).glob('*.result.json')]

    def injection(self,kind,**raw):
        row=dict(event='injection',kind=kind,monotonic_ns=time.monotonic_ns(),**raw)
        self.trace.append(row);self.record_event('control_injection',observation=row)

    def verify_owned(self,state):
        ids=self.native.docker(['ps','-aq','--no-trunc','--filter','label='+LABEL+'='+state['workload_id']]).decode().split()
        expected={row['id']:row for row in self.created}
        require(set(ids)<=set(expected),'fixture_control_unknown_container_preserve')
        for identifier in ids:
            rows=json.loads(self.native.docker(['inspect',identifier]));require(len(rows)==1,'fixture_control_inspection_incomplete')
            actual=rows[0];row=expected[identifier]
            require(actual['Id']==row['id'] and actual['Created']==row['created_at'] and actual['Name']=='/'+row['name'] and
                actual['Config']['Labels'].get(LABEL)==state['workload_id'] and
                actual['Config']['Labels'].get('org.mldsafail.fixture-control')==self.root.name and
                actual['Config']['Labels'].get('org.mldsafail.fixture-generation')==self.generation and
                actual['Image'] in (self.native.config['worker']['image'],self.native.config['worker'].get('configuration')) and
                actual['HostConfig']['CgroupParent']==Path(row['scope']['path']).name and
                actual['HostConfig']['ReadonlyRootfs'] is True and actual['HostConfig']['NetworkMode']=='none' and
                actual['HostConfig']['Memory']==actual['HostConfig']['MemorySwap']==32*1024**2 and
                actual['HostConfig']['PidsLimit']==16 and actual['HostConfig']['RestartPolicy']['Name']=='no',
                'fixture_control_container_replaced_preserve')
            restart=self.root/'restart-injection.json'
            permitted=private(restart)[1]['after']['State']['StartedAt'] if restart.exists() else row['started_at']
            require((actual['State']['StartedAt']==permitted if permitted else
                not actual['State']['Running'] and actual['State']['StartedAt'] in ('','0001-01-01T00:00:00Z')),
                'fixture_control_container_start_changed_preserve')

    def cleanup_owned(self,state):
        """No name-based adoption: independently recorded exact birth only."""
        self.verify_owned(state)
        before=[]
        for expected in self.created:
            rows=json.loads(self.native.docker(['inspect',expected['id']]))
            require(len(rows)==1,'fixture_control_cleanup_inspection_incomplete')
            row=rows[0]
            require(row['Id']==expected['id'] and row['Created']==expected['created_at'] and
                row['Name']=='/'+expected['name'] and row['Config']['Labels'].get(LABEL)==expected['operation_id'] and
                row['Config']['Labels'].get('org.mldsafail.fixture-control')==self.root.name,
                'fixture_control_cleanup_birth_changed_preserve')
            # A restart is allowed here only if this injection recorded its exact
            # post-restart birth. Other changes remain ambiguous and preserved.
            restart=self.root/'restart-injection.json'
            permitted=private(restart)[1]['after']['State']['StartedAt'] if restart.exists() else expected['started_at']
            if permitted:
                require(row['State']['StartedAt']==permitted,'fixture_control_cleanup_start_changed')
            else:
                require(not row['State']['Running'] and row['State']['StartedAt'] in ('','0001-01-01T00:00:00Z'),
                    'fixture_control_cleanup_start_changed')
            before.append(row)
            if row['State']['Running']:self.native.docker(['kill',row['Id']])
            self.native.docker(['rm',row['Id']])
            router=Path(self.native.record(state)['output'])/'router'/(expected['name']+'.json')
            _,intent=private(router)
            require(intent['operation_id']==state['workload_id'] and intent['name']==expected['name'] and
                intent.get('container_id',expected['id'])==expected['id'] and
                intent.get('created_at',expected['created_at'])==expected['created_at'],
                'fixture_control_cleanup_router_identity_changed')
            from mldsafail.evaluator.native_workload import publish
            publish(router,dict(intent,state='removed',container_id=expected['id'],created_at=expected['created_at'],
                cleanup_disposition='exact_fixture_observed_birth_removed'))
        remaining=self.native.docker(['ps','-aq','--no-trunc','--filter','label='+LABEL+'='+state['workload_id']]).decode().split()
        require(not remaining,'fixture_control_containers_remaining')
        return dict(before=before,remaining=remaining)


def execute(fixture,resources,control,scenario,token):
    """Called only by work() after validating the inherited parent request."""
    from scripts.workload_fixture_worker import inherited_lock
    from scripts.rehearse_workload_installation_fixture import component_review
    inherited_lock(fixture.root,fixture.lock_fd);fixture.require_target();component_review(fixture)
    native_stage=False
    if fixture.manifest.get('schema')=='mldsafail.workload-native-context.v1':
        from deploy.workload_native_context import NativeContext
        require(type(fixture) is NativeContext,'native_component_context_type_required')
        native_stage=True
    require((control,scenario) in CASES,'fixture_control_native_adapter_not_implemented')
    require(fixture.deadline()>4 if native_stage else fixture.deadline()>=180,'fixture_control_insufficient_attempt_budget')
    require(type(token) is str and len(token)==32 and all(c in '0123456789abcdef' for c in token),
        'fixture_control_token_invalid')
    claims=[row for row in fixture.journal.rows if row['event']=='fixture_control_case_claim' and row.get('token')==token]
    require(len(claims)==1 and claims[0].get('control')==control and claims[0].get('scenario')==scenario and
        claims[0].get('generation')==fixture.manifest['generation'],'fixture_control_worker_claim_required')
    requests=[row for row in fixture.lifecycle_journal.rows if row['event']=='fixture_control_requested' and
        row.get('control')==control and row.get('scenario')==scenario]
    require(len(requests)==1 and type(requests[0].get('started_monotonic')) in (int,float) and
        type(requests[0].get('packet_deadline')) in (int,float),'fixture_control_parent_budget_binding_missing')
    started=requests[0]['started_monotonic']
    packet_deadline=(min(fixture.stage_deadline,time.monotonic()+fixture.deadline()-3) if native_stage else
        min(started+177,requests[0]['packet_deadline']))
    root=fixture.root/'artifacts'/('control-'+token);root.mkdir(mode=0o700)
    exclusive(root/'intent.json',canonical(dict(generation=fixture.manifest['generation'],
        manifest_sha256=fixture.binding,control=control,scenario=scenario,token=token,
        envelope=dict(startup=30,case=90,cleanup=45,postflight=15),outer_supervision_reserve_seconds=3)))
    evidence_root=root/'evidence';evidence_root.mkdir(mode=0o700)
    evidence=Journal(evidence_root,fixture.binding)
    phase_deadline=[min(started+30,packet_deadline)];phase=['startup'];original_run=resources.run
    evidence_lock=threading.RLock();command_lock=threading.Lock()
    original_append=evidence.append
    def append(event,**fields):
        with evidence_lock:original_append(event,**fields)
    evidence.append=append
    def bounded_resources(argv,*,seconds=35,inner_seconds=None):
        command_deadline=min(phase_deadline[0],time.monotonic()+4.65)
        remaining=command_deadline-time.monotonic()
        require(remaining>4,'fixture_control_'+phase[0]+'_expired')
        command_id=uuid.uuid4().hex
        evidence.append('control_command_intent',command=command_id,phase=phase[0],argv=argv,
            inner_seconds=.65,monotonic_ns=time.monotonic_ns())
        acquired=command_lock.acquire(timeout=max(0,remaining))
        try:
            require(acquired,'fixture_control_command_lock_deadline')
            remaining=command_deadline-time.monotonic()
            require(remaining>4,'fixture_control_command_deadline')
            raw=original_run(argv,seconds=min(4.65,remaining),inner_seconds=.65)
        except BaseException as error:
            evidence.append('control_command_failed',command=command_id,phase=phase[0],type=type(error).__name__,message=str(error),
                monotonic_ns=time.monotonic_ns());raise
        finally:
            if acquired:command_lock.release()
        evidence.append('control_command_observed',command=command_id,phase=phase[0],sha256=digest(raw),bytes=len(raw),
            monotonic_ns=time.monotonic_ns())
        return raw
    resources.run=bounded_resources
    from deploy.workload_installed import observation_runner
    try:
        with observation_runner(bounded_resources):
            return _run(fixture,resources,control,scenario,root,started,packet_deadline,
                phase_deadline,phase,evidence)
    except BaseException as error:
        blocked=dict(phase=phase[0],type=type(error).__name__,message=str(error),
            disposition='preserve_ambiguous_resources_and_partial_evidence',monotonic_ns=time.monotonic_ns())
        evidence.append('control_blocked',**blocked)
        exclusive(root/'blocked.json',canonical(dict(blocked,generation=fixture.manifest['generation'],
            control=control,scenario=scenario,evidence_head=evidence.head,passed=False)))
        raise
    finally:resources.run=original_run


def _run(fixture,resources,control,scenario,root,started,packet_deadline,phase_deadline,phase,evidence):
    proposal_raw,proposal=fixture.proposal();source=proposal['identities']
    baseline=resources.postflight(proposal)
    evidence.append('control_baseline',observed=baseline,monotonic_ns=time.monotonic_ns())
    from mldsafail.evaluator.workload_client import WorkloadClient
    status=WorkloadClient(source['resources']['socket']['path'],root/'inspection-client').status()
    evidence.append('control_installed_supervisor',observed=status,monotonic_ns=time.monotonic_ns())
    require(status and status['paused'] is True and status['phase'] in ('cleaned','complete'),
        'fixture_control_installed_supervisor_not_paused')
    require(time.monotonic()<started+30,'fixture_control_startup_expired')
    phase[0]='case';phase_deadline[0]=min(packet_deadline,started+120,time.monotonic()+90)
    case_deadline=phase_deadline[0]
    # This is fixture-only construction, not a replacement for any installed
    # configuration or its native acceptance binding.
    exclusive(root/'baseline.json',canonical(baseline))
    from deploy.workload_fixture_control_cleanup import prepare_context
    configuration=prepare_context(fixture,proposal,control,scenario,root.name[-32:],baseline)
    runtime_root=Path(configuration['root'])
    native_calls=[];response_thread=[];response_entered=threading.Event();response_release=threading.Event();response_durations=[];response_intervals=[]
    def bounded(argv):
        require(time.monotonic()<packet_deadline,'fixture_control_packet_expired')
        command_started=time.monotonic()
        native_calls.append(dict(argv=argv,monotonic_ns=time.monotonic_ns(),thread=threading.current_thread().name))
        raw=resources.run(argv,seconds=min(4.65,packet_deadline-time.monotonic()),inner_seconds=.65)
        if response_thread and threading.current_thread() is response_thread[0]:
            held_started=time.monotonic_ns();response_entered.set()
            response_release.wait(max(0,command_started+.65-time.monotonic()))
            response_intervals.append((held_started,time.monotonic_ns()))
            response_durations.append((time.monotonic()-command_started)*1000)
            evidence.append('control_response_timeout',interval=response_intervals[-1],duration_ms=response_durations[-1])
            raise WorkloadBlocked('fixture_control_bounded_response_timeout')
        return raw
    native=NativeRuntime(configuration,run=bounded)
    runtime=InertRuntime(native,root,scenario,case_deadline,record=evidence.append);gate=HostGate(runtime_root,runtime)
    trace=runtime.trace
    errors=[];before=None;after=None;cleanup=None;observations={};failure=None;state=None
    def reject(function):
        try:function()
        except (WorkloadBlocked,OSError) as error:errors.append(str(error));return True
        return False
    try:
        with gate.locked():
            gate.acquire('administration',dict(fixture=scenario,generation=fixture.manifest['generation']))
            before=dict(state=copy.deepcopy(gate.state),native=native.record(gate.state))
            from deploy.workload_fixture_routing import CASES as ROUTING_CASES, execute_owned
            if (control,scenario) in ROUTING_CASES:
                routed=execute_owned(fixture,resources,native,gate.state,root,control,scenario,root.name[-32:],case_deadline)
                observations=routed['observations'];runtime.trace.extend(routed['trace'])
                evidence.append('control_routing_observation',observed=routed)
            elif control=='persistent_pause':
                from mldsafail.evaluator.native_workload import private_json
                original_record=private_json(Path(source['resources']['socket']['path']).parent/'socket.json')
                original_process=original_record['process']
                require(process_birth(original_process['pid'])==original_process,'fixture_control_supervisor_replaced')
                main=int(resources.run(['/usr/bin/systemctl','--user','show','mldsafail-workload-supervisor.service',
                    '--property=MainPID','--value']).strip())
                require(main==original_process['pid'],'fixture_control_supervisor_unit_changed')
                installed_root=Path(source['installation']['gate_root'])
                original_launches=[(path.name,private_json(path).get('controllers',[])) for path in installed_root.glob('*.native.json')]
                fixture.journal.append('fixture_installed_inspection_invalidated',generation=fixture.manifest['generation'],
                    process=original_process,token=root.name[-32:],monotonic_ns=time.monotonic_ns())
                runtime.injection('supervisor_sigkill',process=original_process)
                resources.run(['/usr/bin/systemctl','--user','kill','--kill-who=main','--signal=SIGKILL',
                    'mldsafail-workload-supervisor.service'])
                while True:
                    require(time.monotonic()<case_deadline,'fixture_control_supervisor_restart_expired')
                    try:
                        replacement=private_json(Path(source['resources']['socket']['path']).parent/'socket.json')
                        if replacement['process']!=original_process and process_birth(replacement['process']['pid'])==replacement['process']:
                            restarted=WorkloadClient(source['resources']['socket']['path'],root/'restart-client').status()
                            if restarted and restarted['paused']:break
                    except (FileNotFoundError,OSError,WorkloadBlocked):pass
                    time.sleep(.05)
                current_launches=[(path.name,private_json(path).get('controllers',[])) for path in installed_root.glob('*.native.json')]
                new_controllers=[item for item in current_launches if item not in original_launches]
                observations=dict(restart_launches=sum(len(item[1]) for item in new_controllers),paused=restarted['paused'])
                evidence.append('control_supervisor_replacement',before=original_record,after=replacement,state=restarted)
            elif control=='delegation':
                if scenario=='missing_controller':
                    group=runtime.owned_cgroup(gate.state,'mldsafail-heavy.slice')
                    probe_configuration=copy.deepcopy(configuration);probe_root=root/'delegation-probe';probe_root.mkdir(mode=0o700)
                    probe_configuration.update(root=str(probe_root),heavy=str(group),heavy_birth=birth(group))
                    chain=[];cursor=group
                    while True:
                        chain.append(birth(cursor))
                        if str(cursor)=='/sys/fs/cgroup':break
                        cursor=cursor.parent
                    probe_configuration['ancestors']=chain
                    probe=NativeRuntime(probe_configuration,run=bounded)
                    actual=dict(controllers=(group/'cgroup.controllers').read_text(),subtree_control=(group/'cgroup.subtree_control').read_text())
                    runtime.injection('missing_controller',actual=actual)
                    require(reject(lambda:probe.preflight(gate.policy)) and errors[-1] in
                        ('cgroup_delegation_missing','cgroup_controllers_not_enabled'),'fixture_missing_controller_not_rejected')
                    observations=dict(attempts=len(runtime.created),launches=sum(row['operation']=='start' for row in runtime.calls))
                else:
                    runtime.injection('inspected_limits',scope=birth(native.heavy))
                    observations=dict(cpu_max=(native.heavy/'cpu.max').read_text().strip(),
                        pids_max=int((native.heavy/'pids.max').read_text()),swap_max=int((native.heavy/'memory.swap.max').read_text()))
            elif control=='scheduling_exclusion':
                from deploy.workload_installed import scheduling
                runtime.injection('retained_trigger_inventory')
                actual=scheduling(proposal)
                from deploy.workload_registry import observe as owner_inventory
                from deploy.workload_preparation import manager_prefix
                from deploy.workload_schedule_v3 import unit_name
                owners=owner_inventory(source,resources.run,installed_units=True)
                expected={manager:set(names) for manager,names in source['inventory']['manager_units'].items()}
                expected['user:'+str(source['host']['uid'])].add('mldsafail-workload-supervisor.service')
                unknown={manager:sorted(set(names)-expected.get(manager,set())) for manager,names in owners.items()}
                active={}
                for identifier in source['scheduling']['computational_units']:
                    owner=source['scheduling']['owners'][identifier]
                    active[identifier]=resources.run([*manager_prefix(owner,source['host']['uid']),
                        'show',unit_name(identifier,owner),'--property=ActiveState','--value']).decode().strip()
                evidence.append('control_scheduling_observation',observed=actual,owners=owners,unknown=unknown,active=active)
                observations=dict(unclassified=sum(len(names) for names in unknown.values()),
                    unexpected_active=sum(value not in ('inactive','failed') for value in active.values()))
            elif scenario in ('lost_create_ack','lost_start_ack'):
                require(reject(lambda:gate.launch({'fixture':'inert'})),'fixture_ack_not_lost')
                call='create' if scenario=='lost_create_ack' else 'start'
                calls=sum(row['operation']==call for row in runtime.calls)
                reject(lambda:gate.launch({'fixture':'inert'}))
                observations={call+'_calls':calls,'replay_'+call+'_calls':sum(row['operation']==call for row in runtime.calls)-calls}
            else:
                gate.launch({'fixture':'inert'})
                if scenario=='parent_oom':
                    trigger=root/'oom.start'
                    code='import pathlib,time\nwhile not pathlib.Path('+repr(str(trigger))+').exists():time.sleep(.01)\nx=bytearray(64*1024*1024);time.sleep(3)'
                    child=runtime.spawn(gate.state,'oom',code,pressure=True)
                    pressure_group=runtime.extra_cgroups[-1];baseline_events=values(Path(pressure_group['path'])/'memory.events')
                    runtime.oom_monitors.append((pressure_group,baseline_events))
                    runtime.injection('parent_oom',scope=pressure_group,before=baseline_events,process=runtime.children[-1][1])
                    exclusive(trigger,b'allocate')
                    child.wait(timeout=min(5,max(.001,case_deadline-time.monotonic())))
                    after_events=values(Path(pressure_group['path'])/'memory.events')
                    evidence.append('control_oom_observed',after=after_events,returncode=child.returncode)
                    require(after_events['oom_kill']>baseline_events['oom_kill'] and reject(gate.check) and
                        gate.state['reason']=='operation_oom','fixture_control_kernel_oom_not_observed')
                    observations=dict(oom_delta=after_events['oom_kill']-baseline_events['oom_kill'],
                        results=len(runtime.results(gate.state)),paused=gate.state['paused'])
                elif scenario=='log_exhaustion':
                    output=Path(before['native']['output']);log=output/'inert.stdout';marker=root/'log-injection.json'
                    code=('import errno,json,os,resource\nlimit=resource.getrlimit(resource.RLIMIT_FSIZE)\n'
                          'os.lseek(1,limit[0]-1,os.SEEK_SET);os.write(1,b"x")\n'
                          'try:os.write(1,b"x")\n'
                          'except OSError as error:\n fd=os.open('+repr(str(marker))+',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);'
                          'os.write(fd,json.dumps(dict(limits=limit,kernel_errno=error.errno,process=os.getpid())).encode());os.close(fd)\n')
                    runtime.injection('log_exhaustion',log_path=str(log))
                    child=runtime.spawn(gate.state,'log-writer',code,log=log);child.wait(timeout=min(3,max(.001,case_deadline-time.monotonic())))
                    raw=private(marker)[1];expected_log=identity(log,content=False)
                    require(raw['kernel_errno']==errno.EFBIG and raw['limits'][0]==raw['limits'][1] and
                        log.stat().st_size==raw['limits'][0],'fixture_control_kernel_log_limit_not_observed')
                    runtime.log_monitors.append((expected_log,raw['limits'][0]));evidence.append('control_log_exhaustion_observed',raw=raw,log=expected_log)
                    require(reject(gate.check),'fixture_control_log_exhaustion_not_rejected')
                    runtime.require_sample_rejection('native_log_budget_exhausted')
                    observations=dict(results=len(runtime.results(gate.state)),paused=gate.state['paused'],enforcement='kernel',
                        log_rlimit_bytes=raw['limits'][0],max_log_streams=2,
                        generation_filesystem_bytes=native.output_mount(gate.policy)['bytes'])
                elif scenario=='controller_disconnect':
                    child=runtime.spawn_controller(gate.state);child.wait(timeout=min(3,max(.001,case_deadline-time.monotonic())))
                    evidence.append('control_controller_exit_observed',process=runtime.children[-1][1],returncode=child.returncode)
                    require(child.returncode==23 and reject(gate.check),'fixture_control_disconnect_not_observed')
                    runtime.require_sample_rejection('native_controller_disconnected')
                    observations=dict(results=len(runtime.results(gate.state)),paused=gate.state['paused'])
                elif control=='native_linux_acceptance':
                    name='native_execution_fact'
                    require(name in fixture.manifest['inputs'],'fixture_control_execution_mode_fact_missing')
                    fact=private(fixture.root/'inputs'/name)[1]
                    from scripts.rehearse_workload_installation_fixture import component_review
                    review=component_review(fixture)
                    mode=execution_mode(fact,source,review,fixture.manifest['inputs'][name]['sha256'],
                        Path('/etc/machine-id').read_text().strip())
                    runtime.injection('inert_lifecycle_and_cleanup',execution_fact=fact)
                    observations=dict(emulated=mode=='emulated',platform=sys.platform)
                elif scenario=='generation_quota_exhaustion':
                    output=Path(before['native']['output']);log=output/'quota-writer.stdout'
                    child=runtime.spawn(gate.state,'quota-writer','import time;time.sleep(90)',log=log)
                    limits=Path('/proc/'+str(child.pid)+'/limits').read_text().splitlines()
                    file_limit=next(row.split()[3:5] for row in limits if row.startswith('Max file size'))
                    require(file_limit==[str(16*1024**2)]*2,'fixture_control_writer_limit_not_observed')
                    raw=runtime.exhaust_generation(gate.state)
                    require(raw['kernel_errno']==errno.ENOSPC and reject(gate.check),'fixture_control_quota_not_rejected')
                    runtime.require_sample_rejection('generation_budget_exhausted')
                    observations=dict(results=len(runtime.results(gate.state)),paused=gate.state['paused'],enforcement='kernel',
                        log_rlimit_bytes=int(file_limit[0]),max_log_streams=2,generation_filesystem_bytes=raw['mount']['bytes'])
                    runtime.release_quota()
                    require(process_birth(child.pid)==runtime.children[-1][1],'fixture_control_writer_replaced')
                    child.terminate();child.wait(timeout=.65)
                elif scenario=='surviving_worker':
                    child=runtime.spawn(gate.state,'survivor','import time;time.sleep(90)')
                    runtime.leave_survivor=True;runtime.injection('surviving_worker',identity=process_birth(child.pid))
                    require(reject(gate.reconcile),'fixture_survivor_ownership_not_blocked')
                    observations=dict(ownership_released=gate.state['phase']=='complete',results=len(runtime.results(gate.state)))
                elif scenario=='ancestor_limit_change':
                    record=native.record(gate.state);leaf=Path(record['leaf']['path']);target=leaf/'memory.max'
                    original=target.read_text().strip();target.write_text(str(256*1024**2));changed=target.read_text().strip()
                    runtime.injection('ancestor_limit_change',leaf=birth(leaf),before=original,after=changed)
                    require(reject(gate.check),'fixture_limit_drift_not_rejected')
                    runtime.require_sample_rejection('native_controller_limits_changed')
                    observations=dict(results=len(runtime.results(gate.state)),paused=gate.state['paused'])
                elif control=='common_cgroup':
                    marker=root/'descendant.pid'
                    stop=root/'placement.stop'
                    code=placement_program(marker,stop)
                    child=runtime.spawn(gate.state,'placement',code)
                    while not marker.exists():
                        require(child.poll() is None and time.monotonic()<case_deadline,'fixture_control_descendant_not_observed');time.sleep(.01)
                    grandchild=int(private(marker,parse=False)[0]);rows=native.containers(gate.state)
                    inventory=[process_birth(child.pid),process_birth(grandchild),process_birth(rows[0]['State']['Pid'])]
                    from deploy.workload_bound_control_observers import process_placement
                    raw=process_placement(Path(native.record(gate.state)['scope']['path']),inventory)
                    runtime.injection('controller_worker_descendants',processes=raw)
                    observations=dict(outside_heavy=raw['outside_heavy'],inspected_processes=raw['inspected_processes'])
                    exclusive(stop,b'stop');child.wait(timeout=.65)
                elif control=='continuous_monitor':
                    session=WorkloadSession(gate).start();reader=None
                    injection_start=time.monotonic()
                    try:
                        if scenario=='stale_sample':
                            injection_start=time.monotonic();runtime.block_sample=True;runtime.injection('stale_sample')
                            require(runtime.sample_entered.wait(1),'fixture_sample_not_blocked')
                        else:
                            reader=threading.Thread(target=lambda:reject(lambda:native.docker(['inspect',runtime.created[0]['id']])),
                                name='fixture-stuck-control-reader')
                            response_thread.append(reader);reader.start()
                            require(response_entered.wait(1),'fixture_control_reader_not_blocked')
                            leaf=Path(before['native']['leaf']['path']);require(birth(leaf)==before['native']['leaf'],'fixture_control_leaf_replaced')
                            injection_start=time.monotonic();original=(leaf/'memory.max').read_text();(leaf/'memory.max').write_text(str(256*1024**2))
                            runtime.injection('stuck_control_io',leaf=birth(leaf),before=original,after=(leaf/'memory.max').read_text(),
                                model='bounded_native_command_response_hold')
                        require(session.failed.wait(1.5),'fixture_independent_monitor_did_not_abort')
                        observations=dict(results=len(list(Path(before['native']['output']).glob('*.result.json'))),paused=gate.state['paused'],
                            monitor_continued=session.failed.is_set(),
                            abort_latency_ms=(time.monotonic()-injection_start)*1000)
                    finally:
                        response_release.set();runtime.sample_release.set();runtime.block_sample=False
                        if reader:reader.join(1)
                        session.finish_monitor()
                    intents={}
                    durations=[]
                    for row in evidence.rows:
                        if row['event']=='control_command_intent':intents[row['command']]=row['monotonic_ns']
                        elif row['event']=='control_command_observed' and row['command'] in intents:
                            durations.append((row['monotonic_ns']-intents[row['command']])/1e6)
                    if scenario=='stale_sample':require(session.reason=='monitor_stale','fixture_stale_sampler_wrong_abort_reason')
                    if scenario=='stuck_control_io':
                        runtime.require_sample_rejection('native_controller_limits_changed')
                        observations['monitor_continued']=any(row['thread']=='heavy-workload-monitor' and
                            start<=row['monotonic_ns']<=end for start,end in response_intervals for row in native_calls)
                    observations['control_read_ms']=max(response_durations if response_durations else durations) if response_durations or durations else None
                elif scenario=='container_restart':
                    expected=runtime.created[0];old=json.loads(native.docker(['inspect',expected['id']]))[0]
                    runtime.injection('container_restart',before=old)
                    native.docker(['restart','--time=0',expected['id']])
                    new=json.loads(native.docker(['inspect',expected['id']]))[0]
                    require(old['Created']==new['Created'] and old['State']['StartedAt']!=new['State']['StartedAt'],
                        'fixture_restart_not_observed')
                    exclusive(root/'restart-injection.json',canonical(dict(before=old,after=new)))
                    evidence.append('control_restart_observed',before=old,after=new)
                    require(reject(gate.check),'fixture_restart_not_rejected')
                    runtime.require_sample_rejection('native_container_restarted')
                    observations=dict(results=len(runtime.results(gate.state)),paused=gate.state['paused'])
                elif scenario=='daemon_replacement':
                    runtime.replace_binding=True;runtime.injection('daemon_replacement',original_identity=gate.state['identity'])
                    require(reject(gate.reconcile),'fixture_replacement_not_rejected')
                    observations=dict(replacement_kills=sum(row['argv'][:len(configuration['docker'])]==configuration['docker'] and
                        row['argv'][len(configuration['docker']):len(configuration['docker'])+1]==['kill'] for row in native_calls),paused=gate.state['paused'])
                    runtime.replace_binding=False
            require(time.monotonic()<case_deadline,'fixture_control_case_expired')
            if not runtime.trace:runtime.injection(scenario,native=native.record(gate.state))
            if scenario!='surviving_worker':reject(gate.reconcile)
            if scenario in ('failed_preflight','fresh_preflight'):
                gate.pause('fixture_explicit_resume_test');runtime.deny_preflight=scenario=='failed_preflight'
                resumed=not reject(gate.resume)
                observations=dict(resources=int(not native.stopped(gate.state)),resumed=resumed)
                runtime.deny_preflight=False
            elif scenario=='empty_scope_and_absent_containers':
                record=native.record(gate.state)
                observations=dict(populated=values(Path(record['scope']['path'])/'cgroup.events')['populated'],
                    containers=len(native.containers(gate.state)))
            if not gate.state['paused']:gate.pause('fixture_control_finished')
            state=copy.deepcopy(gate.state);after=dict(state=state,containers=native.containers(state)) if scenario!='container_restart' else dict(state=state)
    except BaseException as error:
        failure=dict(type=type(error).__name__,message=str(error))
    finally:
        phase[0]='cleanup';phase_deadline[0]=min(packet_deadline,started+165,time.monotonic()+45)
        cleanup_deadline=phase_deadline[0]
        evidence.append('control_cleanup_started',monotonic_ns=time.monotonic_ns())
        runtime.release_quota()
        # Cleanup owns only these fixture-created births. Uncertain ownership
        # raises and leaves both resources and the immutable intent for recovery.
        if gate.state is not None:
            require(time.monotonic()<cleanup_deadline,'fixture_control_cleanup_expired')
            record=native.record(gate.state)
            # Native cleanup may already have removed acknowledged containers.
            existing=set(native.docker(['ps','-aq','--no-trunc','--filter','label='+LABEL+'='+gate.state['workload_id']]).decode().split())
            runtime.created=[row for row in runtime.created if row['id'] in existing]
            cleanup=runtime.cleanup_owned(gate.state)
            scope=Path(record['scope']['path']);require(birth(scope)==record['scope'],'fixture_control_scope_replaced_before_kill')
            before_kill=values(scope/'cgroup.events')
            (scope/'cgroup.kill').write_text('1')
            while values(scope/'cgroup.events')['populated']:
                require(time.monotonic()<min(cleanup_deadline,packet_deadline),'fixture_control_scope_populated')
                time.sleep(.01)
            empty=values(scope/'cgroup.events')
            for child,expected in runtime.children:
                if child.poll() is None:require(process_birth(child.pid)==expected,'fixture_control_cleanup_process_replaced')
                child.wait(timeout=min(.65,max(.001,cleanup_deadline-time.monotonic())))
            for expected in reversed(runtime.extra_cgroups):
                group=Path(expected['path']);require(birth(scope)==record['scope'] and birth(group)==expected and values(group/'cgroup.events')['populated']==0,
                    'fixture_control_extra_scope_replaced_or_populated');group.rmdir()
            router_rows=[private(path)[1] for path in (Path(record['output'])/'router').glob('*.json')]
            require(not any(row.get('state')=='create_intent' and not row.get('container_id') for row in router_rows),
                'fixture_control_unresolved_router_transaction')
            runtime.leave_survivor=False;runtime.replace_binding=False;runtime.deny_preflight=False
            with gate.locked():
                if gate.state['phase'] not in ('cleaned','complete'):gate.reconcile()
                require(native.stopped(gate.state) and gate.state['phase'] in ('cleaned','complete') and gate.state['paused'],
                    'fixture_control_ownership_transaction_unresolved')
                state=copy.deepcopy(gate.state)
            cleanup['transactions']='resolved';cleanup['gate_state']=state;cleanup['router_states']=router_rows
            leaf=Path(record['leaf']['path']);require(birth(scope)==record['scope'] and birth(leaf)==record['leaf'],'fixture_control_leaf_replaced');leaf.rmdir()
            native.run(['/usr/bin/systemctl','--user','stop',Path(record['scope']['path']).name])
            remaining_scope=identity(scope)
            require(remaining_scope['state']=='absent' or birth(scope)==record['scope'] and
                values(scope/'cgroup.events')['populated']==0,'fixture_control_scope_not_removed_or_empty')
            cleanup['scope_termination']=dict(before=record['scope'],before_kill=before_kill,empty=empty,
                after=remaining_scope,leaf_removed=not leaf.exists())
        require(time.monotonic()<cleanup_deadline,'fixture_control_cleanup_expired')
    phase[0]='postflight';phase_deadline[0]=min(packet_deadline,time.monotonic()+15)
    postflight=resources.postflight(proposal)
    require(postflight==baseline,'fixture_control_retained_postflight_changed')
    require(time.monotonic()<phase_deadline[0],'fixture_control_postflight_expired')
    if control=='native_linux_acceptance':
        termination=cleanup['scope_termination']
        observations.update(fixture_resources_after=len(cleanup['remaining'])+int(termination['after']['state']!='absent')+
            int(not termination['leaf_removed']),retained_services_unchanged=postflight==baseline,
            retained_before=baseline['retained_services'],retained_after=postflight['retained_services'])
    trace.append(dict(event='observation',monotonic_ns=time.monotonic_ns()))
    identities=dict(schema='mldsafail.fixture-control-identities.v1',proposal_sha256=digest(proposal_raw),
        release_sha256=proposal['manifest_sha256'],source_sha256=digest(canonical(fixture.manifest['source_hashes'])),
        native_configuration=identity(root/'native-configuration.json'),cleanup_context=identity(root/'cleanup-context.json'),
        workload_id=state['workload_id'] if state else None,runtime=state['identity'] if state else None,
        scope=before['native']['scope'] if before else None)
    receipt=dict(schema='mldsafail.fixture-native-control.v1',origin='local_linux',fixture_only=True,
        installed_native_eligible=False,generation=fixture.manifest['generation'],control=control,scenario=scenario,token=root.name[-32:],
        before=before,after=after,observations=observations,identities=identities,trace=trace,errors=errors,failure=failure,
        calls=runtime.calls,native_calls=native_calls,cleanup=cleanup,
        fixture_scope_termination=(dict(state='removed' if cleanup['scope_termination']['after']['state']=='absent' else 'empty',
            identity=cleanup['scope_termination']['before'],events=cleanup['scope_termination']['empty']) if cleanup else None),
        retained_before=baseline,retained_after=postflight,paused=state is not None and state['paused'],transactions='resolved')
    exclusive(root/'receipt.json',canonical(receipt))
    require(failure is None,'fixture_control_case_failed_retained_evidence')
    require_observations(control,scenario,observations)
    return receipt
