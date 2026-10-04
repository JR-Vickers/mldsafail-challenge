"""Private-socket disconnection and SIGKILL native lifecycle probes.

Requires a separately delegated empty parent and reviewed immutable image. No
results are scored. Complete/failed generation evidence is retained by supervisor.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from research.cpu_measurement.ownership import canonical_directory, publish
from research.cpu_measurement.reconcile import reconcile
from research.cpu_measurement.audit import audit_journal


def wait_for(predicate, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.05)
    raise TimeoutError('Native lifecycle transition deadline exceeded')


def lifecycle(args, output):
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    state = canonical_directory(args.parent)
    socket_path = output / 'supervisor.sock'
    previous = json.loads((state / 'journal.json').read_text())['generation']
    server = subprocess.Popen([sys.executable, '-m', 'research.cpu_measurement.supervisor',
                               '--socket', str(socket_path), '--ownership-directory', str(state),
                               '--parent', str(args.parent), '--cgroup-parent', args.cgroup_parent,
                               '--image', args.image, '--epoch', 'isolated-native-lifecycle'],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    results = []
    connection = None
    socket_identity = None
    try:
        wait_for(lambda: socket_path.exists() and server.poll() is None)
        socket_identity = socket_path.stat().st_ino
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(30)
        connection.connect(str(socket_path))
        connection.sendall(b'{"fixture":"child"}\n')
        connection.close()
        connection = None
        def disconnected_completed():
            record = json.loads((state / 'journal.json').read_text())
            return record if record['generation'] != previous and record['state'] == 'complete' else None
        completed = wait_for(disconnected_completed)
        decision = audit_journal(state, completed['generation'])
        results.append(dict(fault='connection_loss', passed=decision['status'] == 'no_answer', generation=completed['generation']))
        # A second request proves response loss did not poison dispatch. Use the
        # hanging reviewed fixture so SIGKILL occurs after proven input delivery.
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(30)
        connection.connect(str(socket_path))
        connection.sendall(b'{"fixture":"hang"}\n')
        def active_input():
            record = json.loads((state / 'journal.json').read_text())
            return record if record['generation'] != completed['generation'] and any(
                row['operation'] == 'input_delivered' for row in record['mutations']) else None
        interrupted = wait_for(active_input)
        os.kill(server.pid, signal.SIGKILL)
        server.wait(timeout=10)
        # New work must remain fenced after kernel releases flock on owner death.
        from research.cpu_measurement.ownership import Ownership
        fenced = False
        try:
            with Ownership(state, args.parent):
                pass
        except RuntimeError as error:
            fenced = 'reconciliation' in str(error)
        cleanup = reconcile(state, args.parent)
        results.append(dict(fault='SIGKILL', passed=fenced and cleanup['cleanup_complete'],
                            generation=interrupted['generation'], cleanup=cleanup))
    finally:
        errors = []
        try:
            if connection is not None:
                connection.close()
        except Exception as error:
            errors.append(dict(step='socket_connection_close', error=repr(error)))
        try:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=40)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=10)
        except Exception as error:
            errors.append(dict(step='supervisor_termination', error=repr(error)))
        cleanup = {'cleanup_complete': False}
        try:
            cleanup = reconcile(state, args.parent)
            if not cleanup['cleanup_complete']:
                errors.append(dict(step='generation_reconciliation', error='Cleanup remains incomplete'))
        except Exception as error:
            errors.append(dict(step='generation_reconciliation', error=repr(error)))
        try:
            if socket_path.exists():
                if socket_identity is None or socket_path.stat().st_ino != socket_identity:
                    raise RuntimeError('Owned socket identity changed; removal prohibited')
                socket_path.unlink()
        except Exception as error:
            errors.append(dict(step='owned_socket_removal', error=repr(error)))
        cleanup['independent_cleanup_errors'] = errors
        cleanup['cleanup_complete'] = cleanup['cleanup_complete'] and not errors
        publish(output / 'cleanup.json', cleanup)
        if not cleanup['cleanup_complete']:
            raise RuntimeError('Lifecycle cleanup remains incomplete; new work prohibited')
    for row in results:
        publish(output / (row['fault'] + '.json'), row)
    return results
