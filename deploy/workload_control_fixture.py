"""Executable disposable control regressions; never installed-native evidence.

The runtime is deliberately synthetic. File locks, durable journals, SQLite
transactions, descendant processes and monitor threads are real local effects.
No Docker daemon, host scheduling configuration or cgroup ancestor is mutated.
"""
import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time

from deploy.workload_control_registry import get_runner
from mldsafail.evaluator.workload import HostGate, ResourcePolicy, WorkloadBlocked, WorkloadSession


class FixtureRuntime:
    def __init__(self):
        self.host = dict(boot_id='fixture-boot', daemon_id='fixture-daemon')
        self.ceiling = 2*1024**3
        self.live = False
        self.cleanup = True
        self.ack_lost = False
        self.birth_valid = True
        self.calls = []
        self.sample_data = dict(available=1024**3, memory=0, oom_events=0, swap=0,
            disk_free=6*1024**3, logs=0, generation=0, identity_valid=True)

    def identity(self): return dict(self.host)
    def preflight(self, policy):
        self.calls.append('preflight')
        return self.ceiling
    def sample(self, state): return dict(self.sample_data)
    def launch(self, state, specification):
        self.calls.append('create'); self.live=True
        if self.ack_lost == 'create': raise OSError('fixture_create_ack_lost')
        self.calls.append('start')
        if self.ack_lost == 'start': raise OSError('fixture_start_ack_lost')
        return dict(id=state['workload_id'], birth='fixture-container-birth')
    def inspect(self, state, birth): return self.birth_valid
    def terminate(self, state):
        self.calls.append('terminate')
        if self.cleanup: self.live=False
        return self.cleanup
    def stopped(self, state): return not self.live
    def snapshot(self):
        return dict(identity=self.identity(), ceiling=self.ceiling, live=self.live,
            calls=list(self.calls), sample=dict(self.sample_data), cleanup=self.cleanup,
            birth_valid=self.birth_valid)


def blocked(function, errors):
    try: function()
    except (WorkloadBlocked, OSError) as error:
        errors.append(str(error)); return True
    return False


