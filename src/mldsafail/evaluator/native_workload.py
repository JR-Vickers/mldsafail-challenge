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
import platform
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
    environment = {key: value for key, value in os.environ.items() if key not in {'DOCKER_CONTEXT', 'DOCKER_HOST', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'}}
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               close_fds=True, env=environment)
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
    target = Path(path)/'memory.events.local'
    if not target.exists() and Path(path) == CGROUP_ROOT and not (Path(path)/'memory.events').exists():
        return {}
    require(target.exists(), 'memory_events_local_required')
    return values(target)


def values(path):
    return {key: int(value) for key, value in (row.split() for row in Path(path).read_text().splitlines())}


class NativeRuntime:
    def __init__(self, configuration, *, run=command):
        self.config = configuration
        self.run = run
        require(set(configuration) == {'root', 'heavy', 'heavy_birth', 'ancestors', 'output',
                'disk_root', 'docker', 'daemon_id', 'boot_id', 'python', 'controller_configuration',
                'roles', 'router', 'worker', 'environment', 'retained_services', 'python_sha256', 'controller_configuration_sha256', 'daemon_pid_file', 'daemon_executable', 'daemon_sha256'}, 'native_configuration_fields')
        for key in ('root', 'heavy', 'output', 'disk_root', 'python', 'controller_configuration', 'router'):
            path = Path(configuration[key])
            require(path.is_absolute() and '..' not in path.parts and
                    (key == 'python' or not any(p.is_symlink() for p in (path, *path.parents))), 'native_configuration_path')
        self.root = Path(configuration['root'])
        self.heavy = Path(configuration['heavy'])
        require(self.heavy.name == 'mldsafail-heavy.slice' and
                self.heavy.is_relative_to(CGROUP_ROOT), 'native_heavy_slice_required')
        require(configuration['roles'] and set(configuration['roles']) <=
                {'participant', 'create', 'reference', 'audit', 'inert'}, 'native_role_configuration')
        for role, settings in configuration['roles'].items():
            require(type(settings) is dict and set(settings) == ({'timeout_seconds'} if role == 'participant' else {'timeout_seconds', 'operation_id', 'authorization'}) and
                    type(settings['timeout_seconds']) is int and 0 < settings['timeout_seconds'] <= 5400, 'native_role_limits')
            if role=='inert':require(settings['timeout_seconds']<=180,'native_inert_deadline')
            if role != 'participant': require(re.fullmatch('[a-f0-9]{32}', settings['operation_id']), 'native_role_operation_id')
        require(type(configuration['docker']) is list and configuration['docker'] and
                Path(configuration['docker'][0]).is_absolute(), 'native_docker_command')
        require(set(configuration['worker']) == {'image', 'configuration', 'platform_manifest'} and
                all(re.fullmatch('sha256:[a-f0-9]{64}', value) for value in configuration['worker'].values()), 'native_worker_image')
        require(re.fullmatch('[a-f0-9]{64}', configuration['python_sha256']), 'native_python_identity')

    def docker(self, args): return self.run([*self.config['docker'], *args])

    def identity(self):
        require(sys.platform == 'linux', 'native_linux_required')
        pid_path = Path(self.config['daemon_pid_file'])
        require(pid_path.is_absolute() and not any(path.is_symlink() for path in (pid_path, *pid_path.parents)), 'native_daemon_pid_file_changed')
        descriptor = os.open(pid_path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor) as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1, 'native_daemon_pid_owner')
            text = stream.read(33).strip()
        require(text.isdecimal() and len(text) <= 10, 'native_daemon_pid_invalid')
        daemon = process_birth(int(text))
        executable = (PROC_ROOT/f"{daemon['pid']}/exe").stat()
        configured = Path(self.config['daemon_executable']).stat()
        require((executable.st_dev, executable.st_ino) == (configured.st_dev, configured.st_ino), 'native_daemon_executable_changed')
        require(len(self.config['docker']) == 3 and self.config['docker'][1] == '--host' and self.config['docker'][2].startswith('unix:///'), 'native_private_docker_endpoint_required')
        endpoint = Path(self.config['docker'][2].removeprefix('unix://'))
        require(not any(path.is_symlink() for path in (endpoint, *endpoint.parents)), 'native_daemon_socket_symlink')
        parent = endpoint.parent.stat()
        require(parent.st_uid == os.getuid() and not parent.st_mode & 0o077, 'native_daemon_socket_directory')
        socket = endpoint.lstat()
        require(stat.S_ISSOCK(socket.st_mode) and socket.st_uid == os.getuid(), 'native_daemon_socket_owner')
        info=json.loads(self.docker(['info', '--format', '{{json .}}']))
        return dict(boot_id=Path(PROC_ROOT/'sys/kernel/random/boot_id').read_text().strip(),
                    daemon_id=info['ID'],daemon_mode=dict(driver=info['CgroupDriver'],version=str(info['CgroupVersion']),
                    rootless=any('rootless' in option for option in info['SecurityOptions'])),
                    daemon_birth=daemon, daemon_executable=dict(device=executable.st_dev,inode=executable.st_ino),
                    socket_birth=dict(path=str(endpoint),device=socket.st_dev,inode=socket.st_ino))

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
        require(hashlib.sha256(Path(self.config['controller_configuration']).read_bytes()).hexdigest() == self.config['controller_configuration_sha256'], 'native_controller_configuration_changed')
        controller = private_json(self.config['controller_configuration'])
        require(set(controller) == {'native_configuration','identity','epoch_path','worker_image','signing_key'} and
                set(controller['identity']) == {'benchmark_version','evaluator_fingerprint','hidden_suite_version','worker_class','epoch_id'} and
                controller['identity']['benchmark_version']=='0.5.0' and controller['worker_image']==self.config['worker']['image'], 'native_controller_configuration_fields')
        key=Path(controller['signing_key']); key_info=key.lstat()
        require(not key.is_symlink() and stat.S_ISREG(key_info.st_mode) and key_info.st_uid==os.getuid() and
                key_info.st_nlink==1 and not key_info.st_mode&0o077 and 32<=key_info.st_size<=4096, 'native_signing_key_invalid')
        require(platform.python_version() == '3.12.10' and
                hashlib.sha256(Path(self.config['python']).read_bytes()).hexdigest() == self.config['python_sha256'], 'native_interpreter_changed')
        observed = self.identity()
        require(all(observed[key] == self.config[key] for key in ('boot_id', 'daemon_id')), 'native_runtime_replaced')
        require(observed['daemon_mode']==dict(driver='systemd',version='2',rootless=True) and
                platform.machine()=='x86_64', 'native_rootless_amd64_cgroup_v2_required')
        with Path(self.config['daemon_executable']).open('rb') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == self.config['daemon_sha256'], 'native_daemon_binary_changed')
        from mldsafail.benchmark_v050.execution import fingerprint
        image = json.loads(self.docker(['image', 'inspect', self.config['worker']['image']]))[0]
        require(image['Id'] in (self.config['worker']['image'],self.config['worker']['configuration']) and
                image['Os'] == 'linux' and image['Architecture'] == 'amd64' and
                image['Config']['Labels'].get('org.mldsafail.trusted') == fingerprint(), 'native_worker_environment_changed')
        paths = self.domains()
        journal_path = self.root/'workload.json'
        active = private_json(journal_path) if journal_path.exists() else None
        current_id = active['workload_id'] if active and active['phase'] != 'complete' else None
        running = self.docker(['ps', '-q', '--no-trunc']).decode().split()
        if running:
            rows = json.loads(self.docker(['inspect', *running]))
            allowed = set(self.config['retained_services'].values())
            require(all(row['Id'] in allowed or current_id and row['Config']['Labels'].get(LABEL) == current_id for row in rows), 'unreconciled_running_container')
        for child in self.heavy.iterdir():
            if child.is_dir() and (child/'cgroup.events').exists() and values(child/'cgroup.events')['populated']:
                require(current_id and child.name == 'mldsafail-heavy-'+current_id+'.slice', 'unreconciled_heavy_scope')
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
        quota = os.statvfs(self.config['output'])
        require(quota.f_bavail*quota.f_frsize >= 1024**2, 'resource_deferral')
        allowances = [memory['MemTotal']-policy.reserve]
        installed_limit=(self.heavy/'memory.max').read_text().strip()
        if installed_limit!='max':allowances.append(int(installed_limit))
        for path in paths[1:]:
            limit = (path/'memory.max').read_text().strip() if (path/'memory.max').exists() else 'max'
            if limit != 'max':
                allowances.append(int(limit)-max(0,int((path/'memory.current').read_text())-int((self.heavy/'memory.current').read_text())))
        ceiling = policy.ceiling(memory['MemTotal'], allowances)
        require(int((self.heavy/'memory.current').read_text())*100 <= ceiling*95 and
                int((self.heavy/'memory.swap.current').read_text()) == 0, 'resource_deferral')
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
        scope = self.heavy/name
        output = Path(self.config['output'])/state['workload_id']
        baseline = private_json(self.root/'preflight.json')
        record = dict(schema='mldsafail.native-workload.v1',workload_id=state['workload_id'], scope_path=str(scope), scope=None, leaf=None,
                      baseline=baseline, output=str(output), controllers=[], revoked=False, phase='prepare_intent')
        publish(path, record)  # Durable before even an empty cgroup/unit is created.
        self.run(['/usr/bin/busctl', '--user', 'call', 'org.freedesktop.systemd1',
                  '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager',
                  'StartTransientUnit', 'ssa(sv)a(sa(sv))', name, 'fail', '1',
                  'Description', 's', 'MLDSAFAIL owned workload '+state['workload_id'], '0'])
        require(scope.is_dir(), 'native_slice_creation_unverified')
        record['scope'] = birth(scope); publish(path, record)
        (scope/'cgroup.subtree_control').write_text('+cpu +memory +pids')
        leaf = scope/'creators'; leaf.mkdir()
        record['leaf'] = birth(leaf); publish(path, record)
        for control, value in {'memory.max':512*1024**2, 'memory.swap.max':0, 'pids.max':256, 'cpu.max':'100000 100000'}.items():
            (leaf/control).write_text(str(value))
        output.mkdir(mode=0o700)
        record['operation_events'] = {str(node):events(node) for node in (scope,leaf)}
        record['phase'] = 'prepared'; publish(path, record)
        return True

    def aborted_prepare(self, state):
        record = private_json(self.record_path(state))
        if record.get('phase') not in ('prepare_intent', 'prepare_aborted'): return None
        require(record['workload_id'] == state['workload_id'] and not record['controllers'], 'native_prepare_ownership_changed')
        self.domains()
        require(Path(PROC_ROOT/'sys/kernel/random/boot_id').read_text().strip() == state['identity']['boot_id'], 'native_prepare_boot_changed')
        scope = Path(record['scope_path'])
        require(scope == self.heavy/('mldsafail-heavy-'+state['workload_id']+'.slice'), 'native_prepare_scope_changed')
        if scope.exists():
            if record['scope'] is not None: require(birth(scope) == record['scope'], 'native_prepare_scope_replaced')
            # A preparation intent cannot authorize any creator. Never kill an
            # uninspected/replacement process while settling a lost empty-unit ACK.
            require(values(scope/'cgroup.events')['populated'] == 0, 'native_prepare_scope_not_empty')
        record.update(phase='prepare_aborted', revoked=True)
        publish(self.record_path(state), record)
        return record

    def record(self, state):
        record = private_json(self.record_path(state))
        require(record.get('schema') == 'mldsafail.native-workload.v1' and record.get('phase') == 'prepared' and
                record['output'] == str(Path(self.config['output'])/state['workload_id']) and
                record['scope']['path'] == str(self.heavy/('mldsafail-heavy-'+state['workload_id']+'.slice')) and
                record['leaf']['path'] == str(Path(record['scope']['path'])/'creators') and
                record['workload_id'] == state['workload_id'] and
                birth(record['scope']['path']) == record['scope'] and
                birth(record['leaf']['path']) == record['leaf'], 'native_scope_replaced')
        require(self.identity() == state['identity'], 'native_runtime_replaced')
        return record

    def containers(self, state, *, cleanup=False):
        identifiers = self.docker(['ps', '-aq', '--no-trunc', '--filter', 'label='+LABEL+'='+state['workload_id']]).decode().split()
        if not identifiers: return []
        try:
            rows = json.loads(self.docker(['inspect', *identifiers]))
        except WorkloadBlocked:
            remaining = self.docker(['ps','-aq','--no-trunc','--filter','label='+LABEL+'='+state['workload_id']]).decode().split()
            require(self.identity()==state['identity'], 'native_runtime_replaced')
            require(set(remaining)<set(identifiers), 'native_container_inspection_lost')
            rows = json.loads(self.docker(['inspect',*remaining])) if remaining else []
            identifiers = remaining
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
            pending_create = (not cleanup and record.get('state')=='create_intent' and not record.get('container_id') and
                              not row['State']['Running'] and record.get('operation_id')==state['workload_id'] and
                              record.get('name')==row['Name'].lstrip('/') and row['Config']['Image'] in
                              (self.config['worker']['image'],self.config['worker']['configuration']))
            require(pending_create or record.get('container_id') == row['Id'] and
                    record.get('created_at') == row['Created'], 'native_container_creation_changed')
            if record.get('started_at'):
                require(record['started_at'] == row['State']['StartedAt'], 'native_container_restarted')
            if row['State']['Running']:
                try:
                    actual = CGROUP_ROOT/(PROC_ROOT/f"{row['State']['Pid']}/cgroup").read_text().strip().removeprefix('0::/').lstrip('/')
                except FileNotFoundError:
                    ended = json.loads(self.docker(['inspect',row['Id']]))[0]
                    require(not ended['State']['Running'] and ended['Created']==row['Created'] and
                            ended['State']['StartedAt']==row['State']['StartedAt'], 'native_container_exit_unverified')
                    continue
                require(actual.is_relative_to(self.heavy/('mldsafail-heavy-'+state['workload_id']+'.slice')),
                        'native_container_placement')
        return rows

    def authorize_role(self, state, role):
        if role != 'participant':
            authority = private_json(self.config['roles'][role]['authorization'])
            configuration_digest = hashlib.sha256(json.dumps(self.config, sort_keys=True).encode()).hexdigest()
            require(authority.get('purpose') == ('native_workload_control_only' if role == 'inert' else 'production_unmeasured_operation_only') and
                    authority.get('authorized_by') == 'owner' and authority.get('operation_id') == state['reference'].get('operation_id') == self.config['roles'][role]['operation_id'] and
                    authority.get('packet_sha256') == state['reference'].get('packet_sha256') and
                    authority.get('native_configuration_sha256') == configuration_digest, 'native_control_authorization_required')
            if role == 'inert':
                require(0 <= time.time()-authority.get('time', 0) < 180, 'native_control_authorization_expired')
                protocol=authority.get('native_protocol',{})
                sequence=protocol.get('sequence',[])
                require(type(protocol.get('timeout_seconds')) is int and 0<protocol['timeout_seconds']<=180,
                        'native_inert_packet_budget_required')
                require(time.time()<authority['time']+protocol['timeout_seconds'],'native_inert_packet_expired')
                case=state['reference'].get('fixture')
                require(type(sequence) is list and sequence and all(type(row) is dict and
                        set(row)=={'case','seconds'} and type(row['case']) is str and
                        type(row['seconds']) is int and 0<row['seconds']<=180 for row in sequence) and
                        len({row['case'] for row in sequence})==len(sequence) and
                        case in {row['case'] for row in sequence} and sum(row['seconds'] for row in sequence)<=protocol['timeout_seconds'],
                        'native_inert_exact_case_authority_required')
                grant_path=self.root/(self.config['roles'][role]['operation_id']+'.inert-grant.json')
                grant=private_json(grant_path) if grant_path.exists() else dict(packet_sha256=authority['packet_sha256'],
                    configuration_sha256=configuration_digest,cases_started=[])
                require(grant['packet_sha256']==authority['packet_sha256'] and
                        grant['configuration_sha256']==configuration_digest,'native_inert_grant_changed')
                require(case not in [row['case'] for row in grant['cases_started']],'native_inert_case_already_attempted')
                require(len(grant['cases_started'])<len(sequence) and sequence[len(grant['cases_started'])]['case']==case,
                        'native_inert_case_order_changed')
                grant['cases_started'].append(dict(case=case,workload_id=state['workload_id']))
                publish(grant_path,grant)
                return dict(seconds=next(row['seconds'] for row in sequence if row['case']==case),
                            expires_at=authority['time']+protocol['timeout_seconds'])
            else:
                grant_path = self.root/(self.config['roles'][role]['operation_id']+'.grant.json')
                if grant_path.exists():
                    grant = private_json(grant_path)
                    require(grant['workload_id'] == state['workload_id'] and grant['packet_sha256'] == authority['packet_sha256'] and
                            grant['configuration_sha256'] == configuration_digest and time.time() < grant['expires_at'], 'native_operation_grant_changed')
                else:
                    require(0 <= time.time()-authority.get('time', 0) < 300 and
                            type(authority.get('lifetime_seconds')) is int and 0 < authority['lifetime_seconds'] <= 9000,
                            'native_operation_authorization_expired')
                    grant = dict(workload_id=state['workload_id'], packet_sha256=authority['packet_sha256'],
                                 configuration_sha256=configuration_digest, expires_at=authority['time']+authority['lifetime_seconds'],
                                 allowed_roles=authority['roles'], roles_started=[])
                require(role in grant['allowed_roles'] and role not in grant['roles_started'], 'native_role_already_attempted')
                grant['roles_started'].append(role)
                publish(grant_path, grant)

    def launch(self, state, specification):
        require(set(specification) == {'role'} and specification['role'] in self.config['roles'], 'native_configured_role_required')
        record = self.record(state)
        current = private_json(self.root/'workload.json')
        require(current['workload_id'] == state['workload_id'] and not current['paused'] and
                current['phase'] == 'launch_intent' and current['launch_nonce'] == state['launch_nonce'], 'native_launch_authority_changed')
        require(not record['revoked'], 'native_launch_revoked')
        role = specification['role']
        require(role != 'participant' or state['kind'] == 'evaluation', 'native_role_kind')
        require(role == 'participant' or state['kind'] == 'administration', 'native_role_kind')
        permission=self.authorize_role(state, role)
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
            log_limit=ResourcePolicy().log_max//(2*(1 if state['kind']=='evaluation' else 4))
            def limits():
                resource.setrlimit(resource.RLIMIT_FSIZE,(log_limit,log_limit))
            environment = dict(self.config['environment'])
            require(set(environment) <= {'PATH', 'PYTHONPATH', 'LANG', 'LC_ALL', 'PYTHONUNBUFFERED'}, 'controller_database_credentials_forbidden')
            environment.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',XDG_RUNTIME_DIR='/run/user/'+str(os.getuid()), DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/'+str(os.getuid())+'/bus', HOME=str(output), GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0')
            process = subprocess.Popen([self.config['python'], '-m', 'mldsafail.evaluator.workload_controller',
                        '--request', str(request)], stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                        env=environment, start_new_session=True, close_fds=True, preexec_fn=limits)
        identity = process_birth(process.pid)
        identity.update(role=role,nonce=state['launch_nonce'],output=str(output),started_at=time.monotonic(),log_limit=log_limit)
        if role=='inert':identity.update(authorized_seconds=permission['seconds'],authorized_until=permission['expires_at'])
        record['controllers'].append(identity)
        publish(self.record_path(state), record)
        return identity

    def inspect(self, state, identity):
        record = self.record(state)
        require(identity in record['controllers'], 'native_controller_unrecorded')
        try:
            require(process_birth(identity['pid']) == {k: identity[k] for k in ('pid', 'start_ticks')}, 'native_controller_replaced')
            limits=(PROC_ROOT/f"{identity['pid']}/limits").read_text().splitlines()
            file_limit=next(row.split()[3:5] for row in limits if row.startswith('Max file size'))
            require(file_limit==[str(identity['log_limit'])]*2,'native_log_writer_limit_changed')
            executable = (PROC_ROOT/f"{identity['pid']}/exe").stat()
            configured = Path(self.config['python']).stat()
            require((executable.st_dev, executable.st_ino) == (configured.st_dev, configured.st_ino), 'native_controller_interpreter_changed')
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
        require(not (self.root/(state['workload_id']+'.violation.json')).exists(), 'native_router_protection_failure')
        record = self.record(state)
        policy = ResourcePolicy()
        require(not record['revoked'] or state['phase'] not in ('acquired','launch_intent','running'), 'native_launch_authority_revoked')
        paths = self.domains()
        require(self.output_mount(policy) == record['baseline']['output'], 'native_output_mount_replaced')
        event_delta = 0
        monitored = [(path,record['baseline']['events'][str(path)]) for path in paths]
        monitored += [(Path(path),before) for path,before in record['operation_events'].items()]
        fixture_path = Path(record['scope']['path'])/'fixture'
        if any(controller['role']=='inert' for controller in record['controllers']) and fixture_path.exists():
            fixture = private_json(Path(record['output'])/'fixture.json')
            require(birth(fixture_path)==fixture['scope'], 'native_fixture_scope_replaced')
            monitored.append((fixture_path,fixture['before']))
        for path,before in monitored:
            now = events(path)
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
        leaf = Path(record['leaf']['path'])
        require(all((leaf/key).read_text().strip() == value for key,value in
                    {'memory.max':str(512*1024**2),'memory.swap.max':'0','pids.max':'256','cpu.max':'100000 100000'}.items()), 'native_controller_limits_changed')
        self.containers(state)
        if state['phase'] in ('launch_intent', 'running'):
            for identity in record['controllers']:
                require(time.monotonic()-identity['started_at'] <= self.config['roles'][identity['role']]['timeout_seconds'], 'native_controller_deadline')
                if identity['role']=='inert':
                    require(time.monotonic()-identity['started_at']<=identity['authorized_seconds'] and
                            time.time()<identity['authorized_until'],'native_inert_case_deadline')
                self.inspect(state, identity)
        memory = dict(row.split(':', 1) for row in Path(PROC_ROOT/'meminfo').read_text().splitlines())
        disk = os.statvfs(self.config['disk_root'])
        output = Path(record['output'])
        quota = os.statvfs(self.config['output'])
        generation = (quota.f_blocks-quota.f_bfree)*quota.f_frsize
        require(quota.f_bavail > 0, 'generation_budget_exhausted')
        for identity in record['controllers']:
            for suffix in ('stdout','stderr'):
                log=output/(identity['role']+'.'+suffix)
                require(not log.exists() or log.stat().st_size<identity['log_limit'],'native_log_budget_exhausted')
        logs = sum(path.stat().st_size for path in output.glob('*.std*'))
        return dict(available=int(memory['MemAvailable'].split()[0])*1024,
                    memory=int((self.heavy/'memory.current').read_text()), oom_events=event_delta,
                    swap=int((self.heavy/'memory.swap.current').read_text()), disk_free=disk.f_bavail*disk.f_frsize,
                    logs=logs, generation=generation, identity_valid=True)

    def emergency(self, state):
        # No Docker call: a lost/replaced daemon must not leave known owned
        # creators running. Boot and cgroup birth still constrain this kill.
        require(Path(PROC_ROOT/'sys/kernel/random/boot_id').read_text().strip() == state['identity']['boot_id'], 'native_cleanup_boot_changed')
        self.domains()
        if self.aborted_prepare(state) is not None: return True
        record = private_json(self.record_path(state))
        require(record['workload_id'] == state['workload_id'] and
                birth(record['scope']['path']) == record['scope'] and
                birth(record['leaf']['path']) == record['leaf'], 'native_cleanup_scope_changed')
        record['revoked'] = True
        publish(self.record_path(state), record)
        Path(record['scope']['path'], 'cgroup.kill').write_text('1')
        return True

    def terminate(self, state):
        if self.aborted_prepare(state) is not None: return True
        record = self.record(state)
        record['revoked'] = True
        publish(self.record_path(state), record)
        # Kill creators first, then enumerate immutable label-owned container IDs.
        Path(record['leaf']['path'], 'cgroup.kill').write_text('1')
        for row in self.containers(state, cleanup=True):
            if row['State']['Running']: self.docker(['kill', row['Id']])
            self.docker(['rm', '-f', row['Id']])
            path = Path(record['output'])/'router'/(row['Name'].lstrip('/')+'.json')
            container_record = private_json(path)
            publish(path, dict(container_record, state='removed'))
        return True

    def stopped(self, state):
        if self.aborted_prepare(state) is not None:
            return not self.docker(['ps', '-aq', '--filter', 'label='+LABEL+'='+state['workload_id']]).strip()
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
    require(method in {'identity', 'environment', 'preflight', 'prepare', 'sample', 'launch', 'inspect', 'result', 'emergency', 'terminate', 'stopped'}, 'native_method')
    if method in ('identity', 'environment'): result = getattr(runtime, method)()
    elif method == 'preflight': result = runtime.preflight(ResourcePolicy(**argument['policy']))
    elif method == 'launch': result = runtime.launch(argument['state'], argument['specification'])
    elif method == 'inspect': result = runtime.inspect(argument['state'], argument['birth'])
    else: result = getattr(runtime, method)(argument['state'])
    print(json.dumps({'result': result}, allow_nan=False))


if __name__ == '__main__': main()
