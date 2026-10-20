"""Versioned private pipe SQL protocol for an owned frozen-image helper.

No Docker launch on import. The host adapter accepts an already owned helper;
production admission must inspect its daemon/container/image/network identities.
"""
import json
import select
import threading
import time
import uuid

MAX_MESSAGE = 65536
VERSION = 1


def encode(value):
    data = json.dumps(value, separators=(',', ':')).encode() + b'\n'
    if len(data) > MAX_MESSAGE:
        raise ValueError('maintenance_transport_message_limit')
    return data


class Connection:
    autocommit = True

    def __init__(self, process, identity, expected, *, timeout=.5):
        if not 0 < timeout <= 9002 or identity() != expected:
            raise ValueError('maintenance_transport_identity')
        self.process, self.identity, self.expected = process, identity, expected
        # Holder uses lifetime + bounded transport margin; verifier uses <= .5s.
        self.timeout, self.mutex = timeout, threading.Lock()
        self.rows = []
        self.closed = False
        self.buffer = b''

    def execute(self, sql, params=()):
        with self.mutex:
            if self.closed or self.process.poll() is not None or self.identity() != self.expected:
                raise RuntimeError('maintenance_transport_lost')
            request = uuid.uuid4().hex
            data = encode(dict(version=VERSION, request=request, sql=sql, params=params))
            deadline = time.monotonic() + self.timeout
            # Nonblocking descriptors ensure even a blackholed helper is bounded.
            import os
            os.set_blocking(self.process.stdin.fileno(), False)
            os.set_blocking(self.process.stdout.fileno(), False)
            try:
                while data:
                    left = deadline - time.monotonic()
                    if left <= 0 or not select.select([], [self.process.stdin], [], left)[1]:
                        raise TimeoutError()
                    count = os.write(self.process.stdin.fileno(), data)
                    data = data[count:]
                while b'\n' not in self.buffer:
                    left = deadline - time.monotonic()
                    if left <= 0 or not select.select([self.process.stdout], [], [], left)[0]:
                        raise TimeoutError()
                    block = os.read(self.process.stdout.fileno(), 4096)
                    if not block:
                        raise RuntimeError()
                    self.buffer += block
                    if len(self.buffer) > MAX_MESSAGE:
                        raise RuntimeError()
                line, self.buffer = self.buffer.split(b'\n', 1)
                response = json.loads(line)
                if (response['version'] != VERSION or response['request'] != request
                        or response.get('error') or self.buffer):
                    raise RuntimeError()
                self.rows = [tuple(row) for row in response['rows']]
                return self
            except Exception:
                self.closed = True
                # No SQL, credentials or server errors escape the private helper.
                raise RuntimeError('maintenance_transport_reconciliation_required') from None

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True
        # Owned launcher must additionally inspect and stop helper container.
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
                self.process.wait(timeout=2)
        if self.process.poll() is None:
            raise RuntimeError('maintenance_helper_remains')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def serve(input_stream, output_stream, connect):
    """Inside helper: first bounded private input carries credentials, never argv."""
    first = input_stream.readline(MAX_MESSAGE + 1)
    if len(first) > MAX_MESSAGE or not first.endswith(b'\n'):
        raise ValueError('maintenance_transport_input')
    credentials = json.loads(first)
    connection = connect(credentials)
    try:
        while True:
            line = input_stream.readline(MAX_MESSAGE + 1)
            if not line:
                return
            if len(line) > MAX_MESSAGE or not line.endswith(b'\n'):
                raise ValueError('maintenance_transport_input')
            value = json.loads(line)
            if set(value) != {'version', 'request', 'sql', 'params'} or value['version'] != VERSION:
                raise ValueError('maintenance_transport_version')
            try:
                cursor = connection.execute(value['sql'], value['params'])
                rows = cursor.fetchall() if cursor.description else []
                response = dict(version=VERSION, request=value['request'], rows=rows)
                data = encode(response)
            except Exception:
                data = encode(dict(version=VERSION, request=value['request'], error='query_failed'))
            output_stream.write(data)
            output_stream.flush()
    finally:
        connection.close()


