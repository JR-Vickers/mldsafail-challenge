"""Fixed, inherited-lock Docker control injections in a disposable VM fixture.

The existing fixture target marker, component review, parent request, source
manifest and lifecycle descriptor are mandatory. No production/native authority
is manufactured here. These records have local_linux origin, not installed-native
acceptance. Every created container has a recorded ID, birth and generation label.
"""
import copy
import json
from pathlib import Path
import time

from deploy.workload_installation import exclusive, identity, private
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.native_workload import NativeRuntime, LABEL, birth, require, values
from mldsafail.evaluator.workload import HostGate, WorkloadBlocked

CASES=frozenset((('durable_launch_intent','lost_create_ack'),
    ('durable_launch_intent','lost_start_ack'),('inspected_births','container_restart'),
    ('inspected_births','daemon_replacement'),
    ('verified_cleanup','empty_scope_and_absent_containers'),
    ('explicit_resume','failed_preflight'),('explicit_resume','fresh_preflight')))


class InertRuntime:
    """Production native sampling/cleanup with a fixed inert Docker creator."""
    def __init__(self,native,root,scenario,deadline):
        self.native=native;self.root=Path(root);self.scenario=scenario;self.deadline=deadline
        self.calls=[];self.created=[];self.deny_preflight=False;self.replace_binding=False
    def identity(self):
        row=self.native.identity()
        if self.replace_binding:row=dict(row,daemon_id='fixture-injected-replacement')
        return row
    def preflight(self,policy):return 0 if self.deny_preflight else self.native.preflight(policy)
    def prepare(self,state):return self.native.prepare(state)
    def sample(self,state):return self.native.sample(state)
    def emergency(self,state):return self.native.emergency(state)
    def stopped(self,state):return self.native.stopped(state)
    def terminate(self,state):return self.native.terminate(state)
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
        exclusive(self.root/'created-container.json',canonical(created));self.created.append(created)
        if self.scenario=='lost_create_ack':raise OSError('fixture_lost_create_ack')
        from mldsafail.evaluator.native_workload import publish
        intent.update(container_id=identifier,created_at=row['Created'],state='start_intent');publish(path,intent)
        self.calls.append(dict(operation='start',monotonic_ns=time.monotonic_ns()))
        self.native.docker(['start',identifier])
        row=json.loads(self.native.docker(['inspect',identifier]))[0]
        require(row['State']['Running'] and row['Created']==created['created_at'],'fixture_control_start_not_observed')
        created['started_at']=row['State']['StartedAt']
        exclusive(self.root/'started-container.json',canonical(created))
        if self.scenario=='lost_start_ack':raise OSError('fixture_lost_start_ack')
        intent.update(started_at=row['State']['StartedAt'],state='running');publish(path,intent)
        self.native.containers(state)  # Actual /proc placement, not requested parent alone.
        return dict(id=identifier,created_at=row['Created'])

    def cleanup_owned(self,state):
        """No name-based adoption: independently recorded exact birth only."""
        before=[];after=[]
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
            if row['State']['Running']:
                require(permitted and row['State']['StartedAt']==permitted,'fixture_control_cleanup_start_changed')
            before.append(row)
            if row['State']['Running']:self.native.docker(['kill',row['Id']])
            self.native.docker(['rm',row['Id']])
        remaining=self.native.docker(['ps','-aq','--no-trunc','--filter','label='+LABEL+'='+state['workload_id']]).decode().split()
        require(not remaining,'fixture_control_containers_remaining')
        return dict(before=before,remaining=remaining)


