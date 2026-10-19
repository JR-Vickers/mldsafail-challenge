"""Owned commands and sequential frozen public workload for disposable diagnostics."""
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import uuid

from deploy import owned_client, owned_daemon
from scripts import production_diagnostic as diagnostic
from scripts.production_diagnostic_deadline import remaining

LABEL = 'org.mldsafail.diagnostic'


class Client:
    """Each lifecycle, observer and worker owns a separate durable registry."""
    def __init__(self, root, deadline, *, cancel=None):
        self.root = Path(root)
        self.root.mkdir(mode=0o700, exist_ok=True)
        self.deadline = deadline
        self.cancel = cancel or threading.Event()
        self.clients, self.commands = [], []
        self.save()

    def save(self):
        owned_daemon.publish(self.root / 'clients.json', dict(clients=self.clients, commands=self.commands))

    def run(self, argv, *, ceiling=10, mutation=False, check=True, **kwargs):
        from scripts.production_diagnostic_deadline import timeout
        duration = min(remaining(self.deadline, ceiling), timeout(ceiling))
        absolute_deadline = min(self.deadline, time.monotonic()+duration)
        intent = dict(id=uuid.uuid4().hex, argv_sha256=diagnostic.digest(argv),
            started=time.monotonic(), mutation=mutation, complete=False)
        self.commands.append(intent)
        self.save()
        try:
            result = owned_client.run(argv, self.clients, self.save, self.root,
                timeout=duration, absolute_deadline=absolute_deadline, cancel=self.cancel, capture_output=True, check=check, **kwargs)
            intent.update(complete=True, returncode=result.returncode)
            return result
        except BaseException as error:
            intent.update(error_type=type(error).__name__)
            raise
        finally:
            intent['finished'] = time.monotonic()
            self.save()

    def docker(self, args, **kwargs):
        return self.run(['docker', *args], **kwargs).stdout


class Workload:
    """No scientific acceptance: one sequential stream, always starting at zero."""
    def __init__(self, packet, root, deadline, run_id, worker_slice):
        self.packet, self.root, self.deadline = packet, Path(root), deadline
        self.client = Client(self.root / 'worker-client', deadline)
        self.run_id, self.worker_slice = run_id, worker_slice
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.error = None
        self.rows = []
        self.thread = threading.Thread(target=self._run, daemon=True)

    def publish(self):
        owned_daemon.publish(self.root / 'workload.json', dict(diagnostic_only=True,
            private_acceptance=False, ranking=False, rows=self.rows, error_type=self.error))

    def start(self):
        self.publish()
        self.thread.start()
        if not self.ready.wait(timeout=remaining(self.deadline, 30)) or self.error or not self.rows:
            self.stop.set()
            raise RuntimeError('Worker stream did not establish its first invocation')
        return self

    def _run(self):
        from mldsafail.benchmark_v050.generator import generate_mlwe
        from mldsafail.benchmark_v050.verify import verify_candidate
        from mldsafail.benchmark_v050.models import canonical_json
        from mldsafail.benchmark_v050.constants import MAX_SERIALIZED_BYTES
        try:
            index = 0
            while not self.stop.is_set():
                # Reserve time for a complete bounded invocation and removal.
                if time.monotonic() + 90 > self.deadline:
                    break
                case = self.packet['public_cases'][index % 50]
                instance = generate_mlwe(case['profile'], case['seed'], case['eta']).public
                if hashlib.sha256(canonical_json(instance.to_dict())).hexdigest() != case['input_digest']:
                    raise ValueError('Frozen public case identity differs')
                name = 'diagnostic-worker-' + uuid.uuid4().hex
                row = dict(index=index, case=case, name=name, started=time.monotonic(), complete=False)
                self.rows.append(row)
                self.publish()  # Unfinished invocations survive lost acknowledgement.
                args = ['create', '--name', name, '--label', LABEL + '=' + self.run_id,
                    '--cgroup-parent', self.worker_slice, '--network=none', '--read-only',
                    '--user=65534:65534', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                    '--cpus=1', '--memory=2g', '--memory-swap=2g', '--pids-limit=64',
                    '--tmpfs=/tmp:rw,noexec,nosuid,size=64m', '--log-driver=none',
                    '--mount', 'type=bind,src=' + self.packet['reference_solver_directory'] + ',dst=/solver,readonly',
                    '-i', diagnostic.WORKER]
                identifier = self.client.docker(args, mutation=True, ceiling=10).decode().strip()
                row['container_id'] = identifier
                self.publish()
                inspected = json.loads(self.client.docker(['inspect', identifier]))[0]
                if (inspected['Image'] != diagnostic.WORKER
                        or inspected['Config']['Labels'].get(LABEL) != self.run_id):
                    raise RuntimeError('Worker ownership differs')
                import subprocess
                payload = canonical_json(dict(instance=instance.to_dict(), solver='contestant'))
                workload = self
                class Input:
                    position = 0
                    def read(self, count=65536):
                        chunk = payload[self.position:self.position+count]
                        self.position += len(chunk)
                        if not chunk:
                            row['input_delivered_to_client'] = time.monotonic()
                            workload.publish()
                            workload.ready.set()
                        return chunk
                try:
                    result = self.client.run(['docker', 'start', '--attach', '--interactive', identifier],
                        mutation=True, ceiling=60, input=Input())
                    if len(result.stdout) + len(result.stderr) > MAX_SERIALIZED_BYTES:
                        raise RuntimeError('Worker output cap exceeded')
                    answer = json.loads(result.stdout)
                    verification = verify_candidate(instance, answer.get('candidate'))
                    if answer.get('candidate') is not None and not verification['verified']:
                        raise RuntimeError('Fixed reference worker returned invalid candidate')
                    row.update(status='returned', verification=verification,
                        output_sha256=hashlib.sha256(result.stdout).hexdigest())
                except subprocess.TimeoutExpired:
                    row['status'] = 'timeout'
                finally:
                    self.client.docker(['rm', '-f', identifier], mutation=True)
                row.update(complete=True, removal_acknowledged=True, finished=time.monotonic())
                self.publish()
                index += 1
        except BaseException as error:
            self.error = type(error).__name__
            self.publish()
        finally:
            self.ready.set()

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=remaining(self.deadline, 90))
        if self.thread.is_alive():
            self.client.cancel.set()
            raise RuntimeError('Worker did not settle before phase deadline')
        if self.error:
            raise RuntimeError('Worker failed: ' + self.error)
