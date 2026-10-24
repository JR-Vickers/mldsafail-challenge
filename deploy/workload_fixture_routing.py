"""Actual routing and PostgreSQL fences, with fixed inert fixture controllers.

Only the inherited-lock fixture adapter calls this module. It supplies neither
an epoch nor arbitrary roles/commands. The temporary SQL service is separately
owned, so verified computational cleanup can precede releasing its transaction
fence without touching a retained database.
"""
import copy
import resource
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from deploy import maintenance_fence,protected_epoch
from deploy.workload_fixture_database import OwnedDatabase
from deploy.workload_installation import Journal,exclusive,private
from deploy.workload_release import canonical,digest
from deploy.workload_routing_fixture import InertController,execute as dispatcher_cases,CASES as DISPATCHER_CASES
from mldsafail.evaluator.envelope import sign_envelope
from mldsafail.evaluator.native_workload import birth,process_birth,require
from mldsafail.evaluator.workload import HostGate
from mldsafail.evaluator.workload_client import WorkloadClient
from mldsafail.evaluator.workload_socket import SupervisorProtocol
from mldsafail.web.models import Base,EvaluationJob,User
from mldsafail.web.services import create_submission

ADMIN_CASES=frozenset((('administrative_routing','host_gate_before_fence'),
    ('administrative_routing','queued_blocks_admin'),('zero_pending_fence','queued_claimed_running')))
CASES=DISPATCHER_CASES|ADMIN_CASES


class OwnedRoutingRuntime(InertController):
    def __init__(self,native,state):
        super().__init__();self.native=native;self.physical_state=copy.deepcopy(state);self.role='participant'
        self.physical_record=native.record(state);self.actual_processes=[]
    def identity(self):return self.native.identity()
    def preflight(self,policy):
        self.calls.append('preflight')
        return 0 if self.ceiling<=0 else self.native.preflight(policy)
    def sample(self,state):return self.native.sample(self.physical_state)
    def child_preexec(self):
        leaf=self.physical_record['leaf']
        require(birth(leaf['path'])==leaf,'fixture_routing_leaf_replaced')
        resource.setrlimit(resource.RLIMIT_AS,(64*1024**2,64*1024**2))
        resource.setrlimit(resource.RLIMIT_NPROC,(32,32))
        (Path(leaf['path'])/'cgroup.procs').write_text(str(__import__('os').getpid()))
    def launch(self,state,specification):
        require(set(specification)=={'role'} and specification['role'] in ('participant','inert'),
            'fixture_routing_role_not_inert')
        self.role=specification['role'];super().launch(state,specification)
        actual=process_birth(self.child.pid);self.actual_processes.append(actual);return actual
    def stopped(self,state):
        return super().stopped(state) and self.native.stopped(self.physical_state)
    def inspect(self,state,observed):
        if self.child is None or self.child.poll() is not None:return False
        return process_birth(self.child.pid)==observed
    def snapshot(self):
        row=super().snapshot();row['native_sample']=self.native.sample(self.physical_state)
        row['owned_processes']=[dict(identity=item,returncode=self.child.poll() if self.child else None) for item in self.actual_processes]
        return row
    def result(self,state):
        if self.role=='participant':return super().result(state)
        return sign_envelope(dict(binding=dict(workload_id=state['workload_id'],role='inert',reference=state['reference']),
            status='administrative_complete',result=dict(fixture_only=True,verified=True)),b'k'*32)


def rows(engine):
    with Session(engine) as session:
        return [dict(id=row.id,status=row.status,attempts=row.attempts) for row in session.scalars(select(EvaluationJob))]