class OwnedHelper:
    """Host-side launcher: two instances supply separate holder/verifier sessions.

    identity_probe must independently inspect database container, Docker daemon,
    source bytes and connection authority with bounded I/O. No exposed DB port.
    """
    def __init__(self, root, expected, identity_probe, docker, image, source, *, runner=None):
        from pathlib import Path
        from deploy.production_preparation import IMAGES
        if image != 'sha256:' + IMAGES['COORDINATOR_IMAGE']:
            raise ValueError('maintenance_helper_frozen_image_required')
        if not {'database_container', 'daemon', 'operator_sha256', 'connection_authority'} <= set(expected):
            raise ValueError('maintenance_helper_identity_incomplete')
        self.root, self.expected, self.probe = Path(root), expected, identity_probe
        self.docker, self.image, self.source = list(docker), image, str(Path(source).absolute())
        self.runner = runner
        self.container = None
        self.connection = None

    def command(self, args):
        import subprocess
        if self.runner is not None:
            result = self.runner(self.docker + args, check=True, capture_output=True, timeout=2)
            if len(result.stdout) + len(result.stderr) > MAX_MESSAGE:
                raise RuntimeError('maintenance_helper_inspection_limit')
            return result.stdout
        import os
        import selectors
        process = subprocess.Popen(self.docker + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        selector = selectors.DefaultSelector()
        buffers = [bytearray(), bytearray()]
        for index, stream in enumerate((process.stdout, process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, index)
        deadline = time.monotonic() + 2
        try:
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise RuntimeError('maintenance_helper_inspection_timeout')
                for key, _ in selector.select(max(0, deadline - time.monotonic())):
                    data = os.read(key.fileobj.fileno(), 4096)
                    if not data:
                        selector.unregister(key.fileobj)
                    else:
                        buffers[key.data].extend(data)
                        if sum(map(len, buffers)) > MAX_MESSAGE:
                            raise RuntimeError('maintenance_helper_inspection_limit')
            if process.wait(timeout=max(.001, deadline - time.monotonic())) != 0:
                raise RuntimeError('maintenance_helper_command_failed')
            return bytes(buffers[0])
        finally:
            selector.close()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            process.stdout.close()
            process.stderr.close()

    def open(self, credentials, authorization, *, timeout=.5, parent):
        import hashlib
        import os
        import subprocess
        from pathlib import Path
        from deploy.recovery_journal import atomic_json
        if (authorization.get('purpose') != 'production_maintenance'
                or authorization.get('state') != 'execution_ready'
                or self.probe() != self.expected
                or hashlib.sha256(Path(self.source).read_bytes()).hexdigest() != self.expected['operator_sha256']):
            raise ValueError('maintenance_helper_authorization_required')
        if not parent or not self.expected['database_container']:
            raise ValueError('maintenance_helper_scope_required')
        name = 'maintenance-sql-' + uuid.uuid4().hex
        self.root.mkdir(mode=0o700)
        atomic_json(self.root / 'helper.json', dict(state='create_intent', name=name, identity=self.expected))
        # Only the database's inspected network namespace is shared; no port map.
        output = self.command(['create', '--interactive', '--name', name, '--label',
            'org.mldsafail.maintenance-helper=' + name, '--network',
            'container:' + self.expected['database_container'], '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--memory=64m', '--memory-swap=64m', '--cpus=.1',
            '--pids-limit=16', '--cgroup-parent', parent, '--log-driver=none',
            '--mount', 'type=bind,src=' + self.source + ',dst=/maintenance_transport.py,readonly',
            '--entrypoint', '/app/.venv/bin/python', self.image, '-c',
            'import sys,psycopg; sys.path.insert(0,"/"); from maintenance_transport import serve; '
            'serve(sys.stdin.buffer,sys.stdout.buffer,lambda c:psycopg.connect(**c,autocommit=True,connect_timeout=2))'])
        self.container = output.decode().strip()
        import re
        if not re.fullmatch('[a-f0-9]{64}', self.container):
            raise RuntimeError('maintenance_helper_create_ambiguous')
        atomic_json(self.root / 'helper.json', dict(state='start_intent', name=name, container=self.container, identity=self.expected))
        process = subprocess.Popen(self.docker + ['start', '--attach', '--interactive', self.container],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.connection = Connection(process, self.probe, self.expected, timeout=timeout)
        # Private pipe bootstrap is bounded and contains no command-line secrets.
        data = encode(credentials)
        os.set_blocking(process.stdin.fileno(), False)
        deadline = time.monotonic() + 2
        while data:
            left = deadline - time.monotonic()
            if left <= 0 or not select.select([], [process.stdin], [], left)[1]:
                raise RuntimeError('maintenance_helper_bootstrap_ambiguous')
            written = os.write(process.stdin.fileno(), data)
            data = data[written:]
        atomic_json(self.root / 'helper.json', dict(state='started', name=name, container=self.container,
                                                   client_pid=process.pid, identity=self.expected))
        return self.connection

    def cleanup(self):
        """Exact owned resource only. Missing create ack remains reconciliation."""
        from deploy.production_preparation import read_manifest
        from deploy.recovery_journal import atomic_json
        if not self.container or self.probe() != self.expected:
            raise RuntimeError('maintenance_helper_cleanup_ambiguous')
        record = read_manifest(self.root / 'helper.json')
        state = json.loads(self.command(['inspect', self.container]))[0]
        if (state['Id'] != self.container or state['Config']['Image'] != self.image
                or state['Config']['Labels'].get('org.mldsafail.maintenance-helper') != record['name']):
            raise RuntimeError('maintenance_helper_ownership_lost')
        atomic_json(self.root / 'cleanup.json', dict(state='stop_intent', container=self.container))
        self.command(['stop', '--time', '1', self.container])
        state = json.loads(self.command(['inspect', self.container]))[0]
        if state['Id'] != self.container or state['State']['Running']:
            raise RuntimeError('maintenance_helper_remains')
        if self.connection:
            self.connection.close()
        atomic_json(self.root / 'cleanup.json', dict(state='terminated', container=self.container,
                                                   client_terminated=True, removed=False))
        return True
