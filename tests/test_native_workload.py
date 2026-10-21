"""Fake cgroup-v2/proc fixtures. Never modify the host hierarchy."""
from types import SimpleNamespace
import json
import sys
import hashlib
import socket
import tempfile
from pathlib import Path

import pytest

import mldsafail.evaluator.native_workload as native
from mldsafail.evaluator.workload import HostGate, ProtectionAbort, ResourcePolicy, WorkloadBlocked


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(value))
    if path.name=='memory.events' and path.with_name('memory.events.local').exists(): path.with_name('memory.events.local').write_text(str(value))


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    cgroup = tmp_path/'cgroup'; cgroup.mkdir()
    proc = tmp_path/'proc'; proc.mkdir()
    monkeypatch.setattr(native, 'CGROUP_ROOT', cgroup)
    monkeypatch.setattr(native, 'PROC_ROOT', proc)
    monkeypatch.setattr(native.sys, 'platform', 'linux')
    monkeypatch.setattr(native.platform,'machine',lambda:'x86_64')
    heavy = cgroup/'mldsafail-heavy.slice'; heavy.mkdir()
    for path in (cgroup, heavy):
        for name, value in {'cgroup.controllers':'cpu memory pids', 'cgroup.subtree_control':'cpu memory pids',
                'cgroup.procs':'', 'memory.current':0, 'memory.max':3*1024**3,
                'memory.events.local':'oom 0\noom_kill 0\noom_group_kill 0\n', 'memory.events':'oom 0\noom_kill 0\noom_group_kill 0\n', 'memory.swap.current':0,
                'memory.swap.max':0, 'cpu.max':'max 100000', 'pids.max':'max'}.items():
            write(path/name, value)
    root = tmp_path/'gate'; root.mkdir(mode=0o700)
    output = tmp_path/'output'; output.mkdir(mode=0o700)
    write(proc/'sys/kernel/random/boot_id', 'boot')
    write(proc/'self/cgroup', '0::/control')
    write(proc/'meminfo', 'MemTotal: 4194304 kB\nMemAvailable: 2097152 kB\n')
    write(proc/'self/mountinfo', f'55 1 0:44 / {output} rw,nosuid,nodev,noexec - ext4 /dev/loop99 rw\n')
    sizes = dict(output=1024**3, disk=6*1024**3)
    def statvfs(path):
        return SimpleNamespace(f_blocks=sizes['output'] if str(path)==str(output) else sizes['disk'],
                               f_frsize=1, f_bfree=sizes['output'], f_bavail=sizes['output'] if str(path)==str(output) else sizes['disk'])
    monkeypatch.setattr(native.os, 'statvfs', statvfs)
    (tmp_path/'key').write_bytes(b'k'*32); (tmp_path/'key').chmod(0o600)
    native.publish(tmp_path/'controller.json', dict(native_configuration=str(tmp_path/'native.json'),
        identity=dict(benchmark_version='0.5.0',evaluator_fingerprint='f'*64,hidden_suite_version='synthetic',worker_class='synthetic',epoch_id='synthetic'),
        epoch_path=str(tmp_path/'epoch'),worker_image='sha256:'+'a'*64,signing_key=str(tmp_path/'key')))
    socket_directory = tempfile.TemporaryDirectory(prefix='native-socket-', dir='/tmp')
    socket_path = Path(socket_directory.name).resolve()/'docker.sock'
    endpoint = socket.socket(socket.AF_UNIX); endpoint.bind(str(socket_path))
    write(tmp_path/'dockerd', 'synthetic daemon binary')
    write(tmp_path/'dockerd.pid', '12345')
    write(proc/'12345/stat', '12345 (dockerd) '+' '.join(['S']+['0']*18+['777']+['0']*20))
    (proc/'12345/exe').symlink_to(tmp_path/'dockerd')
    config = dict(daemon_pid_file=str(tmp_path/'dockerd.pid'), daemon_executable=str(tmp_path/'dockerd'),
        daemon_sha256=hashlib.sha256((tmp_path/'dockerd').read_bytes()).hexdigest(), controller_configuration_sha256=hashlib.sha256((tmp_path/'controller.json').read_bytes()).hexdigest(), root=str(root), heavy=str(heavy), heavy_birth=native.birth(heavy),
        ancestors=[native.birth(heavy), native.birth(cgroup)], output=str(output), disk_root=str(tmp_path),
        docker=['/usr/bin/docker','--host','unix://'+str(socket_path)], daemon_id='daemon', boot_id='boot', python=sys.executable, python_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        controller_configuration=str(tmp_path/'controller.json'), roles={'participant':{'timeout_seconds':1200}},
        retained_services={}, router=str(tmp_path/'bin/docker'), worker=dict(image='sha256:'+'a'*64, configuration='sha256:'+'b'*64, platform_manifest='sha256:'+'c'*64), environment={})
    calls = []
    def run(arguments):
        calls.append(arguments)
        if arguments[0] == '/usr/bin/busctl':
            scope = heavy/arguments[8]; scope.mkdir()
            write(scope/'cgroup.events', 'populated 0\n')
            write(scope/'cgroup.kill', '')
            return b''
        if arguments[0] == '/usr/bin/docker':
            args = arguments[3:]
            if args[0] == 'info': return b'{"ID":"daemon","CgroupDriver":"systemd","CgroupVersion":"2","SecurityOptions":["name=rootless"]}'
            if args[0] == 'ps': return b''
            if args[:2] == ['image','inspect']:
                from mldsafail.benchmark_v050.execution import fingerprint
                return json.dumps([dict(Id=config['worker']['image'],Os='linux',Architecture='amd64',Config=dict(Labels={'org.mldsafail.trusted':fingerprint()}))]).encode()
        pytest.fail(str(arguments))
    original_events=native.events
    def kernel_events(path):
        path=Path(path)
        if path not in (cgroup,heavy) and not (path/'memory.events.local').exists():
            (path/'memory.events.local').write_text('oom 0\noom_kill 0\noom_group_kill 0\n')
        return original_events(path)
    monkeypatch.setattr(native,'events',kernel_events)
    runtime = native.NativeRuntime(config, run=run)
    try:
        yield runtime, sizes, proc, heavy, cgroup, calls
    finally:
        endpoint.close(); socket_directory.cleanup()


