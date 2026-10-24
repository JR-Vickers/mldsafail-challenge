"""Exercise the production dispatcher with disposable SQL and inert processes.

No source checkout, solver, evaluator or epoch is opened. Signed results describe
synthetic data, so these receipts remain synthetic even on a Linux host.
"""
from pathlib import Path
import os
import stat
import subprocess
import sys
import time
from types import SimpleNamespace

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from deploy.workload_control_fixture import FixtureRuntime
from mldsafail.evaluator.dispatcher import Dispatcher
from mldsafail.evaluator.envelope import sign_envelope
from mldsafail.evaluator.workload import HostGate
from mldsafail.evaluator.workload_client import WorkloadClient
from mldsafail.evaluator.workload_socket import SupervisorProtocol
from mldsafail.web.models import Base, EvaluationAttempt, EvaluationJob, ExperimentResult, User
from mldsafail.web.services import create_submission

CASES = frozenset((('coordinator_routing','deferred_admission'),
                   ('coordinator_routing','result_after_cleanup'),
                   ('shared_host_gate','cross_database_and_admin')))


class InertController(FixtureRuntime):
    def __init__(self):
        super().__init__();self.child=None;self.births=[]
    def launch(self,state,specification):
        self.child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)'],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            start_new_session=True)
        self.births.append(dict(pid=self.child.pid,started_monotonic_ns=time.monotonic_ns()))
        return super().launch(state,specification)
    def terminate(self,state):
        if self.child is not None and self.child.poll() is None:
            self.child.kill();self.child.wait(timeout=2)
        return super().terminate(state)
    def stopped(self,state):
        return (self.child is None or self.child.poll() is not None) and super().stopped(state)
    def result(self,state):
        identity={**state['reference']['identity'],'source_digest':'a'*64}
        payload=dict(**identity,verified=True,score=.91,diagnostics={'eligible':True},failure_class=None)
        return sign_envelope(dict(binding=dict(workload_id=state['workload_id'],role='participant',
            reference=state['reference']),status='evaluated',source_digest='a'*64,
            envelope=sign_envelope(payload,b'k'*32)),b'k'*32)


def execute(control,scenario,root):
    if (control,scenario) not in CASES:raise ValueError('routing_fixture_case_unsupported')
    root=Path(root).absolute()
    if any(path.is_symlink() for path in (root,*root.parents)):
        raise ValueError('routing_fixture_symlink_path')
    parent=root.parent.stat()
    if parent.st_uid!=os.getuid() or stat.S_IMODE(parent.st_mode)&0o077:
        raise ValueError('routing_fixture_private_parent_required')
    root.mkdir(mode=0o700,exist_ok=False)
    runtime=InertController();engines=[];dispatchers=[];sql_trace=[]
    cohort=dict(epoch_id='inert-fixture',evaluator_fingerprint='inert-fixture',
                hidden_suite_version='inert-fixture',worker_class='inert-fixture')
    key=root/'key';key.write_bytes(b'k'*32);key.chmod(0o600)
    def snapshot(engine):
        with Session(engine) as db:
            return dict(jobs=[dict(id=r.id,status=r.status,attempts=r.attempts) for r in db.scalars(select(EvaluationJob))],
                attempts=db.scalar(select(func.count()).select_from(EvaluationAttempt)),
                results=db.scalar(select(func.count()).select_from(ExperimentResult)))
    gate=HostGate(root/'gate',runtime)
    try:
        with gate.locked():
            protocol=SupervisorProtocol(gate,{'participant':{'role':'participant'}})
            def build(index):
                engine=create_engine('sqlite:///'+str(root/(str(index)+'.sqlite')));engines.append(engine)
                Base.metadata.create_all(engine)
                with Session(engine) as db:
                    user=User(display_name='inert-fixture');db.add(user);db.commit()
                    create_submission(db,user,dict(repository_url='https://github.com/example/solver',commit_sha='a'*40,
                        hypothesis='inert routing control',benchmark_version='0.5.0'),'fixture',cohort=cohort)
                config=SimpleNamespace(database_url=engine.url.render_as_string(hide_password=False),
                    supervisor_socket=root/'socket',work_root=root/('dispatcher-'+str(index)),signing_key=key,
                    benchmark_version='0.5.0',**cohort)
                client=WorkloadClient(root/'socket',root/('client-'+str(index)),
                    transport=lambda path,request:protocol.dispatch(request))
                dispatcher=Dispatcher(config,client=client);dispatchers.append(dispatcher)
                @event.listens_for(dispatcher.engine,'before_cursor_execute')
                def observe(connection,cursor,statement,parameters,context,many):
                    if statement.lstrip().upper().startswith('INSERT INTO EXPERIMENT_RESULTS'):
                        sql_trace.append(dict(event='result_insert',monotonic_ns=time.monotonic_ns(),
                            resources=int(not runtime.stopped(gate.state)),phase=gate.state['phase']))
                return dispatcher,engine
            first,engine=build(0);before=snapshot(engine)
            injection=dict(event='injection',monotonic_ns=time.monotonic_ns())
            if scenario=='deferred_admission':
                runtime.ceiling=0;ran=first.run_once();after=snapshot(engine)
                observations=dict(attempts_before=before['attempts'],attempts_after=after['attempts'],admitted=ran)
            elif scenario=='result_after_cleanup':
                ran=first.run_once();after=snapshot(engine)
                if len(sql_trace)!=1:raise RuntimeError('routing_result_insert_not_observed')
                observations=dict(resources_at_commit=sql_trace[0]['resources'],results=after['results'],admitted=ran)
            else:
                second,other=build(1)
                first.client.acquire('evaluation',{'owner':{'database':first.database_id}})
                blocked_dispatcher=not second.run_once();blocked_admin=False
                other_client=WorkloadClient(root/'socket',root/'admin-client',
                    transport=lambda path,request:protocol.dispatch(request))
                from mldsafail.evaluator.workload import WorkloadBlocked
                try:other_client.acquire('administration',{'database':'admin'})
                except WorkloadBlocked:blocked_admin=True
                after=snapshot(engine);raw_other=snapshot(other)
                observations=dict(callers=3,acquired=1+int(not blocked_dispatcher)+int(not blocked_admin),
                    overlap=int(not blocked_dispatcher)+int(not blocked_admin))
                first.client.unused()
            state=gate.state.copy() if gate.state else None
            if gate.state is not None:gate.pause('routing_fixture_finished')
            return dict(observations=observations,before=before,after=after,sql_trace=sql_trace,
                other_database=raw_other if scenario=='cross_database_and_admin' else None,
                process_births=runtime.births,process_returncode=runtime.child.returncode if runtime.child else None,
                trace=[injection,dict(event='observation',monotonic_ns=time.monotonic_ns())],state=state)
    finally:
        runtime.terminate({})
        for dispatcher in dispatchers:dispatcher.engine.dispose()
        for engine in engines:engine.dispose()
