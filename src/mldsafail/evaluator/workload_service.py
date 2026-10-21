"""Private supervisor/client and cleanup-only commands; no public listener.

An installed reviewed runtime helper must enforce native cgroup, filesystem and
Docker controls. This module never substitutes a permissive local adapter.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import signal
import socket
import stat
import struct
import threading
import time

from mldsafail.evaluator.runtime_io import RuntimeTransport
from mldsafail.evaluator.workload import HostGate, WorkloadBlocked, WorkloadSession
from mldsafail.evaluator.workload_socket import PrivateSocket, SupervisorProtocol


def read_configuration(path):
    path = Path(path).absolute()
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise WorkloadBlocked('configuration_symlink')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor) as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                info.st_nlink != 1 or info.st_mode & 0o077 or info.st_size > 65536):
            raise WorkloadBlocked('private_configuration_required')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise WorkloadBlocked('duplicate_configuration_key')
                result[key] = value
            return result
        config = json.loads(stream.read(65537), object_pairs_hook=unique)
    if (type(config) is not dict or set(config) != {'root', 'socket', 'helper', 'roles'} or
            type(config['roles']) is not dict or not config['roles'] or
            any(not isinstance(name, str) or type(role) is not dict
                for name, role in config['roles'].items()) or
            any(not isinstance(config[key], str) or not Path(config[key]).is_absolute()
                for key in ('root', 'socket')) or
            Path(config['socket']).parent != Path(config['root']) or
            type(config['helper']) is not list or not config['helper'] or
            any(not isinstance(part, str) or not part or '\0' in part for part in config['helper']) or
            not Path(config['helper'][0]).is_absolute()):
        raise WorkloadBlocked('invalid_supervisor_configuration')
    return config


class HelperRuntime:
    """Separate bounded helper channels for monitor and control threads.

    A timed-out helper cannot delay sampling or masquerade as successful cleanup.
    Every process handle remains attached to its channel until reaped.
    """
    def __init__(self, command):
        self.command = tuple(command)
        self.transports = {name: RuntimeTransport(self.command) for name in ('monitor', 'control')}

    def call(self, method, argument):
        channel = 'monitor' if threading.current_thread().name == 'heavy-workload-monitor' else 'control'
        return self.transports[channel].call(method, argument)

    def identity(self): return self.call('identity', {})
    def preflight(self, policy): return self.call('preflight', {'policy': asdict(policy)})
    def sample(self, state): return self.call('sample', {'state': state})
    def launch(self, state, specification):
        return self.call('launch', {'state': state, 'specification': specification})
    def inspect(self, state, birth): return self.call('inspect', {'state': state, 'birth': birth})
    def terminate(self, state): return self.call('terminate', {'state': state})
    def stopped(self, state): return self.call('stopped', {'state': state})


def notify(message):
    address = os.environ.get('NOTIFY_SOCKET')
    if not address:
        return
    if address.startswith('@'):
        address = '\0' + address[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
        client.settimeout(.2)
        client.connect(address)
        client.sendall(message.encode())


def cleanup(gate):
    """Only inspected termination; never clear pause or authorize new work."""
    if gate.state is None:
        return
    gate._owned()
    gate.pause('cleanup_only')
    if gate.state['phase'] in ('postflight', 'commit_intent', 'committed', 'complete'):
        # Preserve transaction ambiguity and its lifecycle. These phases already
        # passed cleanup; any new resource indicates failed identity isolation.
        if gate.runtime.stopped(gate.state) is not True:
            raise WorkloadBlocked('postflight_resources_reappeared')
        return
    gate.reconcile()


def serve(gate, path, roles, stop):
    protocol = SupervisorProtocol(gate, roles)
    session = None
    if gate.state is not None:
        # A daemon restart never resumes a computational phase or drops evidence.
        gate.pause('supervisor_restart')
    try:
        with PrivateSocket(path, protocol) as server:
            notify('READY=1\nSTATUS=Scheduling requires reconciled ownership')
            while not stop.is_set():
                if gate.state and gate.state['phase'] != 'complete' and not gate.state['paused']:
                    if session is None:
                        session = WorkloadSession(gate).start()
                elif session is not None:
                    session.finish_monitor()
                    session = None
                server.poll(.05)
                notify('WATCHDOG=1')
    finally:
        try:
            if session is not None:
                session.finish_monitor()
        finally:
            cleanup(gate)


def call_private(path, request, *, timeout=.8):
    """A timeout is ambiguous; retry the identical persisted request ID."""
    if not 0 < timeout <= .8:
        raise ValueError('invalid_client_timeout')
    path = Path(path).absolute()
    if not hasattr(socket, 'SO_PEERCRED'):
        raise WorkloadBlocked('linux_peer_credentials_required')
    for parent in (path.parent, *path.parent.parents):
        if parent.is_symlink():
            raise WorkloadBlocked('private_socket_directory_required')
    parent = path.parent.stat()
    info = path.lstat()
    if (parent.st_uid != os.getuid() or parent.st_mode & 0o077 or
            not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise WorkloadBlocked('private_socket_required')
    wire = json.dumps(request, allow_nan=False).encode() + b'\n'
    if len(wire) > 65536:
        raise WorkloadBlocked('supervisor_request_limit')
    deadline = time.monotonic() + timeout
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(path))
        _, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != os.getuid():
            raise WorkloadBlocked('supervisor_peer_identity_changed')
        client.sendall(wire)
        result = bytearray()
        while b'\n' not in result:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WorkloadBlocked('supervisor_response_deadline')
            client.settimeout(remaining)
            chunk = client.recv(min(4096, 65537 - len(result)))
            if not chunk:
                raise WorkloadBlocked('supervisor_response_missing')
            result.extend(chunk)
            if len(result) > 65536:
                raise WorkloadBlocked('supervisor_response_limit')
    response = json.loads(result)
    if type(response) is not dict or set(response) != {'result'}:
        raise WorkloadBlocked('supervisor_request_blocked')
    return response['result']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('serve', 'cleanup', 'client'))
    parser.add_argument('--configuration', type=Path, required=True)
    parser.add_argument('--request', type=Path, help='Persisted exact JSON request for client action')
    args = parser.parse_args(argv)
    config = read_configuration(args.configuration)
    if args.action == 'client':
        if args.request is None:
            parser.error('client requires --request')
        print(json.dumps({'result': call_private(config['socket'], json.loads(args.request.read_bytes()))}))
        return 0
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    runtime = HelperRuntime(config['helper'])
    with HostGate(config['root'], runtime).locked() as gate:
        if args.action == 'cleanup':
            cleanup(gate)
        else:
            serve(gate, config['socket'], config['roles'], stop)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
