"""Private Linux supervisor protocol. No arbitrary commands or Docker API.

Deployment must supply a reviewed runtime and independent process-death cleanup.
This transport alone is not a native runtime or a deployment entrypoint.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import selectors
import socket
import stat
import struct
import time

from mldsafail.evaluator.workload import WorkloadBlocked


class SupervisorProtocol:
    def __init__(self, gate, roles):
        self.gate = gate
        self.roles = copy.deepcopy(roles)
        if not all(isinstance(name, str) and type(value) is dict for name, value in self.roles.items()):
            raise ValueError('invalid_command_roles')

    def dispatch(self, request):
        if type(request) is not dict or set(request) != {'id', 'method', 'argument'}:
            raise WorkloadBlocked('invalid_supervisor_request')
        identifier, method, argument = request['id'], request['method'], request['argument']
        if (not isinstance(identifier, str) or not 1 <= len(identifier) <= 128 or
                type(argument) is not dict):
            raise WorkloadBlocked('invalid_supervisor_request')
        if method == 'status':
            return copy.deepcopy(self.gate.state)
        if method not in {'acquire', 'bind', 'launch', 'complete', 'reconcile', 'resume'}:
            raise WorkloadBlocked('invalid_supervisor_method')
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        with self.gate.mutex:
            state = self.gate.state
            requests = state.get('requests', {}) if state else {}
            previous = requests.get(identifier)
            if previous:
                if previous['sha256'] != digest:
                    raise WorkloadBlocked('request_id_reused')
                if previous['phase'] != 'complete':
                    raise WorkloadBlocked('request_reconciliation_required')
                return copy.deepcopy(previous['result'])
            if len(requests) >= 1024:
                raise WorkloadBlocked('request_ledger_full')
            if method == 'acquire':
                if set(argument) != {'kind', 'reference'}:
                    raise WorkloadBlocked('invalid_acquire')
                # acquire writes its ownership intent before any launch. A lost
                # acknowledgement still blocks replacement acquisition.
                result = self.gate.acquire(argument['kind'], argument['reference'])
                requests = self.gate.state.setdefault('requests', {})
            else:
                if state is None:
                    raise WorkloadBlocked('host_ownership_required')
                requests = state.setdefault('requests', {})
                requests[identifier] = dict(sha256=digest, phase='intent')
                self.gate._write()
                if method == 'bind':
                    result = self.gate.bind(argument)
                elif method == 'launch':
                    if set(argument) != {'role'} or argument['role'] not in self.roles:
                        raise WorkloadBlocked('configured_role_required')
                    result = self.gate.launch(copy.deepcopy(self.roles[argument['role']]))
                else:
                    if argument:
                        raise WorkloadBlocked('unexpected_supervisor_argument')
                    result = getattr(self.gate, method)()
            requests[identifier] = dict(sha256=digest, phase='complete', result=result)
            self.gate._write()
            return result


class PrivateSocket:
    """One nonblocking event loop; slow clients cannot accumulate reader threads."""
    def __init__(self, path, protocol, *, max_clients=8):
        self.path, self.protocol = Path(path), protocol
        self.max_clients = max_clients
        self.listener = None
        self.clients = {}
        self.selector = selectors.DefaultSelector()

    def __enter__(self):
        if not hasattr(socket, 'SO_PEERCRED'):
            raise WorkloadBlocked('linux_peer_credentials_required')
        parent = self.path.parent.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or
                parent.st_mode & 0o077 or any(p.is_symlink() for p in (self.path.parent, *self.path.parents))):
            raise WorkloadBlocked('private_socket_directory_required')
        # Refuse stale sockets: recovery must independently establish the old
        # supervisor's death rather than unlinking a possibly live endpoint.
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.listener.bind(str(self.path))
            os.chmod(self.path, 0o600)
            self.birth = self.path.lstat()
            self.listener.listen(self.max_clients)
            self.listener.setblocking(False)
            self.selector.register(self.listener, selectors.EVENT_READ)
        except BaseException:
            self.listener.close()
            raise
        return self

    def close_client(self, client):
        self.selector.unregister(client)
        self.clients.pop(client)
        client.close()

    def poll(self, timeout=.05):
        for key, _ in self.selector.select(min(timeout, .25)):
            client = key.fileobj
            if client is self.listener:
                peer, _ = self.listener.accept()
                _, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if uid != os.getuid() or len(self.clients) >= self.max_clients:
                    peer.close()
                    continue
                peer.setblocking(False)
                self.clients[peer] = dict(deadline=time.monotonic() + .8, data=bytearray(), output=None)
                self.selector.register(peer, selectors.EVENT_READ)
                continue
            state = self.clients[client]
            try:
                if state['output'] is not None:
                    count = client.send(state['output'])
                    del state['output'][:count]
                    if not state['output']: self.close_client(client)
                else:
                    data = client.recv(4096)
                    state['data'].extend(data)
                    if not data or len(state['data']) > 65536:
                        self.close_client(client)
                    elif b'\n' in state['data']:
                        try:
                            request = json.loads(state['data'])
                            result = self.protocol.dispatch(request)
                            response = {'result': result}
                        except (ValueError, WorkloadBlocked, KeyError, TypeError):
                            response = {'error': 'supervisor_request_blocked'}
                        state['output'] = bytearray(json.dumps(response).encode() + b'\n')
                        self.selector.modify(client, selectors.EVENT_WRITE)
            except (ConnectionError, OSError):
                self.close_client(client)
        for client, state in list(self.clients.items()):
            if time.monotonic() >= state['deadline']:
                self.close_client(client)

    def __exit__(self, *exc):
        for client in list(self.clients): self.close_client(client)
        self.selector.close()
        self.listener.close()
        info = self.path.lstat()
        if (info.st_dev, info.st_ino) == (self.birth.st_dev, self.birth.st_ino):
            self.path.unlink()