def administrative_case(control,scenario,root,database,runtime_factory,deadline):
    root=Path(root);root.mkdir(mode=0o700);engine=database.engine();Base.metadata.create_all(engine)
    state_values=['queued','claimed','running'] if control=='zero_pending_fence' else [
        'queued' if scenario=='queued_blocks_admin' else None]
    outcomes=[];trace=[];key=root/'key';exclusive(key,b'k'*32)
    evidence_root=root/'evidence';evidence_root.mkdir(mode=0o700)
    evidence=Journal(evidence_root,digest(canonical(dict(control=control,scenario=scenario,database=database.identifier))))
    try:
        for index,status in enumerate(state_values):
            if status is not None:
                with Session(engine) as session:
                    previous=session.scalars(select(EvaluationJob)).all()
                    if previous:
                        require(len(previous)==1,'fixture_routing_pending_inventory_changed')
                        previous[0].status=status;session.commit()
                    else:
                        user=User(display_name='inert-control');session.add(user);session.commit()
                        create_submission(session,user,dict(repository_url='https://github.com/example/solver',
                            commit_sha='a'*40,hypothesis='inert fence fixture',benchmark_version='0.5.0'),'inert',
                            cohort=dict(epoch_id='inert',evaluator_fingerprint='inert',hidden_suite_version='inert',worker_class='inert'))
                        job=session.scalar(select(EvaluationJob));job.status=status;session.commit()
            runtime=runtime_factory();base=root/str(index);base.mkdir(mode=0o700);gate=HostGate(base/'gate',runtime)
            fences=[];before=rows(engine);error=None;binding=None
            exclusive(base/'before.json',canonical(dict(rows=before,status=status)))
            with gate.locked():
                protocol=SupervisorProtocol(gate,{'inert':{'role':'inert'}})
                def transport(path,request):
                    response=protocol.dispatch(request)
                    trace.append(dict(event='supervisor_'+request['method'],monotonic_ns=time.monotonic_ns(),
                        phase=gate.state['phase'] if gate.state else None))
                    evidence.append('routing_observation',observation=trace[-1])
                    return response
                client=WorkloadClient(base/'socket',base/'client',transport=transport)
                packet=dict(operation_id=digest(str(base).encode())[:32],attempt=str(base/'attempt'),roles=['inert'],
                    signing_key=str(key),result_receipt=str(base/'result'))
                reference=dict(operation_id=packet['operation_id'],packet_sha256=digest(canonical(packet)))
                def factory(packet,client):
                    trace.append(dict(event='database_fence',monotonic_ns=time.monotonic_ns(),
                        host_state=copy.deepcopy(gate.state)))
                    evidence.append('routing_observation',observation=trace[-1])
                    require(gate.state['kind']=='administration' and gate.state['phase']=='acquired',
                        'fixture_admin_host_not_owned_before_fence')
                    with database.connect() as connection:identity=maintenance_fence.database_identity(connection)
                    remaining=min(80,int(deadline-time.monotonic()))
                    ceilings=dict(stop=1,create=30,audit=1,inspection=1,cleanup=15,restoration=1,margin=1)
                    maintenance_fence.prepare(base/'fence',database=identity,container=database.identifier,
                        lifetime=remaining,ceilings=ceilings)
                    fence=maintenance_fence.Fence(base/'fence',database.connect,
                        lambda:database.inspect()['Id']);fences.append(fence);return fence
                try:binding=protected_epoch._route_administration(packet,reference,client,factory)
                except RuntimeError as caught:
                    error=str(caught)
                    pending_rows=rows(engine)
                    pending_observed=bool(pending_rows) and all(row['status'] in ('queued','claimed','running') for row in pending_rows)
                    # The server may reject inside its DO block before the
                    # verifier sees held locks. Preserve that distinct raw
                    # failure; accept only its exact custom-exception type plus
                    # an independently observed unchanged pending inventory.
                    holder_error=fences[-1].holder_error if fences else None
                    require(status is not None and pending_observed and
                        ('pending' in error or (error=='maintenance_acquisition_failed' and holder_error=='RaiseException')),
                        'fixture_admin_unexpected_failure')
                finally:
                    try:
                        exclusive(base/'after.json',canonical(dict(rows=rows(engine),state=copy.deepcopy(gate.state),
                            holder_error=fences[-1].holder_error if fences else None)))
                    finally:
                        # Failed evidence capture cannot suppress creator reaping.
                        runtime.terminate(gate.state or {})
                after=rows(engine)
                if status is None:require(binding is not None,'fixture_admin_success_missing')
                else:
                    require(binding is None and not Path(packet['attempt']).exists() and before==after,
                        'fixture_admin_pending_rows_mutated_or_launched')
                require(runtime.stopped(gate.state),'fixture_admin_worker_survives')
                if gate.state is not None and not gate.state['paused']:gate.pause('fixture_admin_finished')
                outcomes.append(dict(status=status,before=before,after=after,error=error,binding=binding,
                    holder_error=fences[-1].holder_error if fences else None,
                    launches=runtime.calls.count('create'),state=copy.deepcopy(gate.state),
                    processes=runtime.actual_processes if hasattr(runtime,'actual_processes') else runtime.births,
                    fence_state=private(base/'fence/state.json')[1] if fences else None))
    finally:engine.dispose()
    admission_trace=[row for row in trace if row['event'] in ('supervisor_acquire','database_fence')]
    host_events=[index for index,row in enumerate(admission_trace) if row['event']=='supervisor_acquire']
    fence_events=[index for index,row in enumerate(admission_trace) if row['event']=='database_fence']
    require(len(host_events)==len(fence_events)==len(outcomes),'fixture_admin_order_trace_incomplete')
    observations=(dict(host_gate_order=1+host_events[0],fence_order=1+fence_events[0]) if scenario=='host_gate_before_fence' else
        dict(queued=sum(row['status']=='queued' for row in outcomes),controller_launches=sum(row['launches'] for row in outcomes))
        if scenario=='queued_blocks_admin' else dict(blocked_states=[row['status'] for row in outcomes if row['error']],
            launches=sum(row['launches'] for row in outcomes)))
    return dict(observations=observations,before=outcomes[0]['before'],after=outcomes[-1]['after'],
        raw=dict(outcomes=outcomes,routing_trace=trace),trace=[dict(event='injection',monotonic_ns=trace[0]['monotonic_ns']),
            dict(event='observation',monotonic_ns=time.monotonic_ns())])


def execute_owned(fixture,resources,native,state,root,control,scenario,token,deadline):
    require((control,scenario) in CASES,'fixture_database_control_case_unsupported')
    database=OwnedDatabase(fixture,resources,native,root,token,deadline);result=None;failure=None
    try:
        database.start()
        factory=lambda:OwnedRoutingRuntime(native,state)
        if (control,scenario) in DISPATCHER_CASES:
            result=dispatcher_cases(control,scenario,Path(root)/'routing',database=database,runtime_factory=factory)
        else:result=administrative_case(control,scenario,Path(root)/'routing',database,factory,deadline)
    except BaseException as error:
        failure=dict(type=type(error).__name__,message=str(error))
        exclusive(Path(root)/'routing-failure.json',canonical(failure));raise
    finally:
        # All SQL state is synthetic and this exact acknowledged container is
        # generation-owned. Removal aborts any failed fixture transactions; it
        # never drops a retained database or mutates a production table.
        try:cleanup=database.cleanup(min(time.monotonic()+45,deadline))
        except BaseException as error:
            exclusive(Path(root)/'database-blocked.json',canonical(dict(failure=failure,
                cleanup_error=dict(type=type(error).__name__,message=str(error)),ownership='blocked_preserve')))
            raise
    result['database_cleanup']=cleanup;result['transactions']='resolved';return result
