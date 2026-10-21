"""Installed Linux cgroup-v2 adapter. No workload starts on import.

The helper is invoked through RuntimeTransport. Native configuration is reviewed
installation authority, never contestant input. Missing delegation or a bounded
output mount denies admission; directory size polling is not a quota substitute.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import selectors
import signal
import stat
import subprocess
import sys
import time

from mldsafail.evaluator.workload import ResourcePolicy, WorkloadBlocked
from mldsafail.evaluator.workload_socket import decode_request

LABEL = 'org.mldsafail.workload'
CGROUP_ROOT = Path('/sys/fs/cgroup')
PROC_ROOT = Path('/proc')


def require(value, reason):
    if not value:
        raise WorkloadBlocked(reason)


def publish(path, value):
    data = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    require(len(data) <= 1024 * 1024, 'native_record_limit')
    temporary = path.with_name('.' + os.urandom(16).hex())
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def private_json(path):
    path = Path(path)
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'native_symlink')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                info.st_nlink == 1 and not info.st_mode & 0o077 and info.st_size <= 1024**2,
                'native_private_record_required')
        return decode_request(stream.read(1024**2 + 1))


def command(argv, *, timeout=.65, limit=1024**2):
    """Bound both pipe reads and process exit; never collect unbounded output."""
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               close_fds=True)
    output = bytearray()
    deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                require(remaining > 0, 'native_io_deadline')
                for key, _ in selector.select(remaining):
                    data = os.read(key.fd, min(4096, limit + 1 - len(output)))
                    if not data: selector.unregister(key.fileobj)
                    output.extend(data)
                    require(len(output) <= limit, 'native_io_limit')
        require(process.wait(timeout=max(.001, deadline-time.monotonic())) == 0, 'native_io_failed')
        return bytes(output)
    finally:
        if process.poll() is None:
            try: process.kill()
            except ProcessLookupError: pass
        try: process.wait(timeout=.02)
        except subprocess.TimeoutExpired: pass
        process.stdout.close()


def birth(path):
    path = Path(path)
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'cgroup_symlink')
    info = path.stat()
    return dict(path=str(path), device=info.st_dev, inode=info.st_ino)


def process_birth(pid):
    # /proc/stat comm may contain spaces and parentheses.
    fields = (PROC_ROOT/f'{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return dict(pid=pid, start_ticks=int(fields[19]))


def events(path):
    target = Path(path)/'memory.events'
    if not target.exists() and Path(path) == CGROUP_ROOT:
        return {}
    return values(target)


def values(path):
    return {key: int(value) for key, value in (row.split() for row in Path(path).read_text().splitlines())}


class NativeRuntime:
    def __init__(self, configuration, *, run=command):
        self.config = configuration
        self.run = run
        require(set(configuration) == {'root', 'heavy', 'heavy_birth', 'ancestors', 'output',
                'disk_root', 'docker', 'daemon_id', 'boot_id', 'python', 'controller_configuration',
                'roles', 'router', 'worker', 'environment', 'retained_services'}, 'native_configuration_fields')
        for key in ('root', 'heavy', 'output', 'disk_root', 'python', 'controller_configuration', 'router'):
            path = Path(configuration[key])
            require(path.is_absolute() and '..' not in path.parts and
                    not any(p.is_symlink() for p in (path, *path.parents)), 'native_configuration_path')
        self.root = Path(configuration['root'])
        self.heavy = Path(configuration['heavy'])
        require(self.heavy.name == 'mldsafail-heavy.slice' and
                self.heavy.is_relative_to(CGROUP_ROOT), 'native_heavy_slice_required')
        require(configuration['roles'] and set(configuration['roles']) <=
                {'participant', 'create', 'reference', 'audit'}, 'native_role_configuration')
        require(type(configuration['docker']) is list and configuration['docker'] and
                Path(configuration['docker'][0]).is_absolute(), 'native_docker_command')
        require(re.fullmatch('sha256:[a-f0-9]{64}', configuration['worker']['image']), 'native_worker_image')

    def docker(self, args): return self.run([*self.config['docker'], *args])

    def identity(self):
        require(sys.platform == 'linux', 'native_linux_required')
        return dict(boot_id=Path(PROC_ROOT/'sys/kernel/random/boot_id').read_text().strip(),
                    daemon_id=json.loads(self.docker(['info', '--format', '{{json .}}']))['ID'])

    def environment(self):
        info = json.loads(self.docker(['info', '--format', '{{json .}}']))
        image = json.loads(self.docker(['image', 'inspect', self.config['worker']['image']]))[0]
        retained = {}
        for role, identifier in self.config['retained_services'].items():
            row = json.loads(self.docker(['inspect', identifier]))[0]
            retained[role] = dict(id=row['Id'], image=row['Image'], started_at=row['State']['StartedAt'], running=row['State']['Running'])
        return dict(info={key: info[key] for key in ('ID', 'CgroupDriver', 'CgroupVersion')},
                    worker=dict(id=image['Id'], os=image['Os'], architecture=image['Architecture']), retained=retained)

    def domains(self):
        require(birth(self.heavy) == self.config['heavy_birth'], 'native_heavy_replaced')
        # Bind every ancestor through the cgroup root; do not trust a caller's
        # shortened ancestor list or overlook a smaller inherited allowance.
        paths = [self.heavy]
        while paths[-1] != CGROUP_ROOT:
            paths.append(paths[-1].parent)
        require([birth(path) for path in paths] == self.config['ancestors'], 'native_ancestor_replaced')
        return paths

    def output_mount(self, policy):
        output = Path(self.config['output'])
        rows = [row.split() for row in Path(PROC_ROOT/'self/mountinfo').read_text().splitlines()]
        row = next((row for row in rows if row[4] == str(output)), None)
        require(row is not None, 'generation_quota_mount_missing')
        split = row.index('-')
        require(row[split+1] in ('ext4', 'xfs') and {'nodev', 'nosuid', 'noexec'} <= set(row[5].split(',')),
                'generation_bounded_filesystem_required')
        filesystem = os.statvfs(output)
        require(0 < filesystem.f_blocks * filesystem.f_frsize <= policy.generation_max,
                'generation_quota_unbounded')
        return dict(mount_id=int(row[0]), device=row[2], root=row[3], path=row[4],
                    bytes=filesystem.f_blocks * filesystem.f_frsize, filesystem=row[split+1])

    def preflight(self, policy):
        require(self.identity() == {k: self.config[k] for k in ('boot_id', 'daemon_id')}, 'native_runtime_replaced')
        paths = self.domains()
        require((CGROUP_ROOT/'cgroup.controllers').exists(), 'cgroup_v2_required')
        require({'cpu', 'memory', 'pids'} <= set((self.heavy/'cgroup.controllers').read_text().split()),
                'cgroup_delegation_missing')
        require({'cpu', 'memory', 'pids'} <= set((self.heavy/'cgroup.subtree_control').read_text().split()),
                'cgroup_controllers_not_enabled')
        require(not (self.heavy/'cgroup.procs').read_text().strip(), 'heavy_internal_processes')
        current = CGROUP_ROOT/Path(PROC_ROOT/'self/cgroup').read_text().strip().removeprefix('0::/').lstrip('/')
        require(not current.is_relative_to(self.heavy), 'supervisor_must_be_outside_heavy')
        memory = {key: int(value.split()[0])*1024 for key, value in
                  (row.split(':', 1) for row in Path(PROC_ROOT/'meminfo').read_text().splitlines())}
        require(memory['MemAvailable'] >= policy.reserve, 'resource_deferral')
        filesystem = os.statvfs(self.config['disk_root'])
        require(filesystem.f_bavail*filesystem.f_frsize >= policy.disk_floor, 'resource_deferral')
        self.output_mount(policy)
        allowances = [memory['MemTotal']-policy.reserve]
        for path in paths[1:]:
            limit = (path/'memory.max').read_text().strip() if (path/'memory.max').exists() else 'max'
            if limit != 'max':
                allowances.append(int(limit)-int((path/'memory.current').read_text()))
        ceiling = policy.ceiling(memory['MemTotal'], allowances)
        for name, value in {'memory.max': ceiling, 'memory.swap.max': 0,
                            'pids.max': policy.pids_max, 'cpu.max': policy.cpu_max}.items():
            target = self.heavy/name
            target.write_text(str(value))
            require(target.read_text().strip() == str(value), 'aggregate_limit_not_applied')
        # Persist a pre-acquisition baseline. Active-workload preflight must not
        # reset it; otherwise a launch check could hide a prior parent OOM.
        journal = self.root/'workload.json'
        state = private_json(journal) if journal.exists() else None
        if state is None or state['phase'] == 'complete':
            publish(self.root/'preflight.json', dict(events={str(p): events(p) for p in paths},
                    swap={str(p): int((p/'memory.swap.current').read_text()) if (p/'memory.swap.current').exists() else 0 for p in paths},
                    domains=[birth(p) for p in paths], output=self.output_mount(policy)))
        return ceiling

    def record_path(self, state):
        require(re.fullmatch('[a-f0-9]{32}', state['workload_id']), 'native_workload_id')
        return self.root/(state['workload_id']+'.native.json')

    def prepare(self, state):
        path = self.record_path(state)
        require(not path.exists(), 'native_generation_exists')
        name = 'mldsafail-heavy-'+state['workload_id']+'.slice'
        self.run(['/usr/bin/busctl', '--user', 'call', 'org.freedesktop.systemd1',
                  '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager',
                  'StartTransientUnit', 'ssa(sv)a(sa(sv))', name, 'fail', '1',
                  'Description', 's', 'MLDSAFAIL owned workload', '0'])
        scope = self.heavy/name
        require(scope.is_dir(), 'native_slice_creation_unverified')
        (scope/'cgroup.subtree_control').write_text('+cpu +memory +pids')
        leaf = scope/'creators'; leaf.mkdir()
        for name, value in {'memory.max': 512*1024**2, 'memory.swap.max': 0, 'pids.max': 256, 'cpu.max': '100000 100000'}.items():
            (leaf/name).write_text(str(value))
        output = Path(self.config['output'])/state['workload_id']; output.mkdir(mode=0o700)
        baseline = private_json(self.root/'preflight.json')
        publish(path, dict(workload_id=state['workload_id'], scope=birth(scope), leaf=birth(leaf),
                           baseline=baseline, output=str(output), controllers=[], revoked=False))
        return True

    def record(self, state):
        record = private_json(self.record_path(state))
        require(record['workload_id'] == state['workload_id'] and
                birth(record['scope']['path']) == record['scope'] and
                birth(record['leaf']['path']) == record['leaf'], 'native_scope_replaced')
        require(self.identity() == state['identity'], 'native_runtime_replaced')
        return record

    def containers(self, state, *, cleanup=False):
        identifiers = self.docker(['ps', '-aq', '--no-trunc', '--filter', 'label='+LABEL+'='+state['workload_id']]).decode().split()
        if not identifiers: return []
        rows = json.loads(self.docker(['inspect', *identifiers]))
        require({row['Id'] for row in rows} == set(identifiers), 'native_container_inventory_changed')
        for row in rows:
            require(row['Config']['Labels'].get(LABEL) == state['workload_id'], 'native_container_ownership')
            record_path = Path(self.config['output'])/state['workload_id']/'router'/(row['Name'].lstrip('/')+'.json')
            record = private_json(record_path)
            if cleanup and record.get('state') == 'create_intent' and not record.get('container_id'):
                require(record.get('operation_id') == state['workload_id'] and
                        record.get('name') == row['Name'].lstrip('/'), 'native_ambiguous_create_owner')
                record.update(container_id=row['Id'], created_at=row['Created'], state='cleanup_discovered')
                publish(record_path, record)
            require(record.get('container_id') == row['Id'] and
                    record.get('created_at') == row['Created'], 'native_container_creation_changed')
            if record.get('started_at'):
                require(record['started_at'] == row['State']['StartedAt'], 'native_container_restarted')
            if row['State']['Running']:
                actual = CGROUP_ROOT/(PROC_ROOT/f"{row['State']['Pid']}/cgroup").read_text().strip().removeprefix('0::/').lstrip('/')
                require(actual.is_relative_to(self.heavy/('mldsafail-heavy-'+state['workload_id']+'.slice')),
                        'native_container_placement')
        return rows

    def launch(self, state, specification):
        require(set(specification) == {'role'} and specification['role'] in self.config['roles'], 'native_configured_role_required')
        record = self.record(state)
        require(not record['revoked'], 'native_launch_revoked')
        role = specification['role']
        require(role != 'participant' or state['kind'] == 'evaluation', 'native_role_kind')
        require(role == 'participant' or state['kind'] == 'administration', 'native_role_kind')
        if role != 'participant':
            require(state['reference'].get('operation_id') == self.config['roles'][role]['operation_id'], 'native_administrative_authority')
        output = Path(record['output'])
        request = output/(state.get('launch_nonce', '')+'.request.json')
        require(re.fullmatch('[a-f0-9]{32}', state.get('launch_nonce', '')), 'native_launch_nonce')
        require(not request.exists(), 'native_launch_replay')
        # Move the launch helper before it dirties controller files/page cache.
        Path(record['leaf']['path'], 'cgroup.procs').write_text(str(os.getpid()))
        publish(request, dict(state=state, role=role, configuration=self.config['controller_configuration']))
        stdout = output/(role+'.stdout'); stderr = output/(role+'.stderr')
        with stdout.open('xb') as out, stderr.open('xb') as err:
            os.chmod(stdout, 0o600); os.chmod(stderr, 0o600)
            def limits():
                resource.setrlimit(resource.RLIMIT_FSIZE, (ResourcePolicy().log_max//2,)*2)
            environment = dict(self.config['environment'])
            require(set(environment) <= {'PATH', 'PYTHONPATH', 'LANG', 'LC_ALL', 'PYTHONUNBUFFERED'}, 'controller_database_credentials_forbidden')
            environment.update(HOME=str(output), GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0')
            process = subprocess.Popen([self.config['python'], '-m', 'mldsafail.evaluator.workload_controller',
                        '--request', str(request)], stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                        env=environment, start_new_session=True, close_fds=True, preexec_fn=limits)
        identity = process_birth(process.pid)
        identity.update(role=role, nonce=state['launch_nonce'], output=str(output), started_at=time.monotonic())
        record['controllers'].append(identity)
        publish(self.record_path(state), record)
        return identity

    def inspect(self, state, identity):
        record = self.record(state)
        require(identity in record['controllers'], 'native_controller_unrecorded')
        try:
            require(process_birth(identity['pid']) == {k: identity[k] for k in ('pid', 'start_ticks')}, 'native_controller_replaced')
            group = CGROUP_ROOT/(PROC_ROOT/f"{identity['pid']}/cgroup").read_text().strip().removeprefix('0::/').lstrip('/')
            require(group == Path(record['leaf']['path']), 'native_controller_placement')
        except FileNotFoundError:
            require((Path(identity['output'])/(identity['role']+'.result.json')).is_file(), 'native_controller_disconnected')
        return True

    def result(self, state):
        record = self.record(state)
        if not record['controllers']: return None
        controller = record['controllers'][-1]
        path = Path(record['output'])/(controller['role']+'.result.json')
        if path.exists(): return private_json(path)
        self.inspect(state, controller)
        return None

    def sample(self, state):
        record = self.record(state)
        policy = ResourcePolicy()
        paths = self.domains()
        require(self.output_mount(policy) == record['baseline']['output'], 'native_output_mount_replaced')
        event_delta = 0
        for path in paths:
            now = events(path); before = record['baseline']['events'][str(path)]
            require(all(now[key] >= before[key] for key in before), 'native_events_reset')
            event_delta += sum(now.get(key, 0)-before.get(key, 0) for key in ('oom', 'oom_kill', 'oom_group_kill'))
        for path in paths:
            swap = int((path/'memory.swap.current').read_text()) if (path/'memory.swap.current').exists() else 0
            require(swap <= record['baseline']['swap'][str(path)], 'native_ancestor_swap_growth')
            if path != self.heavy and (path/'memory.max').exists():
                limit = (path/'memory.max').read_text().strip()
                if limit != 'max':
                    retained = int((path/'memory.current').read_text())-int((self.heavy/'memory.current').read_text())
                    require(int(limit)-max(0, retained) >= state['ceiling'], 'native_ancestor_headroom_lost')
        require((self.heavy/'memory.max').read_text().strip() == str(state['ceiling']) and
                (self.heavy/'memory.swap.max').read_text().strip() == '0' and
                (self.heavy/'pids.max').read_text().strip() == str(policy.pids_max) and
                (self.heavy/'cpu.max').read_text().strip() == policy.cpu_max, 'native_aggregate_limits_changed')
        self.containers(state)
        if state['phase'] in ('launch_intent', 'running'):
            for identity in record['controllers']:
                require(time.monotonic()-identity['started_at'] <= self.config['roles'][identity['role']]['timeout_seconds'], 'native_controller_deadline')
                self.inspect(state, identity)
        memory = dict(row.split(':', 1) for row in Path(PROC_ROOT/'meminfo').read_text().splitlines())
        disk = os.statvfs(self.config['disk_root'])
        output = Path(record['output'])
        quota = os.statvfs(self.config['output'])
        generation = (quota.f_blocks-quota.f_bfree)*quota.f_frsize
        require(quota.f_bavail > 0, 'generation_budget_exhausted')
        logs = sum(path.stat().st_size for path in output.glob('*.std*'))
        return dict(available=int(memory['MemAvailable'].split()[0])*1024,
                    memory=int((self.heavy/'memory.current').read_text()), oom_events=event_delta,
                    swap=int((self.heavy/'memory.swap.current').read_text()), disk_free=disk.f_bavail*disk.f_frsize,
                    logs=logs, generation=generation, identity_valid=True)

    def terminate(self, state):
        record = self.record(state)
        record['revoked'] = True
        publish(self.record_path(state), record)
        # Kill creators first, then enumerate immutable label-owned container IDs.
        Path(record['scope']['path'], 'cgroup.kill').write_text('1')
        for row in self.containers(state, cleanup=True):
            if row['State']['Running']: self.docker(['kill', row['Id']])
            self.docker(['rm', '-f', row['Id']])
            path = Path(record['output'])/'router'/(row['Name'].lstrip('/')+'.json')
            container_record = private_json(path)
            publish(path, dict(container_record, state='removed'))
        return True

    def stopped(self, state):
        record = self.record(state)
        unresolved = any(private_json(path).get('state') == 'create_intent' and
                         not private_json(path).get('container_id')
                         for path in (Path(record['output'])/'router').glob('*.json'))
        return (not unresolved and not self.containers(state) and
                values(Path(record['scope']['path'])/'cgroup.events')['populated'] == 0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', type=Path, required=True)
    args = parser.parse_args(argv)
    runtime = NativeRuntime(private_json(args.configuration))
    request = decode_request(sys.stdin.buffer.readline(65537))
    require(type(request) is dict and set(request) == {'method', 'argument'}, 'native_request')
    method, argument = request['method'], request['argument']
    require(method in {'identity', 'environment', 'preflight', 'prepare', 'sample', 'launch', 'inspect', 'result', 'terminate', 'stopped'}, 'native_method')
    if method in ('identity', 'environment'): result = getattr(runtime, method)()
    elif method == 'preflight': result = runtime.preflight(ResourcePolicy(**argument['policy']))
    elif method == 'launch': result = runtime.launch(argument['state'], argument['specification'])
    elif method == 'inspect': result = runtime.inspect(argument['state'], argument['birth'])
    else: result = getattr(runtime, method)(argument['state'])
    print(json.dumps({'result': result}, allow_nan=False))


if __name__ == '__main__': main()
