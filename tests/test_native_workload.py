"""Fake cgroup-v2/proc fixtures. Never modify the host hierarchy."""
from types import SimpleNamespace
import json
from pathlib import Path

import pytest

import mldsafail.evaluator.native_workload as native
from mldsafail.evaluator.workload import HostGate, ProtectionAbort, ResourcePolicy, WorkloadBlocked


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(value))


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    cgroup = tmp_path/'cgroup'; cgroup.mkdir()
    proc = tmp_path/'proc'; proc.mkdir()
    monkeypatch.setattr(native, 'CGROUP_ROOT', cgroup)
    monkeypatch.setattr(native, 'PROC_ROOT', proc)
    monkeypatch.setattr(native.sys, 'platform', 'linux')
    heavy = cgroup/'mldsafail-heavy.slice'; heavy.mkdir()
    for path in (cgroup, heavy):
        for name, value in {'cgroup.controllers':'cpu memory pids', 'cgroup.subtree_control':'cpu memory pids',
                'cgroup.procs':'', 'memory.current':0, 'memory.max':3*1024**3,
                'memory.events':'oom 0\noom_kill 0\noom_group_kill 0\n', 'memory.swap.current':0,
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
    config = dict(root=str(root), heavy=str(heavy), heavy_birth=native.birth(heavy),
        ancestors=[native.birth(heavy), native.birth(cgroup)], output=str(output), disk_root=str(tmp_path),
        docker=['/usr/bin/docker'], daemon_id='daemon', boot_id='boot', python='/usr/bin/python3',
        controller_configuration=str(tmp_path/'controller.json'), roles={'participant':{'timeout_seconds':1200}},
        retained_services={}, router=str(tmp_path/'bin/docker'), worker=dict(image='sha256:'+'a'*64), environment={})
    calls = []
    def run(arguments):
        calls.append(arguments)
        if arguments[0] == '/usr/bin/busctl':
            scope = heavy/arguments[8]; scope.mkdir()
            write(scope/'cgroup.events', 'populated 0\n')
            write(scope/'cgroup.kill', '')
            return b''
        if arguments[1] == 'info': return b'{"ID":"daemon"}'
        if arguments[1] == 'ps': return b''
        pytest.fail(str(arguments))
    runtime = native.NativeRuntime(config, run=run)
    return runtime, sizes, proc, heavy, cgroup, calls


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
