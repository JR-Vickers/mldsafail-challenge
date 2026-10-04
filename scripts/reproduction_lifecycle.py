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
from deploy import owned_client
from scripts import operator_daemon_lifecycle

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
        self.daemon_descriptor = None

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
                from mldsafail.benchmark_v050 import generator as current_generator
                from research.primitive_selection import generator as frozen_generator
                for module, expected in ((current_generator, source / 'src/mldsafail/benchmark_v050/generator.py'),
                                         (frozen_generator, source / 'research/primitive_selection/generator.py')):
                    if Path(module.__file__).resolve() != expected.resolve():
                        raise ValueError('Resolved reproduction module differs from retained source')
                identity = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD']).decode().strip()
                self.journal = {'run_id': uuid.uuid4().hex, 'source_commit': identity, 'images': self.images,
                                'cleanup_complete': False, 'attempts': [],
                                'docker_host': os.environ.get('DOCKER_HOST'),
                                'orchestrator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
                self.save()
            manifest = (self.journal.get('dedicated_daemon') if self.cleanup_only else
                        operator_daemon_lifecycle.bind(self.journal, self.save))
            if not isinstance(manifest, dict):
                raise ValueError('Durable dedicated daemon binding required')
            self.daemon_descriptor = operator_daemon_lifecycle.lock_daemon(manifest)
            if not self.cleanup_only:
                operator_daemon_lifecycle.owned_daemon.verify_environment(manifest)
            expected_socket = 'unix://' + manifest['socket']
            if os.environ.get('DOCKER_HOST') != expected_socket:
                raise ValueError('Explicit isolated dedicated Docker socket required')
            if self.cleanup_only and self.journal.get('docker_host') != expected_socket:
                raise ValueError('Durable Docker socket binding mismatch')
            self.journal['docker_host'] = expected_socket
            self.save()
            if not re.fullmatch(r'[a-f0-9]{32}', self.journal.get('run_id', '')):
                raise ValueError('Invalid durable ownership identity')
            if not self.cleanup_only:
                for image in self.images:
                    item = json.loads(self.command(['docker', 'image', 'inspect', image], timeout=10).stdout)[0]
                    if item['Id'] != image or item['Architecture'] != 'amd64':
                        raise ValueError('Exact retained Linux amd64 images required')
            return self
        except BaseException:
            if self.daemon_descriptor is not None:
                operator_daemon_lifecycle.release_daemon(self.daemon_descriptor)
                self.daemon_descriptor = None
            os.close(self.descriptor)
            self.descriptor = None
            raise

    def save(self):
        atomic_json(self.root / 'journal.json', self.journal)

    def command(self, argv, **kwargs):
        clients = self.cleanup_clients if hasattr(self, 'cleanup_clients') else self.journal.setdefault('clients', [])
        save = self.cleanup_save if hasattr(self, 'cleanup_clients') else self.save
        mutation = None
        if argv[:2] in (['docker', 'create'], ['docker', 'start']):
            mutation = {'id': uuid.uuid4().hex, 'acknowledged': False}
            self.journal.setdefault('daemon_mutations', []).append(mutation)
            self.save()
        result = owned_client.run(argv, clients, save, self.root, **kwargs)
        if mutation is not None:
            mutation['acknowledged'] = True
            self.save()
        return result

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
        original_error = None
        try:
            self.command(['docker', 'create', '--name', name, '--label', LABEL + '=' + self.journal['run_id'],
                            '--cgroup-parent=' + self.journal['dedicated_daemon']['worker_cgroup_parent'],
                            '--network=none', '--read-only', '--cpus=1', '--memory=2g',
                            '--entrypoint=' + ('cat' if arguments == ['/artifacts.json'] else 'python'), '-i',
                            image, *arguments], check=True, capture_output=True, timeout=10)
            attempt['phase'] = 'created'
            self.save()
            # File-backed streams retain partial output without unbounded RAM.
            with prefix.with_suffix('.stdout').open('xb') as output, prefix.with_suffix('.stderr').open('xb') as error:
                self.command(['docker', 'start', '-ai', name], input=request, stdout=output, stderr=error,
                               check=True, timeout=65)
            attempt['phase'] = 'finished'
            self.save()
            output_path = prefix.with_suffix('.stdout')
            if output_path.stat().st_size > 32 * 1024 * 1024:
                attempt.update(phase='failed', error_type='OutputLimitExceeded', output_limit_bytes=32 * 1024 * 1024)
                self.save()
                raise RuntimeError('Public worker output exceeded 32MiB; raw evidence retained')
            return output_path.read_bytes()
        except BaseException as error:
            original_error = error
            attempt.update(phase='failed', error_type=type(error).__name__)
            try:
                self.save()
            except Exception as publication_error:
                error.add_note('Failure publication failed: ' + type(publication_error).__name__)
            raise
        finally:
            try:
                self.remove(name)
            except Exception as cleanup_error:
                if original_error is None:
                    raise
                original_error.add_note('Independent removal failed: ' + type(cleanup_error).__name__)

    def remove(self, name):
        item = self.command(['docker', 'container', 'inspect', name], capture_output=True, check=False, timeout=10)
        if item.returncode:
            # Absence must be confirmed by final inventory, never inferred passed here.
            return
        data = json.loads(item.stdout)[0]
        if data['Config'].get('Labels', {}).get(LABEL) != self.journal['run_id']:
            raise ValueError('Reproduction container ownership mismatch')
        self.command(['docker', 'rm', '-f', name], check=True, capture_output=True, timeout=10)

    def cleanup(self):
        errors = []
        def publish():
            try:
                self.save()
            except Exception as error:
                errors.append('JournalPublication:' + type(error).__name__)
        self.journal['cleanup_phase'] = 'running'
        self.journal['cleanup_complete'] = False
        publish()
        try:
            retained_clients = self.journal.get('clients', [])
            if not isinstance(retained_clients, list):
                raise ValueError('Client receipt must be a list')
            clients = list(retained_clients)
        except Exception as error:
            errors.append('ClientReceipt:' + type(error).__name__)
            clients = []
        for path in self.root.glob('cleanup-clients-*.json'):
            try:
                receipt = json.loads(safe_path(path).read_text())
                if not isinstance(receipt, list):
                    raise ValueError('Client receipt must be a list')
                clients.extend(receipt)
            except Exception as error:
                errors.append('ClientReceipt:' + type(error).__name__)
        errors.extend(operator_daemon_lifecycle.settle(self.journal, clients, self.root, self.save,
                      permit_restart=not any(isinstance(error, str) and error.startswith('ClientReceipt:') for error in errors)))
        # Independent gated cleanup does not publish through the damaged run journal.
        self.cleanup_clients = []
        receipt_path = self.root / ('cleanup-clients-' + uuid.uuid4().hex + '.json')
        self.cleanup_save = lambda: atomic_json(receipt_path, self.cleanup_clients)
        try:
            names = self.command(['docker', 'ps', '-aq', '--filter',
                        'label=' + LABEL + '=' + self.journal['run_id']], timeout=10).stdout.decode().splitlines()
            for name in names:
                try:
                    self.remove(name)
                except Exception as error:
                    errors.append(type(error).__name__)
        except Exception as error:
            errors.append(type(error).__name__)
        try:
            remaining = self.command(['docker', 'ps', '-aq', '--filter',
                         'label=' + LABEL + '=' + self.journal['run_id']], timeout=10).stdout.decode().splitlines()
        except Exception as error:
            errors.append(type(error).__name__)
            remaining = ['inventory_unavailable']
        self.journal.update(cleanup_complete=not errors and not remaining, cleanup_errors=errors,
                            remaining_owned_containers=remaining, cleanup_phase='complete' if not errors and not remaining else 'incomplete')
        publish()
        self.journal['cleanup_complete'] = not errors and not remaining
        self.journal['cleanup_errors'] = errors
        if errors:
            try:
                atomic_json(self.root / ('cleanup-failure-' + uuid.uuid4().hex + '.json'), self.journal)
            except Exception:
                pass
        return self.journal['cleanup_complete']

    def __exit__(self, error_type, error, traceback):
        try:
            try:
                complete = self.cleanup()
            except Exception as cleanup_error:
                if error is None:
                    raise
                error.add_note('Independent cleanup failed: ' + type(cleanup_error).__name__)
                complete = False
            if not complete:
                if error_type is None:
                    raise RuntimeError('Reproduction cleanup incomplete')
                error.add_note('Reproduction cleanup remains incomplete')
        finally:
            if self.daemon_descriptor is not None:
                operator_daemon_lifecycle.release_daemon(self.daemon_descriptor)
            os.close(self.descriptor)
