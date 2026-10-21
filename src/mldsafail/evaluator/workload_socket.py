"""Private Linux supervisor protocol. No arbitrary commands or Docker API.

Deployment must supply a reviewed runtime and independent process-death cleanup.
This transport alone is not a native runtime or a deployment entrypoint.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from pathlib import Path
import selectors
import socket
import stat
import struct
import time
import threading

from mldsafail.evaluator.workload import WorkloadBlocked


def decode_request(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_request_key')
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError('nonfinite_request_number')
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid_constant)


class SupervisorProtocol:
    def __init__(self, gate, roles):
        self.gate = gate
        self.mutex = threading.RLock()
        self.roles = copy.deepcopy(roles)
        if not all(isinstance(name, str) and type(value) is dict for name, value in self.roles.items()):
            raise ValueError('invalid_command_roles')

    def dispatch(self, request):
        if type(request) is not dict or set(request) != {'id', 'method', 'argument'}:
            raise WorkloadBlocked('invalid_supervisor_request')
        identifier, method, argument = request['id'], request['method'], request['argument']
        if (not isinstance(identifier, str) or not 1 <= len(identifier) <= 128 or
                type(argument) is not dict or not isinstance(method, str)):
            raise WorkloadBlocked('invalid_supervisor_request')
        if method == 'status':
            if argument:
                raise WorkloadBlocked('unexpected_supervisor_argument')
            with self.gate.mutex:
                return copy.deepcopy(self.gate.state)
        # Monotone generation/sequence IDs make discarded outcomes permanently
        # non-executable. A caller learns the next generation from private status.
        match = re.fullmatch(r'([1-9][0-9]{0,18}):([1-9][0-9]{0,18})', identifier)
        if match is None:
            raise WorkloadBlocked('generation_scoped_request_id_required')
        generation, sequence = map(int, match.groups())
        fields = {
            'acquire': {'kind', 'reference'}, 'bind': {'ownership', 'reference'},
            'launch': {'ownership', 'role'}, 'heartbeat': {'ownership'}, 'result': {'ownership'}, 'environment': {'ownership'}, 'cancel': {'ownership'},
            'abort': {'ownership'}, 'postflight': {'ownership'},
            'commit_intent': {'ownership', 'binding'},
            'acknowledge_commit': {'ownership', 'binding'}, 'resolve_commit': {'ownership', 'binding', 'resolution'},
            'release': {'ownership'}, 'reconcile': {'ownership'}, 'resume': {'ownership'},
        }
        # Validate the entire command before writing durable mutation intent.
        if method not in fields or set(argument) != fields[method]:
            raise WorkloadBlocked('invalid_supervisor_method_or_arguments')
        if method == 'acquire' and (argument['kind'] not in ('evaluation', 'administration') or
                                    type(argument['reference']) is not dict):
            raise WorkloadBlocked('invalid_acquire')
        if method == 'bind' and type(argument['reference']) is not dict:
            raise WorkloadBlocked('invalid_reference')
        if method == 'launch' and (not isinstance(argument['role'], str) or
                                   argument['role'] not in self.roles):
            raise WorkloadBlocked('configured_role_required')
        if method in ('commit_intent', 'acknowledge_commit') and (
                type(argument['binding']) is not dict or not argument['binding']):
            raise WorkloadBlocked('commit_binding_required')
        if method == 'resolve_commit' and (type(argument['binding']) is not dict or type(argument['resolution']) is not dict or argument['resolution'].get('disposition') != 'infrastructure_failed'):
            raise WorkloadBlocked('commit_resolution_invalid')
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        with self.mutex:
            state = self.gate.state
            requests = state.get('requests', {}) if state else {}
            current_generation = state.get('request_generation', 0) if state else 0
            expected_generation = current_generation + (method == 'acquire')
            if generation != expected_generation:
                # Acquire replay is allowed only while its workload is current.
                if not (method == 'acquire' and generation == current_generation and identifier in requests):
                    raise WorkloadBlocked('expired_or_future_request_generation')
            previous = requests.get(identifier)
            if previous:
                if previous['sha256'] != digest:
                    raise WorkloadBlocked('request_id_reused')
                if previous['phase'] != 'complete':
                    raise WorkloadBlocked('request_reconciliation_required')
                return copy.deepcopy(previous['result'])
            if method != 'acquire' and sequence <= state.get('request_sequence', 0):
                raise WorkloadBlocked('expired_request_sequence')
            if method != 'acquire' and (state is None or
                    argument['ownership'] != state['workload_id']):
                raise WorkloadBlocked('current_ownership_required')
            if method == 'result':
                return self.gate.result()
            if method == 'environment':
                self.gate._owned()
                return self.gate.runtime.environment()
            if len(requests) >= 1024:
                raise WorkloadBlocked('request_ledger_full')
            phases = {
                'bind': {'acquired'}, 'launch': {'acquired', 'running'},
                'postflight': {'acquired', 'running', 'cleaned'},
                'commit_intent': {'postflight', 'cleaned'}, 'acknowledge_commit': {'commit_intent'}, 'resolve_commit': {'commit_intent'},
                'release': {'committed'}, 'resume': {'cleaned', 'committed', 'complete'},
                'cancel': {'acquired', 'launch_intent', 'running', 'cleaned'},
                'abort': {'acquired', 'launch_intent', 'running', 'termination_intent', 'cleaned'},
                'reconcile': {'acquired', 'launch_intent', 'running', 'termination_intent', 'cleaned'},
            }
            if method in phases and state['phase'] not in phases[method]:
                raise WorkloadBlocked('supervisor_lifecycle_invalid')
            if (method in ('acknowledge_commit', 'resolve_commit') and
                    argument['binding'] != state.get('database_commit')):
                raise WorkloadBlocked('commit_acknowledgement_invalid')
            if method in ('bind', 'launch', 'postflight', 'release') and state['paused']:
                raise WorkloadBlocked('scheduling_paused')
            if method == 'acquire':
                result = self.gate.acquire(argument['kind'], argument['reference'])
                requests = self.gate.state.setdefault('requests', {})
            else:
                self.gate.state['request_sequence'] = sequence
                requests[identifier] = dict(sha256=digest, phase='intent')
                self.gate._write()
                if method == 'bind':
                    result = self.gate.bind(argument['reference'])
                elif method == 'launch':
                    result = self.gate.launch(copy.deepcopy(self.roles[argument['role']]))
                elif method == 'heartbeat':
                    result = self.gate.heartbeat()
                elif method == 'cancel':
                    result = self.gate.reconcile()
                elif method == 'abort':
                    self.gate.pause('dispatcher_abort')
                    result = self.gate.reconcile()
                elif method == 'resolve_commit':
                    result = self.gate.resolve_commit(argument['binding'], argument['resolution'])
                elif method in ('commit_intent', 'acknowledge_commit'):
                    result = getattr(self.gate, method)(argument['binding'])
                else:
                    result = getattr(self.gate, method)()
            requests[identifier] = dict(sha256=digest, phase='complete', result=result)
            self.gate.state['request_sequence'] = sequence
            # Keep a small replay window; the durable high-water mark rejects
            # older IDs. Ambiguous intents are never evicted.
            completed = [key for key, entry in requests.items() if entry['phase'] == 'complete']
            for key in completed[:-64]:
                del requests[key]
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
                            request = decode_request(state['data'])
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
