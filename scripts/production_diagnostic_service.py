"""Disposable service entrypoints; never installed into production images."""
import json
import os
from pathlib import Path
import sys


def append(path, row):
    """Atomic bounded records; no stdout/credential material is accepted."""
    raw = (json.dumps(row, sort_keys=True, allow_nan=False) + '\n').encode()
    if len(raw) > 8192:
        raise ValueError('Diagnostic record exceeds cap')
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    try:
        if os.write(fd, raw) != len(raw):
            raise OSError('Incomplete diagnostic publication')
        os.fsync(fd)
    finally:
        os.close(fd)


class StatusSocket:
    """Private read-only IPC exposes the worker's authoritative failure flag."""
    def __init__(self, app, root):
        import socket, threading
        self.app = app
        self.stop = threading.Event()
        self.socket = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.socket.bind(str(Path(root)/(str(os.getpid())+'.sock')))
        os.chmod(Path(root)/(str(os.getpid())+'.sock'),0o600)
        self.socket.listen(2)
        self.socket.settimeout(.2)
        self.thread = threading.Thread(target=self.serve,daemon=True)
        self.thread.start()

    def serve(self):
        import socket
        while not self.stop.is_set():
            try:
                connection,_ = self.socket.accept()
                with connection:
                    connection.settimeout(1)
                    connection.sendall(json.dumps(dict(failed=self.app.extensions.get('diagnostic_evidence_failed',False))).encode())
            except socket.timeout:
                continue
            except OSError:
                if not self.stop.is_set():
                    self.app.extensions['diagnostic_evidence_failed'] = True
                return

    def close(self):
        self.stop.set()
        self.socket.close()
        self.thread.join(timeout=1)


def post_worker_init(worker):
    """Gunicorn config hook; settings and application factory stay unchanged."""
    from scripts.production_diagnostic_instrumentation import install
    root = Path('/tmp/diagnostic-timings')
    root.mkdir(mode=0o700, exist_ok=True)
    def fail(_reason):
        (root / 'FAILED').touch(mode=0o600)
    install(worker.wsgi, lambda row: append(root / (str(os.getpid()) + '.jsonl'), row), fail)
    worker.wsgi.extensions['diagnostic_status_socket'] = StatusSocket(worker.wsgi,root)


def fixture_operation(operation, path):
    """Private stdin/stdout canonical fixture transfer through an owned exec."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from scripts import production_diagnostic_fixture as fixture
    engine = create_engine(os.environ['MLDSAFAIL_DATABASE_URL'])
    with Session(engine) as session:
        if operation == 'create':
            encoded, metadata = fixture.create(session)
            # Publication is the caller's responsibility; no implicit recreation.
            print(json.dumps(dict(encoded=encoded.decode(), metadata=metadata)))
        elif operation == 'restore':
            packet = json.load(sys.stdin)
            from datetime import datetime
            token = fixture.restore(session, packet['encoded'].encode(), packet['metadata'],
                required_until=datetime.fromisoformat(packet['required_until']))
            print(json.dumps(dict(token=token, identity_sha256=packet['metadata']['identity_sha256'])))
        else:
            raise ValueError('Explicit fixture operation required')
    engine.dispose()


def timing_snapshot(root=Path('/tmp/diagnostic-timings')):
    import socket
    root = Path(root)
    if not root.is_dir() or (root / 'FAILED').exists():
        raise RuntimeError('Instrumentation publication failed or absent')
    sockets = list(root.glob('*.sock'))
    if len(sockets) != 2:
        raise RuntimeError('Both configured Gunicorn worker flags required')
    for path in sockets:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as channel:
            channel.settimeout(1)
            channel.connect(str(path))
            value = json.loads(channel.recv(1024))
            if value != {'failed':False}:
                raise RuntimeError('Worker instrumentation publication failed')
    rows = []
    for path in sorted(root.glob('*.jsonl')):
        if path.stat().st_size > 8 * 1024**2:
            raise RuntimeError('Instrumentation evidence cap exceeded')
        rows.extend(json.loads(line) for line in path.read_text().splitlines())
    print(json.dumps(dict(failed=False, rows=rows)))


def monitor():
    from deploy import host_checks
    # append() failures propagate and invalidate the monitor invocation.
    path = Path(os.environ['MLDSAFAIL_DIAGNOSTIC_MONITOR_EVIDENCE'])
    host_checks.main(diagnostic=lambda row: append(path, row))


if __name__ == '__main__':
    if sys.argv[1] == 'monitor':
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        monitor()
    elif sys.argv[1] == 'timings':
        timing_snapshot()
    else:
        fixture_operation(sys.argv[1], None)