def test_native_admission_aggregate_limits_and_parent_oom(fixture):
    runtime, _, _, heavy, parent, _ = fixture
    with HostGate(runtime.root, runtime).locked() as gate:
        gate.acquire('evaluation', {})
        assert (heavy/'memory.max').read_text() == str(3*1024**3)
        assert (heavy/'cpu.max').read_text() == '100000 100000'
        assert (heavy/'pids.max').read_text() == '448'
        gate.check()
        write(parent/'memory.events', 'oom 1\noom_kill 1\noom_group_kill 0\n')
        with pytest.raises(ProtectionAbort, match='operation_oom'): gate.check()
        assert gate.state['paused']


@pytest.mark.parametrize('failure', ['memory', 'disk', 'quota', 'delegation', 'identity'])
def test_native_deferral_leaves_no_owned_workload(fixture, failure):
    runtime, sizes, proc, heavy, _, _ = fixture
    if failure == 'memory': write(proc/'meminfo', 'MemTotal: 4194304 kB\nMemAvailable: 1 kB\n')
    if failure == 'disk': sizes['disk'] = 1
    if failure == 'quota': sizes['output'] = 2*1024**3
    if failure == 'delegation': write(heavy/'cgroup.subtree_control', 'cpu')
    if failure == 'identity': runtime.config['daemon_id'] = 'replacement'
    with HostGate(runtime.root, runtime).locked() as gate:
        with pytest.raises(WorkloadBlocked): gate.acquire('evaluation', {})
        assert gate.state is None
        assert not gate.path.exists()


@pytest.mark.parametrize('failure', ['swap', 'ancestor_limit', 'aggregate_limit', 'mount'])
def test_native_monitor_rejects_changed_resource_boundaries(fixture, failure):
    runtime, sizes, _, heavy, parent, _ = fixture
    with HostGate(runtime.root, runtime).locked() as gate:
        gate.acquire('evaluation', {})
        if failure == 'swap': write(parent/'memory.swap.current', '1')
        if failure == 'ancestor_limit': write(parent/'memory.max', str(1024**3))
        if failure == 'aggregate_limit': write(heavy/'pids.max', '999')
        if failure == 'mount': sizes['output'] = 2*1024**3
        with pytest.raises(ProtectionAbort): gate.check()
        assert gate.state['paused']


def test_native_bounded_command_output_and_deadline():
    import sys
    with pytest.raises(WorkloadBlocked, match='limit'):
        native.command([sys.executable, '-c', 'print("x"*4096)'], limit=100)
    with pytest.raises(WorkloadBlocked, match='deadline'):
        native.command([sys.executable, '-c', 'import time; time.sleep(5)'], timeout=.05)


def test_native_admin_grant_is_single_attempt_and_covers_later_audit(fixture, monkeypatch):
    runtime, _, _, _, _, _ = fixture
    authority_path = runtime.root/'authority.json'
    for role in ('create','audit'):
        runtime.config['roles'][role] = dict(timeout_seconds=600,operation_id='a'*32,authorization=str(authority_path))
    clock = [1000]
    monkeypatch.setattr(native.time,'time',lambda:clock[0])
    authority=dict(purpose='production_unmeasured_operation_only',authorized_by='owner',operation_id='a'*32,
        packet_sha256='b'*64,native_configuration_sha256=hashlib.sha256(json.dumps(runtime.config,sort_keys=True).encode()).hexdigest(),
        roles=['create','audit'],time=1000,lifetime_seconds=6000)
    native.publish(authority_path,authority)
    state=dict(workload_id='c'*32,reference=dict(operation_id='a'*32,packet_sha256='b'*64))
    runtime.authorize_role(state,'create')
    clock[0] = 1400  # Audit is in the same admitted operation, not a fresh epoch.
    runtime.authorize_role(state,'audit')
    with pytest.raises(WorkloadBlocked,match='already_attempted'): runtime.authorize_role(state,'create')
    state['workload_id']='d'*32
    with pytest.raises(WorkloadBlocked,match='grant_changed'): runtime.authorize_role(state,'create')


