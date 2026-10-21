"""Private frozen Docker CLI shim used only by supervised controllers."""
import fcntl
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import uuid

from deploy.investigation_docker import Router
from mldsafail.evaluator.native_workload import birth, command, private_json, publish, require, values


class WorkloadRouter(Router):
    def prepare_parent(self, record):
        parent = self.config['parent']
        name = parent.removesuffix('.slice')+'-'+uuid.uuid4().hex+'.slice'
        root = Path(self.native['heavy'])/parent
        planned = dict(record, cgroup_parent=name, parent_phase='intent')
        publish(self.root/(record['name']+'.json'), planned)
        command(['/usr/bin/busctl','--user','call','org.freedesktop.systemd1','/org/freedesktop/systemd1',
                 'org.freedesktop.systemd1.Manager','StartTransientUnit','ssa(sv)a(sa(sv))',name,'fail','1',
                 'Description','s','MLDSAFAIL isolated worker '+self.config['operation_id'],'0'])
        path = root/name
        artifact = record['name'].startswith('capacity-artifacts-')
        limits = {'memory.max':str(64*1024**2 if artifact else 2*1024**3),'memory.swap.max':'0',
                  'pids.max':'16' if artifact else '64','cpu.max':'10000 100000' if artifact else '100000 100000'}
        for control,value in limits.items(): (path/control).write_text(value)
        require(all((path/control).read_text().strip()==value for control,value in limits.items()), 'worker_parent_limits_unverified')
        self.parent_binding = dict(path=birth(path), limits=limits, cpu_before=values(path/'cpu.stat')['usage_usec'])
        self.config['parent'] = name
        return dict(planned, parent_phase='prepared', parent_binding=self.parent_binding)

    def admit_start(self, container):
        binding = self.parent_binding
        path = Path(binding['path']['path'])
        require(birth(path) == binding['path'] and all((path/key).read_text().strip()==value for key,value in binding['limits'].items()), 'worker_parent_replaced')
        cpu = values(path/'cpu.stat')['usage_usec']
        peak = int((path/'memory.peak').read_text())
        # This dedicated parent contains only this container; launch helpers stay
        # in creators. Kernel charges establish actual containment even when cat
        # or a tiny worker exits before /proc/PID can be inspected.
        require(cpu > binding['cpu_before'] and peak > 0, 'worker_actual_placement_unverified')
        return dict(parent_cpu_usec_after=cpu, parent_memory_peak=peak)

    def owned(self, name):
        record = private_json(self.root/(name+'.json'))
        parent = record.get('cgroup_parent')
        expected = 'mldsafail-heavy-'+self.config['operation_id']+'-'
        require(isinstance(parent,str) and parent.startswith(expected) and parent.endswith('.slice') and
                re.fullmatch('[a-f0-9]{32}', parent.removeprefix(expected).removesuffix('.slice')), 'worker_owned_parent_invalid')
        self.config['parent'] = parent
        return super().owned(name)

    def remove_parent(self, record):
        binding = record['parent_binding']['path']
        require(birth(binding['path']) == binding, 'worker_parent_replaced')
        require(values(Path(binding['path'])/'cgroup.events')['populated'] == 0, 'worker_parent_not_empty')
        command(['/usr/bin/systemctl','--user','stop',record['cgroup_parent']])

    def dispatch(self, args):
        if '--mount' in args:
            index = args.index('--mount')
            mount = args[index+1] if len(args) > index+1 else ''
            prefix, suffix = 'type=bind,src=', ',dst=/solver,readonly'
            require(mount.startswith(prefix) and mount.endswith(suffix), 'worker_mount_shape')
            source = Path(mount[len(prefix):-len(suffix)])
            require(source.is_dir() and not any(path.is_symlink() for path in (source, *source.parents)), 'worker_mount_symlink')
        return super().dispatch(args)

    def inspected(self, identifier):
        row = super().inspected(identifier)
        host = row['HostConfig']
        require(isinstance(row.get('Created'), str) and bool(row['Created']), 'worker_creation_identity_missing')
        artifact = row['Config']['Entrypoint'] == ['cat']
        require(host['NetworkMode'] == 'none' and host['ReadonlyRootfs'] is True and
                not host['Privileged'] and not host.get('PortBindings') and
                'ALL' in host['CapDrop'] and any(x.startswith('no-new-privileges') for x in host['SecurityOpt']),
                'worker_configuration_changed')
        require(host['PidsLimit'] == (16 if artifact else 64) and
                host['Memory'] == (64*1024**2 if artifact else 2*1024**3) and
                host['NanoCpus'] == (100_000_000 if artifact else 1_000_000_000) and
                host['MemorySwap'] == host['Memory'], 'worker_limits_changed')
        if artifact:
            require(row['Config']['Cmd'] == ['/artifacts.json'], 'worker_artifact_command_changed')
        else:
            image = json.loads(self.command(['image', 'inspect', self.config['image']]))[0]
            require(row['Config']['User'] == '65534:65534' and
                    row['Config']['Entrypoint'] == image['Config']['Entrypoint'] and
                    row['Config']['Cmd'] == image['Config']['Cmd'] and
                    host['Tmpfs'] == {'/tmp': 'rw,noexec,nosuid,size=64m'}, 'worker_frozen_command_changed')
        require(host['LogConfig']['Type'] == 'none', 'worker_logs_unbounded')
        require(not any(mount['Destination'] in ('/var/run/docker.sock', '/epoch') for mount in row['Mounts']),
                'worker_private_mount_forbidden')
        if row['State']['Running']:
            try:
                actual = Path('/sys/fs/cgroup')/Path(f"/proc/{row['State']['Pid']}/cgroup").read_text().strip().removeprefix('0::/').lstrip('/')
                require(actual.is_relative_to(Path(self.native['heavy'])/('mldsafail-heavy-'+self.config['operation_id']+'.slice')/self.config['parent']), 'worker_actual_cgroup_changed')
                expected = {'memory.max':str(64*1024**2 if artifact else 2*1024**3),'memory.swap.max':'0',
                            'pids.max':'16' if artifact else '64','cpu.max':'10000 100000' if artifact else '100000 100000'}
                require(all((actual/key).read_text().strip() == value for key,value in expected.items()), 'worker_actual_limits_changed')
            except FileNotFoundError:
                self.admit_start(row)
        return row

    def create_run(self, *args, **kwargs):
        current = private_json(Path(self.native['root'])/'workload.json')
        require(not (Path(self.native['root'])/(self.config['operation_id']+'.violation.json')).exists(), 'worker_router_authority_revoked')
        require(current['workload_id'] == self.config['operation_id'] and not current['paused'] and
                current['phase'] in ('launch_intent', 'running'), 'worker_launch_authority_revoked')
        return super().create_run(*args, **kwargs)


def main(argv=None):
    config = private_json(os.environ['MLDSAFAIL_ROUTER_CONFIG'])
    native = private_json(config.pop('native_configuration'))
    route = WorkloadRouter(config, lambda args: command([*native['docker'], *args]),
                           lambda args: subprocess.Popen([*native['docker'], *args]))
    route.native = native
    lock = os.open(route.root/'router.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        route.lock_fd = lock
        try:
            return route.dispatch(sys.argv[1:] if argv is None else argv)
        except BaseException as error:
            publish(Path(native['root'])/(config['operation_id']+'.violation.json'),
                    dict(workload_id=config['operation_id'], reason=type(error).__name__))
            raise
    finally:
        os.close(lock)



if __name__ == '__main__':
    raise SystemExit(main())
