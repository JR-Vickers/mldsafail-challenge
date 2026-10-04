"""Owned Docker lifecycle for public frozen-worker reproduction, never staging."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

from deploy.recovery_journal import atomic_json, safe_path

LABEL = 'org.mldsafail.public-reproduction'


class ReproductionRun:
    def __init__(self, root, images, cleanup_only=False):
        self.root = safe_path(root)
        for protected in ('/srv/mldsafail', '/srv/mldsafail-evaluator', '/etc/mldsafail'):
            path = Path(protected).resolve()
            if self.root.is_relative_to(path) or path.is_relative_to(self.root):
                raise ValueError('Reproduction root overlaps protected deployment')
        self.images = images
        if any(not isinstance(image, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', image) for image in images):
            raise ValueError('Immutable image IDs required')
        self.cleanup_only = cleanup_only
        self.descriptor = None

    def __enter__(self):
        self.root.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.descriptor = os.open(self.root.with_name('.' + self.root.name + '.lock'),
                                  os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.cleanup_only:
                if self.root.stat().st_uid != os.getuid() or self.root.stat().st_mode & 0o077:
                    raise ValueError('Private owned reproduction root required')
                path = safe_path(self.root / 'journal.json')
                if path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
                    raise ValueError('Private owned reproduction journal required')
                self.journal = json.loads(path.read_text())
            else:
                self.root.mkdir(mode=0o700)
                source = Path(__file__).resolve().parents[1]
                if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain']).strip():
                    raise ValueError('Clean retained reproduction source required')
                identity = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD']).decode().strip()
                for image in self.images:
                    item = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image], timeout=10))[0]
                    if item['Id'] != image or item['Architecture'] != 'amd64':
                        raise ValueError('Exact retained Linux amd64 images required')
                self.journal = {'run_id': uuid.uuid4().hex, 'source_commit': identity, 'images': self.images,
                                'cleanup_complete': False, 'attempts': [],
                                'orchestrator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
                self.save()
            expected_socket = 'unix:///run/user/' + str(os.getuid()) + '/docker.sock'
            if os.environ.get('DOCKER_HOST') != expected_socket:
                raise ValueError('Explicit current-user rootless Docker socket required')
            if self.cleanup_only and self.journal.get('docker_host') != expected_socket:
                raise ValueError('Durable Docker socket binding mismatch')
            self.journal['docker_host'] = expected_socket
            self.save()
            if not re.fullmatch(r'[a-f0-9]{32}', self.journal.get('run_id', '')):
                raise ValueError('Invalid durable ownership identity')
            return self
        except BaseException:
            os.close(self.descriptor)
            self.descriptor = None
            raise

    def save(self):
        atomic_json(self.root / 'journal.json', self.journal)

    def invoke(self, image, arguments, request=None):
        if image not in self.images:
            raise ValueError('Image outside declared inventory')
        name = 'mldsafail-repro-' + self.journal['run_id'] + '-' + str(len(self.journal['attempts']))
        attempt = {'name': name, 'image': image, 'phase': 'create_intent',
                   'request_sha256': hashlib.sha256(request or b'').hexdigest()}
        self.journal['attempts'].append(attempt)
        self.save()  # durable intent precedes Docker creation
        prefix = self.root / name
        with prefix.with_suffix('.input').open('xb') as source_input:
            source_input.write(request or b'')
            source_input.flush()
            os.fsync(source_input.fileno())
        try:
            subprocess.run(['docker', 'create', '--name', name, '--label', LABEL + '=' + self.journal['run_id'],
                            '--network=none', '--read-only', '--cpus=1', '--memory=2g',
                            '--entrypoint=' + ('cat' if arguments == ['/artifacts.json'] else 'python'), '-i',
                            image, *arguments], check=True, capture_output=True, timeout=10)
            attempt['phase'] = 'created'
            self.save()
            # File-backed streams retain partial output without unbounded RAM.
            with prefix.with_suffix('.stdout').open('xb') as output, prefix.with_suffix('.stderr').open('xb') as error:
                subprocess.run(['docker', 'start', '-ai', name], input=request, stdout=output, stderr=error,
                               check=True, timeout=65)
            attempt['phase'] = 'finished'
            self.save()
            return prefix.with_suffix('.stdout').read_bytes()
        except BaseException as error:
            attempt.update(phase='failed', error_type=type(error).__name__)
            self.save()
            raise
        finally:
            self.remove(name)

    def remove(self, name):
        item = subprocess.run(['docker', 'container', 'inspect', name], capture_output=True, timeout=10)
        if item.returncode:
            # Absence must be confirmed by final inventory, never inferred passed here.
            return
        data = json.loads(item.stdout)[0]
        if data['Config'].get('Labels', {}).get(LABEL) != self.journal['run_id']:
            raise ValueError('Reproduction container ownership mismatch')
        subprocess.run(['docker', 'rm', '-f', name], check=True, capture_output=True, timeout=10)

    def cleanup(self):
        self.journal['cleanup_phase'] = 'running'
        self.save()
        errors = []
        try:
            names = subprocess.check_output(['docker', 'ps', '-aq', '--filter',
                        'label=' + LABEL + '=' + self.journal['run_id']], timeout=10).decode().splitlines()
            for name in names:
                try:
                    self.remove(name)
                except Exception as error:
                    errors.append(type(error).__name__)
        except Exception as error:
            errors.append(type(error).__name__)
        try:
            remaining = subprocess.check_output(['docker', 'ps', '-aq', '--filter',
                         'label=' + LABEL + '=' + self.journal['run_id']], timeout=10).decode().splitlines()
        except Exception as error:
            errors.append(type(error).__name__)
            remaining = ['inventory_unavailable']
        self.journal.update(cleanup_complete=not errors and not remaining, cleanup_errors=errors,
                            remaining_owned_containers=remaining, cleanup_phase='complete' if not errors and not remaining else 'incomplete')
        self.save()
        return self.journal['cleanup_complete']

    def __exit__(self, error_type, error, traceback):
        try:
            if not self.cleanup() and error_type is None:
                raise RuntimeError('Reproduction cleanup incomplete')
        finally:
            os.close(self.descriptor)