def test_native_expired_authorization_cannot_start_an_operation(fixture, monkeypatch):
    runtime, _, _, _, _, _ = fixture
    path = runtime.root/'authority.json'
    runtime.config['roles']['create'] = dict(timeout_seconds=600,operation_id='a'*32,authorization=str(path))
    monkeypatch.setattr(native.time,'time',lambda:1401)
    native.publish(path,dict(purpose='production_unmeasured_operation_only',authorized_by='owner',operation_id='a'*32,
        packet_sha256='b'*64,native_configuration_sha256=hashlib.sha256(json.dumps(runtime.config,sort_keys=True).encode()).hexdigest(),
        roles=['create'],time=1000,lifetime_seconds=6000))
    with pytest.raises(WorkloadBlocked,match='expired'):
        runtime.authorize_role(dict(workload_id='c'*32,reference=dict(operation_id='a'*32,packet_sha256='b'*64)),'create')
    assert not list(runtime.root.glob('*.grant.json'))


def test_same_daemon_id_with_replaced_process_still_revokes_ownership(fixture):
    runtime, _, proc, _, _, _ = fixture
    with HostGate(runtime.root,runtime).locked() as gate:
        gate.acquire('evaluation',{})
        write(proc/'12345/stat','12345 (dockerd) '+' '.join(['S']+['0']*18+['778']+['0']*20))
        with pytest.raises(ProtectionAbort,match='runtime_identity_changed'): gate.check()
        with pytest.raises(ProtectionAbort): gate.reconcile()
        record=native.private_json(runtime.record_path(gate.state))
        assert Path(record['scope']['path'],'cgroup.kill').read_text() == '1'
        assert gate.state['paused'] and gate.state['phase'] != 'complete'


def test_lost_empty_scope_preparation_ack_is_cleanup_only(fixture):
    runtime, _, _, _, _, _ = fixture
    original=runtime.run
    def lose_ack(args):
        result=original(args)
        if args[0]=='/usr/bin/busctl': raise TimeoutError('lost empty slice ack')
        return result
    runtime.run=lose_ack
    with HostGate(runtime.root,runtime).locked() as gate:
        with pytest.raises(TimeoutError): gate.acquire('administration',{})
        assert gate.state['paused']
        runtime.run=original
        gate.reconcile()
        assert gate.state['phase']=='cleaned'
        assert native.private_json(runtime.record_path(gate.state))['phase']=='prepare_aborted'
        gate.resume()


def test_unknown_heavy_subtree_blocks_admission_without_attempt(fixture):
    runtime, _, _, heavy, _, _=fixture
    unknown=heavy/'unknown.scope';unknown.mkdir()
    write(unknown/'cgroup.events','populated 1\n')
    with HostGate(runtime.root,runtime).locked() as gate:
        with pytest.raises(WorkloadBlocked,match='unreconciled_heavy_scope'): gate.acquire('evaluation',{})
        assert gate.state is None


def test_ambiguous_worker_create_cannot_be_reported_stopped(fixture):
    runtime, _, _, _, _, _=fixture
    with HostGate(runtime.root,runtime).locked() as gate:
        gate.acquire('evaluation',{})
        record=native.private_json(runtime.record_path(gate.state))
        router=Path(record['output'])/'router';router.mkdir(mode=0o700)
        native.publish(router/'mlwe-ambiguous.json',dict(state='create_intent',name='mlwe-ambiguous'))
        assert not runtime.stopped(gate.state)
        with pytest.raises(WorkloadBlocked): gate.acquire('administration',{})


def test_preflight_does_not_subtract_existing_owned_usage_twice(fixture):
    runtime, _, _, heavy, parent, _=fixture
    with HostGate(runtime.root,runtime).locked() as gate:
        gate.acquire('evaluation',{})
        write(heavy/'memory.current',128*1024**2)
        write(parent/'memory.current',128*1024**2)
        assert runtime.preflight(ResourcePolicy()) == gate.state['ceiling']


def test_worker_local_oom_does_not_become_parent_infrastructure_oom(fixture):
    runtime, _, _, heavy, _, _=fixture
    with HostGate(runtime.root,runtime).locked() as gate:
        gate.acquire('evaluation',{})
        # Hierarchical worker events change; the operation's local limit did not OOM.
        (heavy/'memory.events').write_text('oom 1\noom_kill 1\noom_group_kill 0\n')
        gate.check()
        assert not gate.state['paused']


def test_kernel_stream_limit_exhaustion_is_a_protection_abort(fixture):
    runtime, _, _, _, _, _=fixture
    with HostGate(runtime.root,runtime).locked() as gate:
        gate.acquire('evaluation',{})
        gate.state['phase']='cleaned';gate._write()
        path=runtime.record_path(gate.state);record=native.private_json(path)
        record['controllers']=[dict(role='participant',log_limit=16)]
        native.publish(path,record)
        (Path(record['output'])/'participant.stdout').write_bytes(b'x'*16)
        with pytest.raises(ProtectionAbort):gate.check()
        assert gate.state['paused']
