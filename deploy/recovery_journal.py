"""Durable recovery ownership and independently retryable cleanup."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid
import time


def safe_path(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('Absolute non-symlink path required')
    return path


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x') as stream:
        temporary.chmod(0o600)
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class Journal:
    def __init__(self, path, config):
        self.path = safe_path(path)
        identity = {'config': config, 'files': {}}
        for key in ('env_file', 'compose'):
            source = config.get('assembly', {}).get(key)
            if source:
                identity['files'][key] = hashlib.sha256(safe_path(source).read_bytes()).hexdigest()
        self.identity = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        if path.exists():
            self.data = json.loads(path.read_text())
            if self.data['version'] != 1 or self.data['configuration'] != self.identity:
                raise ValueError('Recovery journal configuration mismatch')
        else:
            self.data = dict(version=1, configuration=self.identity, phase='created',
                             services={}, containers=[], cleanup_complete=True)

    def save(self, phase):
        self.data['phase'] = phase
        atomic_json(self.path, self.data)

    def services(self, compose, states):
        self.data.update(compose=compose, services=states, cleanup_complete=False)
        self.save('service maintenance intent')

    def container(self, name, image):
        self.data['containers'].append(dict(name=name, image=image, label=name))
        self.data['cleanup_complete'] = False
        self.save('container creation intent')

    def cleanup(self):
        errors = []
        for container in self.data['containers']:
            try:
                result = subprocess.run(['docker', 'container', 'ls', '-aq', '--no-trunc',
                                         '--filter', 'name=^/' + container['name'] + '$'],
                                        capture_output=True, text=True, check=True, timeout=30)
                identifier = result.stdout.strip()
                if not identifier:
                    continue
                info = json.loads(subprocess.check_output(['docker', 'inspect', identifier], timeout=30))[0]
                if (info['Name'] != '/' + container['name'] or info['Image'] != container['image'] or
                        info['Config']['Labels'].get('org.mldsafail.recovery') != container['label']):
                    raise ValueError('Container ownership mismatch')
                subprocess.run(['docker', 'rm', '-f', identifier], check=True, capture_output=True, timeout=60)
            except Exception:
                errors.append('container:' + container['name'])
        for role, running in self.data['services'].items():
            try:
                compose = self.data['compose']
                subprocess.run(compose + ['start' if running else 'stop', role], check=True,
                               capture_output=True, timeout=60)
                identifier = subprocess.check_output(compose + ['ps', '-aq', role], text=True, timeout=30).strip()
                deadline = time.monotonic() + 60
                while True:
                    state = json.loads(subprocess.check_output(['docker', 'inspect', '--format', '{{json .State}}', identifier], text=True, timeout=30))
                    if state['Running'] == running and (not running or state.get('Health', {}).get('Status', 'healthy') == 'healthy'):
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Service health/state mismatch')
                    time.sleep(1)
            except Exception:
                errors.append('service:' + role)
        self.data.update(cleanup_errors=errors, cleanup_complete=not errors)
        self.save('cleanup')
        if errors:
            raise RuntimeError('Recovery cleanup incomplete')
