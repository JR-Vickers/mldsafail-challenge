"""Native experimental private Unix-socket supervisor (no production dispatch).

A trusted operator fixes all paths, image and epoch on startup. Clients can select
only named reviewed fixtures; no Docker arguments, arbitrary source paths or
private instance state can be submitted. Requests execute serially. A durable
unfinished ownership journal prevents subsequent work after supervisor death.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import socket
import struct
import signal
import time
import uuid

from research.cpu_measurement.harness import run
from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v050.verify import verify_candidate

MAX_REQUEST = 4096
FIXTURES = frozenset({'empty', 'child', 'grandchild', 'clock_tampering', 'forged_timing',
                      'early_exit', 'malformed', 'output_flood', 'hang', 'descendant_hang', 'closed_stream_hang'})


def dispatch(args, fixture):
    """Keep bounded private dispatch evidence even when the client disconnects."""
    if not isinstance(fixture, str) or fixture not in FIXTURES:
        raise ValueError('Only approved fixed fixture names accepted')
    from research.cpu_measurement.ownership import publish
    receipt = args.socket.parent / 'last-dispatch.json'
    record = dict(schema='mldsafail.cpu-supervisor-dispatch.v1',
                  request_id=uuid.uuid4().hex, fixture=fixture, state='intent',
                  started_monotonic=time.monotonic())
    publish(receipt, record)
    try:
        instance = generate_mlwe('small', 0, 1).public
        # The owner-kill probe must reach proven input delivery before injection.
        # Ordinary short runaway fixtures keep their existing two-second limit.
        owner_kill = fixture == 'hang' and getattr(args, 'owner_kill_probe', False)
        result = run(args.image, args.parent, args.cgroup_parent,
                     Path(__file__).parent / 'fixtures' / fixture,
                     instance.to_dict(), lambda public, candidate: verify_candidate(instance, candidate)['verified'],
                     timeout=60 if owner_kill else (2 if fixture in {'hang', 'descendant_hang', 'closed_stream_hang'} else 60),
                     ownership_directory=args.ownership_directory,
                     evidence_metadata={'fixture': fixture}, epoch=args.epoch)
    except BaseException as original:
        record.update(state='failed', error_type=type(original).__name__,
                      error=repr(original)[:4096], finished_monotonic=time.monotonic())
        try:
            publish(receipt, record)
        except BaseException as publication:
            original.add_note('Private dispatch failure evidence publication failed: '+repr(publication))
        raise
    record.update(state='complete', generation=result['generation'],
                  finished_monotonic=time.monotonic())
    try:
        publish(receipt, record)
    except BaseException as original:
        record.update(state='failed', error_type=type(original).__name__,
                      error=repr(original)[:4096])
        try:
            publish(receipt, record)
        except BaseException as publication:
            original.add_note('Negative dispatch publication failed: '+repr(publication))
        raise
    return result


def read_request(connection, request_seconds=1):
    deadline = time.monotonic() + request_seconds
    data = bytearray()
    while b'\n' not in data:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Absolute request deadline exceeded')
        connection.settimeout(remaining)
        chunk = connection.recv(min(1024, MAX_REQUEST + 1 - len(data)))
        if not chunk:
            raise ValueError('Incomplete request')
        data.extend(chunk)
        if len(data) > MAX_REQUEST:
            raise ValueError('Request limit exceeded')
    if data.count(b'\n') != 1 or not data.endswith(b'\n'):
        raise ValueError('Exactly one request required')
    request = json.loads(data)
    if isinstance(request, dict) and set(request)=={'inspect_dispatch'} and request['inspect_dispatch'] is True:
        return request
    if set(request) != {'fixture'} or request['fixture'] not in FIXTURES:
        raise ValueError('Only approved fixed fixture names accepted')
    return request


def serve(args):
    directory = args.socket.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_mode & 0o077:
        raise RuntimeError('Socket directory must be private')
    # Never unlink an unknown/live socket. Explicit operator reconciliation is
    # required after abnormal shutdown, independent of generation cleanup.
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    socket_identity = None
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Supervisor shutdown requested')
    previous = {number: signal.signal(number, interrupted) for number in (signal.SIGTERM, signal.SIGINT)}
    last_dispatch = None
    try:
        server.bind(str(args.socket))
        os.chmod(args.socket, 0o600)
        socket_identity = args.socket.stat().st_ino
        server.listen(1)
        while True:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(1)
                request = None
                try:
                    _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid != os.getuid():
                        raise PermissionError('Peer is not the trusted supervisor owner')
                    request = read_request(connection)
                    if 'inspect_dispatch' in request:
                        # Serial dispatch means this response can only follow
                        # completed publication, including any negative retry.
                        response = {'ok': True, 'dispatch': last_dispatch}
                    else:
                        fixture = request['fixture']
                        last_dispatch = dict(state='intent', fixture=fixture)
                        result = dispatch(args, fixture)
                        last_dispatch = dict(state='complete', fixture=fixture,
                                             generation=result['generation'])
                        response = {'ok': True, 'result': {key: result[key] for key in
                                    ('status', 'authoritative_cpu_usec', 'wall_seconds', 'generation')}}
                except Exception as error:
                    if isinstance(request, dict) and 'fixture' in request:
                        last_dispatch = dict(state='failed', fixture=request['fixture'],
                                             error_type=type(error).__name__)
                    response = {'ok': False, 'error_type': type(error).__name__}
                try:
                    connection.sendall(json.dumps(response, allow_nan=False).encode() + b'\n')
                except (OSError, TimeoutError):
                    pass  # Durable evidence survives a disconnected response.
    finally:
        server.close()
        for number, handler in previous.items():
            signal.signal(number, handler)
        if socket_identity is not None and args.socket.exists() and args.socket.stat().st_ino == socket_identity:
            args.socket.unlink()
        # SIGKILL leaves the socket and durable generation for reconciliation.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', type=Path, required=True)
    parser.add_argument('--ownership-directory', type=Path, required=True)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--cgroup-parent', required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--epoch', required=True)
    parser.add_argument('--owner-kill-probe', action='store_true')
    serve(parser.parse_args())


if __name__ == '__main__':
    main()