def execute(control, scenario, root, *, runtime_factory=None):
    """Use an exclusively created directory; return observations, never authority."""
    row=get_runner(control, scenario)
    root=Path(root).absolute()
    if '..' in root.parts or any(path.is_symlink() for path in (root,*root.parents)):
        raise WorkloadBlocked('fixture_symlink_or_traversal_path')
    info=root.parent.stat()
    if info.st_uid!=os.getuid() or info.st_mode&0o077:
        raise WorkloadBlocked('fixture_parent_not_private')
    # Import after module initialization: the routing fixture reuses the runtime
    # contract but drives the real dispatcher/SQL implementation.
    if runtime_factory is None:
        from deploy.workload_routing_fixture import CASES, execute as routing_execute
        if (control,scenario) in CASES:
            result=routing_execute(control,scenario,root)
            result.update(schema='mldsafail.control-fixture-observation.v1',origin='synthetic',
                control=control,scenario=scenario,injection=row['injection'],installed_native_eligible=False,
                errors=[],raw=dict(sql_trace=result['sql_trace'],other_database=result['other_database']),
                fixture_cleanup=dict(descendants_after=result['process_births'],
                    process_returncode=result['process_returncode'],live_runtime_resources_after=False,
                    retained_host_resources_touched=False))
            return result
    root.mkdir(mode=0o700,parents=False,exist_ok=False)
    runtime=FixtureRuntime() if runtime_factory is None else runtime_factory(root)
    errors=[];trace=[];children=[]
    trace.append(dict(event='injection',monotonic_ns=time.monotonic_ns(),kind=row['injection']))
    before=runtime.snapshot();observations={};raw={};state=None;receipt=None
    gate=HostGate(root/'gate',runtime)
    key=(control,scenario)
    try:
        if key == ('persistent_pause','supervisor_sigkill'):
            code='''import sys,time\nfrom mldsafail.evaluator.workload import HostGate\nfrom deploy.workload_control_fixture import FixtureRuntime\nwith HostGate(sys.argv[1],FixtureRuntime()).locked() as gate:\n gate.acquire('administration',{'fixture':'inert-owner'})\n print('ready',flush=True)\n time.sleep(20)\n'''
            child=subprocess.Popen([sys.executable,'-c',code,str(root/'gate')],stdout=subprocess.PIPE,text=True)
            children.append(child)
            if child.stdout.readline().strip()!='ready':raise RuntimeError('fixture_owner_not_ready')
            child.kill();child.wait(timeout=2);child.stdout.close()
            with gate.locked():
                denied=blocked(lambda:gate.acquire('administration',{}),errors)
                gate.pause('fixture_owner_died');gate.reconcile()
                observations=dict(restart_launches=runtime.calls.count('create'),paused=gate.state['paused'],restart_denied=denied)
                state=copy.deepcopy(gate.state)
        else:
            with gate.locked():
                if control == 'shared_host_gate':
                    gate.acquire('evaluation',dict(database='first'))
                    acquired=1;attempts=1
                    for kind in ('evaluation','administration'):
                        attempts+=1
                        def contend():
                            with HostGate(root/'gate',runtime).locked() as contender:
                                contender.acquire(kind,dict(database='second'))
                        if not blocked(contend,errors):acquired+=1
                    observations=dict(callers=attempts,acquired=acquired,overlap=acquired-1)
                    gate.reconcile();gate.pause('fixture_finished')
                elif scenario == 'deferred_admission' or key==('delegation','missing_controller'):
                    runtime.ceiling=0
                    denied=blocked(lambda:gate.acquire('evaluation',{}),errors)
                    observations=dict(attempts_before=0,attempts_after=runtime.calls.count('create'),attempts=runtime.calls.count('create'),launches=runtime.calls.count('start'),denied=denied)
                elif control in ('zero_pending_fence','administrative_routing') and scenario != 'host_gate_before_fence':
                    database=sqlite3.connect(root/'queue.sqlite')
                    try:
                        database.execute('create table jobs(state text)')
                        states=('queued','claimed','running') if control=='zero_pending_fence' else ('queued',)
                        denied=[]
                        for pending in states:
                            database.execute('delete from jobs');database.execute('insert into jobs values (?)',(pending,));database.commit()
                            gate.acquire('administration',dict(fixture='queue'))
                            count=database.execute("select count(*) from jobs where state in ('queued','claimed','running')").fetchone()[0]
                            if count:denied.append(pending)
                            else:gate.launch({})
                            gate.complete()
                        raw['queue_rows']=database.execute('select state from jobs').fetchall()
                        observations=dict(blocked_states=denied,launches=runtime.calls.count('start'),queued=len(raw['queue_rows']),controller_launches=runtime.calls.count('start'))
                    finally:database.close()
                else:
                    gate.acquire('administration',dict(fixture=scenario))
                    if scenario == 'host_gate_before_fence':
                        raw['order']=['host_gate_acquired']
                        database=sqlite3.connect(root/'fence.sqlite')
                        try:
                            database.execute('begin exclusive');raw['order'].append('database_fence_acquired');database.rollback()
                        finally:database.close()
                        observations=dict(host_gate_order=raw['order'].index('host_gate_acquired')+1,fence_order=raw['order'].index('database_fence_acquired')+1)
                    elif control=='durable_launch_intent':
                        runtime.ack_lost='create' if scenario=='lost_create_ack' else 'start'
                        blocked(lambda:gate.launch({}),errors)
                        calls=runtime.calls.count(runtime.ack_lost)
                        blocked(lambda:gate.launch({}),errors)
                        observations={runtime.ack_lost+'_calls':calls,'replay_'+runtime.ack_lost+'_calls':runtime.calls.count(runtime.ack_lost)-calls}
                    elif key==('explicit_resume','failed_preflight') or key==('explicit_resume','fresh_preflight'):
                        gate.launch({});gate.pause('fixture_interruption');gate.reconcile()
                        runtime.ceiling=0 if scenario=='failed_preflight' else before['ceiling']
                        denied=blocked(gate.resume,errors)
                        observations=dict(resources=int(runtime.live),resumed=not denied and gate.state['phase']=='complete')
                    elif control=='delegation':
                        policy=ResourcePolicy()
                        limits={'cpu.max':policy.cpu_max,'pids.max':str(policy.pids_max),'memory.swap.max':str(policy.swap_max)}
                        for name,value in limits.items():(root/name).write_text(value)
                        raw['limit_files']={name:(root/name).read_text() for name in limits}
                        observations=dict(cpu_max=raw['limit_files']['cpu.max'],pids_max=int(raw['limit_files']['pids.max']),swap_max=int(raw['limit_files']['memory.swap.max']))
                    elif control=='scheduling_exclusion':
                        inventory=root/'triggers.json';inventory.write_text(json.dumps([dict(owner='fixture',classified=True,active=False)]))
                        raw['inventory']=json.loads(inventory.read_text())
                        observations=dict(unclassified=sum(not item['classified'] for item in raw['inventory']),unexpected_active=sum(item['active'] for item in raw['inventory']))
                    elif control=='common_cgroup':
                        for _ in range(3):children.append(subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)']))
                        raw['processes']=[dict(pid=child.pid,running=child.poll() is None) for child in children]
                        observations=dict(inspected_processes=sum(item['running'] for item in raw['processes']),placement_verified=False)
                    elif control=='continuous_monitor':
                        gate.launch({});entered=threading.Event();unblock=threading.Event();thread=None
                        session=WorkloadSession(gate).start()
                        started=time.monotonic()
                        try:
                            if scenario=='stale_sample':
                                original=runtime.sample
                                def sample(state):
                                    entered.set()
                                    if not unblock.wait(3):raise OSError('fixture_sampler_timeout')
                                    return original(state)
                                runtime.sample=sample
                            else:
                                original=runtime.launch
                                def launch(state,specification):
                                    entered.set()
                                    if not unblock.wait(3):raise OSError('fixture_creator_timeout')
                                    return original(state,specification)
                                runtime.launch=launch
                                thread=threading.Thread(target=lambda:blocked(lambda:gate.launch({}),errors))
                                thread.start()
                            if not entered.wait(1):raise RuntimeError('fixture_injection_not_entered')
                            if scenario=='stuck_control_io':runtime.sample_data['oom_events']=1
                            if not session.failed.wait(1.5):raise RuntimeError('fixture_monitor_did_not_abort')
                            observations=dict(monitor_continued=session.failed.is_set(),results=0,paused=gate.state['paused'],abort_latency_ms=(time.monotonic()-started)*1000)
                        finally:
                            unblock.set()
                            if thread:thread.join(2)
                            session.finish_monitor()
                    else:
                        gate.launch({})
                        if scenario=='daemon_replacement':runtime.host['daemon_id']='fixture-replacement'
                        elif scenario=='container_restart':runtime.sample_data['identity_valid']=False;runtime.birth_valid=False
                        elif scenario=='parent_oom':runtime.sample_data['oom_events']+=1
                        elif scenario=='ancestor_limit_change':runtime.ceiling//=2
                        elif scenario=='log_exhaustion':runtime.sample_data['logs']=ResourcePolicy().log_max+1
                        elif scenario=='generation_quota_exhaustion':runtime.sample_data['generation']=ResourcePolicy().generation_max+1
                        elif scenario=='surviving_worker':runtime.cleanup=False
                        elif scenario=='controller_disconnect':
                            gate.state['heartbeat_monotonic_deadline']=time.monotonic()-1;gate._write()
                        if scenario=='ancestor_limit_change':blocked(lambda:gate.launch({}),errors)
                        else:blocked(gate.check,errors)
                        if scenario=='daemon_replacement':
                            calls=runtime.calls.count('terminate');blocked(gate.reconcile,errors)
                            observations['replacement_kills']=runtime.calls.count('terminate')-calls
                        else:blocked(gate.reconcile,errors)
                        if scenario=='result_after_cleanup':
                            gate.postflight();gate.commit_intent({'disposition':'fixture_result'})
                            raw['commit_snapshot']=runtime.snapshot();gate.acknowledge_commit({'disposition':'fixture_result'});gate.release()
                            observations.update(resources_at_commit=int(raw['commit_snapshot']['live']),results=int(gate.state['phase']=='complete'))
                        elif control=='native_linux_acceptance':
                            observations.update(emulated=True,fixture_resources_after=int(runtime.live),retained_services_unchanged=None)
                        else:observations['results']=int(gate.state['phase']=='complete')
                        observations.update(paused=gate.state['paused'],oom_delta=runtime.sample_data['oom_events']-before['sample']['oom_events'],ownership_released=gate.state['phase']=='complete',populated=int(runtime.live),containers=int(runtime.live))
                if gate.state is not None and not gate.state['paused']:gate.pause('fixture_finished')
                state=copy.deepcopy(gate.state)
        trace.append(dict(event='observation',monotonic_ns=time.monotonic_ns()))
        receipt=dict(schema='mldsafail.control-fixture-observation.v1',origin='synthetic',control=control,scenario=scenario,
            injection=row['injection'],before=before,after=runtime.snapshot(),state=state,observations=observations,
            raw=raw,errors=errors,trace=trace,installed_native_eligible=False)
        return receipt
    finally:
        for child in children:
            if child.poll() is None:child.kill()
            child.wait(timeout=2)
        # All effects belong to this exclusive fixture; uncertain synthetic
        # ownership remains recorded, while the adapter releases its inert state.
        if hasattr(runtime,'final_cleanup'):runtime.final_cleanup()
        runtime.cleanup=True;runtime.live=False
        if receipt is not None:
            receipt['fixture_cleanup']=dict(descendants_after=[dict(pid=child.pid,returncode=child.returncode) for child in children],
                live_runtime_resources_after=runtime.live,runtime_after=runtime.snapshot(),monotonic_ns=time.monotonic_ns(),
                retained_host_resources_touched=False)
