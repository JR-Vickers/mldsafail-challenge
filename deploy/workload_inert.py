"""Fixed inert native fixtures. No evaluator, epoch, key or solver input."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

from mldsafail.evaluator.native_workload import NativeRuntime, birth, process_birth, publish, require, values


def exercise(state, configuration, output, checkpoint):
    runtime = NativeRuntime(configuration)
    record = runtime.record(state)
    reference = state['reference']
    require(set(reference) == {'operation_id', 'fixture', 'packet_sha256'}, 'inert_fixture_reference')
    case = reference['fixture']
    require(case in ('lifecycle', 'parent_oom', 'supervisor_death'), 'inert_fixture_not_predeclared')
    fixture = Path(record['scope']['path'])/'fixture'
    fixture.mkdir()
    for name, value in {'memory.max':64*1024**2, 'memory.swap.max':0, 'pids.max':32, 'cpu.max':'100000 100000'}.items():
        (fixture/name).write_text(str(value))
    publish(output/'fixture.json', dict(scope=birth(fixture), case=case, before=values(fixture/'memory.events')))
    if case in ('parent_oom', 'supervisor_death'):
        # All pressure is inside this disposable child, never the heavy parent or
        # a retained-service ancestor. The supervisor remains in app.slice.
        code = ('import time; x=bytearray(96*1024*1024); time.sleep(3)' if case == 'parent_oom'
                else 'import time; time.sleep(120)')
        def enter(): (fixture/'cgroup.procs').write_text(str(os.getpid()))
        process = subprocess.Popen([configuration['python'], '-c', code], preexec_fn=enter,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        publish(output/'fixture-process.json', process_birth(process.pid))
        process.wait(timeout=125)
        # Parent OOM is expected to abort protection and kill this controller;
        # returning a score/result for that case is never a passing disposition.
        require(case != 'parent_oom', 'parent_oom_must_abort_protection')
    else:
        from mldsafail.benchmark_v050.execution import environment
        environment(configuration['worker']['image'])  # Frozen read-only artifact cat; never a solver.
        name = 'mlwe-'+uuid.uuid4().hex
        journal = output/'router'/(name+'.json')
        intent = dict(operation_id=state['workload_id'], name=name, state='create_intent')
        publish(journal, intent)
        args = ['create', '--name', name, '--label', 'org.mldsafail.workload='+state['workload_id'],
                '--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--cpus=.1', '--memory=32m', '--memory-swap=32m', '--pids-limit=16', '--log-driver=none',
                '--cgroup-parent', Path(record['scope']['path']).name,
                '--entrypoint=/usr/local/bin/python', configuration['worker']['image'], '-c', 'import time; time.sleep(1)']
        identifier = runtime.docker(args).decode().strip()
        row = json.loads(runtime.docker(['inspect', identifier]))[0]
        require(row['Id'] == identifier and row['Config']['Labels']['org.mldsafail.workload'] == state['workload_id'] and
                row['HostConfig']['CgroupParent'] == Path(record['scope']['path']).name and row['Created'], 'inert_create_unverified')
        intent.update(container_id=identifier, created_at=row['Created'], state='start_intent')
        publish(journal, intent)
        runtime.docker(['start', identifier])
        row = json.loads(runtime.docker(['inspect', identifier]))[0]
        intent.update(state='running', started_at=row['State']['StartedAt'])
        publish(journal, intent)
        # Shared runtime inspection checks actual /proc placement, not merely the
        # requested --cgroup-parent. Every following read is bounded.
        runtime.containers(state)
        deadline = time.monotonic()+5
        while json.loads(runtime.docker(['inspect', identifier]))[0]['State']['Running']:
            checkpoint(); require(time.monotonic() < deadline, 'inert_container_deadline'); time.sleep(.05)
        runtime.docker(['rm', identifier]); publish(journal, dict(intent, state='removed'))
    return dict(status='administrative_complete', result=dict(case=case, fixture_scope=birth(fixture), verified=True))
