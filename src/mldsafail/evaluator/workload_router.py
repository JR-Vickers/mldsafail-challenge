"""Private frozen Docker CLI shim used only by supervised controllers."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

from deploy.investigation_docker import Router
from mldsafail.evaluator.native_workload import command, private_json, require


class WorkloadRouter(Router):
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
            actual = Path('/sys/fs/cgroup')/Path(f"/proc/{row['State']['Pid']}/cgroup").read_text().strip().removeprefix('0::/').lstrip('/')
            require(actual.is_relative_to(Path(self.native['heavy'])/self.config['parent']), 'worker_actual_cgroup_changed')
        return row

    def create_run(self, *args, **kwargs):
        current = private_json(Path(self.native['root'])/'workload.json')
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
        return route.dispatch(sys.argv[1:] if argv is None else argv)
    finally:
        os.close(lock)


if __name__ == '__main__':
    raise SystemExit(main())