def execute(fixture,resources,control,scenario,token):
    """Called only by work() after validating the inherited parent request."""
    from scripts.workload_fixture_worker import inherited_lock
    from scripts.rehearse_workload_installation_fixture import component_review
    inherited_lock(fixture.root,fixture.lock_fd);fixture.require_target();component_review(fixture)
    require((control,scenario) in CASES,'fixture_control_native_adapter_not_implemented')
    require(fixture.deadline()>=180,'fixture_control_insufficient_attempt_budget')
    require(type(token) is str and len(token)==32 and all(c in '0123456789abcdef' for c in token),
        'fixture_control_token_invalid')
    started=time.monotonic();case_deadline=started+120;cleanup_deadline=started+165;packet_deadline=started+180
    root=fixture.root/'artifacts'/('control-'+token);root.mkdir(mode=0o700)
    exclusive(root/'intent.json',canonical(dict(generation=fixture.manifest['generation'],
        manifest_sha256=fixture.binding,control=control,scenario=scenario,token=token,
        envelope=dict(startup=30,case=90,cleanup=45,postflight=15))))
    _,proposal=fixture.proposal();source=proposal['identities']
    baseline=resources.postflight(proposal)
    from mldsafail.evaluator.workload_client import WorkloadClient
    status=WorkloadClient(source['resources']['socket']['path'],root/'inspection-client').status()
    require(status and status['paused'] is True and status['phase'] in ('cleaned','complete'),
        'fixture_control_installed_supervisor_not_paused')
    require(time.monotonic()<started+30,'fixture_control_startup_expired')
    # This is fixture-only construction, not a replacement for any installed
    # configuration or its native acceptance binding.
    from deploy.workload_configuration import templates
    configuration=copy.deepcopy(templates(source)['native'])
    runtime_root=root/'runtime';runtime_root.mkdir(mode=0o700);configuration['root']=str(runtime_root)
    configuration['roles']={'participant':{'timeout_seconds':90}}
    native_calls=[]
    def bounded(argv):
        require(time.monotonic()<packet_deadline,'fixture_control_packet_expired')
        native_calls.append(dict(argv=argv,monotonic_ns=time.monotonic_ns()))
        return resources.run(argv,seconds=min(.65,packet_deadline-time.monotonic()))
    native=NativeRuntime(configuration,run=bounded)
    runtime=InertRuntime(native,root,scenario,case_deadline);gate=HostGate(runtime_root,runtime)
    trace=[dict(event='injection',kind=scenario,monotonic_ns=time.monotonic_ns())]
    errors=[];before=None;after=None;cleanup=None;observations={};failure=None;state=None
    def reject(function):
        try:function()
        except (WorkloadBlocked,OSError) as error:errors.append(str(error));return True
        return False
    try:
        with gate.locked():
            gate.acquire('administration',dict(fixture=scenario,generation=fixture.manifest['generation']))
            before=dict(state=copy.deepcopy(gate.state),native=native.record(gate.state))
            if scenario in ('lost_create_ack','lost_start_ack'):
                require(reject(lambda:gate.launch({'fixture':'inert'})),'fixture_ack_not_lost')
                call='create' if scenario=='lost_create_ack' else 'start'
                calls=sum(row['operation']==call for row in runtime.calls)
                reject(lambda:gate.launch({'fixture':'inert'}))
                observations={call+'_calls':calls,'replay_'+call+'_calls':sum(row['operation']==call for row in runtime.calls)-calls}
            else:
                gate.launch({'fixture':'inert'})
                if scenario=='container_restart':
                    expected=runtime.created[0];old=json.loads(native.docker(['inspect',expected['id']]))[0]
                    native.docker(['restart','--time=0',expected['id']])
                    new=json.loads(native.docker(['inspect',expected['id']]))[0]
                    require(old['Created']==new['Created'] and old['State']['StartedAt']!=new['State']['StartedAt'],
                        'fixture_restart_not_observed')
                    exclusive(root/'restart-injection.json',canonical(dict(before=old,after=new)))
                    require(reject(gate.check),'fixture_restart_not_rejected')
                    observations=dict(results=0,paused=gate.state['paused'])
                elif scenario=='daemon_replacement':
                    runtime.replace_binding=True;require(reject(gate.reconcile),'fixture_replacement_not_rejected')
                    observations=dict(replacement_kills=sum(row['argv'][:3]==configuration['docker'] and row['argv'][3:4]==['kill'] for row in native_calls),paused=gate.state['paused'])
                    runtime.replace_binding=False
            require(time.monotonic()<case_deadline,'fixture_control_case_expired')
            reject(gate.reconcile)
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
        # Cleanup owns only these fixture-created births. Uncertain ownership
        # raises and leaves both resources and the immutable intent for recovery.
        if gate.state is not None:
            require(time.monotonic()<cleanup_deadline,'fixture_control_cleanup_expired')
            record=native.record(gate.state)
            # Native cleanup may already have removed acknowledged containers.
            existing=set(native.docker(['ps','-aq','--no-trunc','--filter','label='+LABEL+'='+gate.state['workload_id']]).decode().split())
            runtime.created=[row for row in runtime.created if row['id'] in existing]
            cleanup=runtime.cleanup_owned(gate.state)
            Path(record['scope']['path'],'cgroup.kill').write_text('1')
            require(values(Path(record['scope']['path'])/'cgroup.events')['populated']==0,'fixture_control_scope_populated')
            leaf=Path(record['leaf']['path']);require(birth(leaf)==record['leaf'],'fixture_control_leaf_replaced');leaf.rmdir()
            native.run(['/usr/bin/systemctl','--user','stop',Path(record['scope']['path']).name])
            require(not Path(record['scope']['path']).exists() or
                values(Path(record['scope']['path'])/'cgroup.events')['populated']==0,'fixture_control_scope_not_removed_or_empty')
        require(time.monotonic()<cleanup_deadline,'fixture_control_cleanup_expired')
    postflight=resources.postflight(proposal)
    require(postflight==baseline,'fixture_control_retained_postflight_changed')
    require(time.monotonic()<packet_deadline,'fixture_control_postflight_expired')
    trace.append(dict(event='observation',monotonic_ns=time.monotonic_ns()))
    receipt=dict(schema='mldsafail.fixture-native-control.v1',origin='local_linux',fixture_only=True,
        installed_native_eligible=False,generation=fixture.manifest['generation'],control=control,scenario=scenario,
        before=before,after=after,observations=observations,trace=trace,errors=errors,failure=failure,
        calls=runtime.calls,native_calls=native_calls,cleanup=cleanup,retained_before=baseline,retained_after=postflight,paused=True)
    exclusive(root/'receipt.json',canonical(receipt))
    require(failure is None,'fixture_control_case_failed_retained_evidence')
    from deploy.workload_controls import SCENARIOS
    expected=SCENARIOS[control][scenario]
    require(all(type(observations.get(key)) is type(value) and observations[key]==value for key,value in expected.items()),
        'fixture_control_observed_assertion_failed')
    return receipt
