"""Fixed inert native fixtures. No evaluator, epoch, key or solver input."""
import errno
import json
import resource
import stat
import os
from pathlib import Path
import subprocess
import time
import uuid

from mldsafail.evaluator.native_workload import NativeRuntime, birth, process_birth, publish, require, values


def inject_limit(record,output):
    """Change only the disposable operation leaf, never a retained ancestor."""
    scope=Path(record['scope']['path']);leaf=Path(record['leaf']['path'])
    require(leaf.parent==scope and birth(scope)==record['scope'] and birth(leaf)==record['leaf'],
            'inert_limit_scope_changed')
    target=leaf/'memory.max';before=target.read_text().strip()
    require(before==str(512*1024**2),'inert_limit_precondition')
    target.write_text(str(256*1024**2));after=target.read_text().strip()
    require(after==str(256*1024**2),'inert_limit_injection_failed')
    raw=dict(kind='ancestor_limit_change',scope=record['scope'],leaf=record['leaf'],
             before=before,after=after,monotonic_ns=time.monotonic_ns())
    publish(Path(output)/'injection.json',raw)
    return raw


def inject_log(output):
    """Exercise the inherited kernel log limit with a sparse bounded write."""
    output=Path(output);target=output/'inert.stdout';info=os.fstat(1);expected=target.stat()
    soft,hard=resource.getrlimit(resource.RLIMIT_FSIZE)
    require(stat.S_ISREG(info.st_mode) and (info.st_dev,info.st_ino)==(expected.st_dev,expected.st_ino) and
            0<soft==hard<=16*1024**2,'inert_log_limit_not_bound')
    publish(output/'injection.json',dict(kind='log_exhaustion',log_limit=soft,
        device=info.st_dev,inode=info.st_ino,monotonic_ns=time.monotonic_ns()))
    os.lseek(1,soft-1,os.SEEK_SET);require(os.write(1,b'x')==1,'inert_log_write_failed')
    try:os.write(1,b'x')
    except OSError as error:require(error.errno==errno.EFBIG,'inert_log_wrong_kernel_error')
    else:require(False,'inert_log_kernel_limit_not_enforced')


def exercise(state, configuration, output, checkpoint):
    runtime = NativeRuntime(configuration)
    record = runtime.record(state)
    reference = state['reference']
    require(set(reference) == {'operation_id', 'fixture', 'packet_sha256'}, 'inert_fixture_reference')
    case = reference['fixture']
    require(case in ('lifecycle', 'parent_oom', 'supervisor_death','ancestor_limit_change','log_exhaustion','controller_exit'), 'inert_fixture_not_predeclared')
    fixture = Path(record['scope']['path'])/'fixture'
    fixture.mkdir()
    for name, value in {'memory.max':64*1024**2, 'memory.swap.max':0, 'pids.max':32, 'cpu.max':'100000 100000'}.items():
        (fixture/name).write_text(str(value))
    publish(output/'fixture.json', dict(scope=birth(fixture), case=case, before=values(fixture/'memory.events')))
    if case in ('ancestor_limit_change','log_exhaustion','controller_exit'):
        if case=='ancestor_limit_change':inject_limit(record,output)
        elif case=='log_exhaustion':inject_log(output)
        else:
            publish(output/'injection.json',dict(kind='controller_exit',requested_exit_code=23,process=process_birth(os.getpid()),monotonic_ns=time.monotonic_ns()))
            os._exit(23)
        while True:
            checkpoint();time.sleep(.05)
    elif case in ('parent_oom', 'supervisor_death'):
        # All pressure is inside this disposable child, never the heavy parent or
        # a retained-service ancestor. The supervisor remains in app.slice.
        code = ('import time; x=bytearray(64*1024*1024); time.sleep(3)' if case == 'parent_oom'
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
