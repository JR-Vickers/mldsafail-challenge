"""Standalone frozen-controller Docker router; no imports from evaluator code.

Admits only the frozen execution.py command shapes. Journal storage must be
private, exclusive to one generation, and on the measured operation filesystem.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

LABEL = 'org.mldsafail.capacity-investigation'
WORKER_FLAGS = ['--network=none', '--read-only', '--user=65534:65534', '--cap-drop=ALL',
                '--security-opt=no-new-privileges', '--cpus=1', '--memory=2g',
                '--memory-swap=2g', '--pids-limit=64',
                '--tmpfs=/tmp:rw,noexec,nosuid,size=64m', '--log-driver=none', '-i']


def require(value, reason='investigation_docker_request_rejected'):
    if not value:
        raise ValueError(reason)


def publish(path, value):
    temporary = path.with_name('.' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Router:
    def __init__(self, config, command, run):
        require(set(config) - {'label'} == {'operation_id', 'parent', 'image', 'configuration', 'platform_manifest', 'journal', 'daemon', 'solver_root'})
        require(re.fullmatch('[a-f0-9]{32}', config['operation_id']))
        require(re.fullmatch('[A-Za-z0-9_.:/-]+', config['parent']))
        require(re.fullmatch('sha256:[a-f0-9]{64}', config['image']))
        require(all(re.fullmatch('sha256:[a-f0-9]{64}',config[k]) for k in ('configuration','platform_manifest')))
        self.label = config.get('label', LABEL)
        require(self.label in (LABEL, 'org.mldsafail.workload'))
        self.config, self.command, self.run = config, command, run
        self.root = Path(config['journal'])
        require(self.root.is_absolute() and '..' not in self.root.parts and not any(p.is_symlink() for p in (self.root, *self.root.parents)))
        st = self.root.stat()
        require(st.st_uid == os.getuid() and not st.st_mode & 0o077)

    def check_daemon(self):
        info = json.loads(self.command(['info', '--format', '{{json .}}']))
        require(info['ID'] == self.config['daemon'], 'investigation_daemon_changed')
        return info

    def inspected(self, identifier):
        rows = json.loads(self.command(['inspect', identifier]))
        require(len(rows) == 1)
        return rows[0]

    def owned(self, name):
        require(re.fullmatch('mlwe-[a-f0-9]{32}', name) or re.fullmatch('capacity-artifacts-' + self.config['operation_id'] + '-[a-f0-9]{32}', name))
        path = self.root / (name + '.json')
        require(not path.is_symlink())
        record = json.loads(path.read_text())
        require(record['name'] == name and record['operation_id'] == self.config['operation_id'])
        require(record.get('container_id'), 'investigation_launch_acknowledgement_missing')
        container = self.inspected(record['container_id'])
        require(container['Id'] == record['container_id'] and container['Name'] == '/' + name)
        require(container['Config']['Labels'].get(self.label) == self.config['operation_id'])
        require(container['Config']['Image'] == record['image']
                and container['Image'] in (self.config['image'],self.config['configuration']))
        require(container['HostConfig']['CgroupParent'] == self.config['parent'])
        if record.get('started_at'):
            require(container['State']['StartedAt'] == record['started_at'], 'investigation_container_restarted')
        return path, record, container

    def create_run(self, name, flags, *, artifact=False):
        path = self.root / (name + '.json')
        # Atomic exclusive reservation; no retries after lost create acknowledgements.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(dict(name=name, operation_id=self.config['operation_id'], state='create_intent'), stream)
            stream.flush()
            os.fsync(stream.fileno())
        record = self.prepare_parent(json.loads(path.read_text()))
        cid = self.command(['create', '--name', name, '--label', self.label + '=' + self.config['operation_id'],
                            '--cgroup-parent', self.config['parent'], *flags]).decode().strip()
        require(re.fullmatch('[a-f0-9]{64}', cid), 'investigation_launch_ambiguous')
        created = self.inspected(cid)
        require(created['Id'] == cid and created['Name'] == '/' + name)
        require(created['Config']['Labels'].get(self.label) == self.config['operation_id'])
        require(created['HostConfig']['CgroupParent'] == self.config['parent'])
        require(created['Config']['Image'] == (flags[-2] if artifact else flags[-1]) and
                created['Image'] in (self.config['image'], self.config['configuration']))
        record.update(state='created', container_id=cid, created_at=created.get('Created'))
        publish(path, record)
        record.update(container_id=cid, image=flags[-2] if artifact else flags[-1], state='start_intent')
        publish(path, record)
        # Register live birth before releasing serialization for timeout cleanup.
        client = self.run(['start', '--attach', '--interactive', cid])
        deadline = time.monotonic() + 2
        while True:
            state = self.inspected(cid)
            if state['State']['StartedAt'] and not state['State']['StartedAt'].startswith('0001-'):
                break
            require(client.poll() is None and time.monotonic() < deadline, 'investigation_start_ambiguous')
            time.sleep(.02)
        record.update(self.admit_start(state))
        record.update(state='running', started_at=state['State']['StartedAt'], pid=state['State'].get('Pid'))
        publish(path, record)
        lock = getattr(self, 'lock_fd', None)
        if lock is not None:
            fcntl.flock(lock, fcntl.LOCK_UN)
        result = client.wait(timeout=20 if artifact else 75)
        if lock is not None:
            deadline = time.monotonic() + 2
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    require(time.monotonic() < deadline, 'investigation_journal_busy')
                    time.sleep(.02)
        current = json.loads(path.read_text())
        if current.get('state') == 'removed':
            return result  # Authorized timeout cleanup already settled this ID.
        _, _, state = self.owned(name)
        record = dict(current, state='exited', exit_code=state['State']['ExitCode'])
        publish(path, record)
        if artifact:
            require(not state['State']['Running'])
            self.command(['rm', cid])
            publish(path, dict(record, state='removed'))
            self.remove_parent(record)
        return result

    def prepare_parent(self, record): return record
    def admit_start(self, container): return {}
    def remove_parent(self, record): return None

    def dispatch(self, args):
        require(args and all(isinstance(a, str) for a in args))
        self.check_daemon()
        image_rows=json.loads(self.command(['image','inspect',self.config['image']]))
        require(len(image_rows)==1 and image_rows[0]['Id'] in (self.config['image'],self.config['configuration'])
                and image_rows[0]['Os']=='linux' and image_rows[0]['Architecture']=='amd64', 'investigation_image_identity_changed')
        image=image_rows[0]['Id']
        if args == ['info', '--format', '{{json .}}']:
            sys.stdout.buffer.write(self.command(args))
            return 0
        if args == ['image', 'inspect', self.config['image']]:
            sys.stdout.write(json.dumps(image_rows))
            return 0
        if args == ['run', '--rm', '--network=none', '--read-only', '--entrypoint=cat', image, '/artifacts.json']:
            return self.create_run('capacity-artifacts-' + self.config['operation_id'] + '-' + uuid.uuid4().hex,
                ['--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                 '--memory=64m', '--memory-swap=64m', '--cpus=.1', '--pids-limit=16',
                 '--log-driver=none', '--entrypoint=cat', image, '/artifacts.json'], artifact=True)
        if len(args) >= 4 and args[:2] == ['run', '--name']:
            name = args[2]
            require(re.fullmatch('mlwe-[a-f0-9]{32}', name))
            suffix = args[3:]
            require(suffix[:len(WORKER_FLAGS)] == WORKER_FLAGS)
            tail = suffix[len(WORKER_FLAGS):]
            if tail != [image]:
                require(len(tail) == 3 and tail[0] == '--mount' and tail[-1] == image)
                prefix, ending = 'type=bind,src=', ',dst=/solver,readonly'
                require(tail[1].startswith(prefix) and tail[1].endswith(ending))
                source = Path(tail[1][len(prefix):-len(ending)])
                root = Path(self.config['solver_root'])
                require(source.is_absolute() and '..' not in source.parts and source.is_relative_to(root)
                        and ',' not in str(source))
            # Include all stopped records: old/ambiguous live workers block new launches.
            for other in self.root.glob('mlwe-*.json'):
                row = json.loads(other.read_text())
                require(row.get('state') in ('removed',), 'investigation_previous_worker_unsettled')
            return self.create_run(name, [*suffix])
        if len(args) == 2 and args[0] == 'kill':
            path, record, state = self.owned(args[1])
            publish(path, dict(record, state='kill_intent'))
            if state['State']['Running']:
                self.command(['kill', state['Id']])
            require(not self.inspected(state['Id'])['State']['Running'])
            publish(path, dict(record, state='terminated'))
            return 0
        if len(args) == 4 and args[:3] == ['inspect', '--format', '{{json .State}}']:
            _, _, state = self.owned(args[3])
            sys.stdout.write(json.dumps(state['State']))
            return 0
        if len(args) == 3 and args[:2] == ['rm', '-f']:
            path, record, state = self.owned(args[2])
            publish(path, dict(record, state='remove_intent'))
            if state['State']['Running']:
                self.command(['kill', state['Id']])
            require(not self.inspected(state['Id'])['State']['Running'])
            self.command(['rm', state['Id']])
            publish(path, dict(record, state='removed'))
            self.remove_parent(record)
            return 0
        raise ValueError('investigation_docker_request_rejected')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    # The frozen controller installs Docker here, not /usr/bin/docker.
    docker = '/usr/local/bin/docker'
    def command(argv):
        # Every small Docker response has bounded transport and output.
        from maintenance_transport import OwnedHelper
        helper = object.__new__(OwnedHelper)
        helper.docker, helper.runner = [docker], None
        return helper.command(argv)
    router = Router(config, command, lambda argv: subprocess.Popen([docker, *argv]))
    lock = os.open(router.root / 'router.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        router.lock_fd = lock
        return router.dispatch(args.arguments)
    finally:
        os.close(lock)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('investigation Docker routing failed; reconciliation required') from None
