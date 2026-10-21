"""Durable physical-host execution gate, independent of database leases.

The runtime adapter must provide bounded, inspected cgroup/container operations.
No adapter is implicitly trusted or selected; this module grants no Docker access.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import threading
from functools import wraps
import uuid
import time


class WorkloadBlocked(RuntimeError):
    pass


class ProtectionAbort(WorkloadBlocked):
    pass


@dataclass(frozen=True)
class ResourcePolicy:
    version: str = 'mldsafail.resource-policy.v1'
    reserve: int = 1024**3
    available_floor: int = 256 * 1024**2
    disk_floor: int = 5 * 1024**3
    cpu_max: str = '100000 100000'
    pids_max: int = 448
    swap_max: int = 0
    log_max: int = 128 * 1024**2
    generation_max: int = 1024**3
    interval: float = .25

    @property
    def sha256(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    def ceiling(self, physical, ancestor_allowances):
        if physical <= self.reserve or not ancestor_allowances:
            raise WorkloadBlocked('effective_memory_unavailable')
        limits = [physical - self.reserve, *ancestor_allowances]
        if any(type(value) is not int or value <= 0 for value in limits):
            raise WorkloadBlocked('invalid_effective_memory')
        return min(limits)

    def violation(self, sample, ceiling):
        # Missing/malformed observations are monitoring loss, never healthy defaults.
        try:
            if sample['available'] < self.available_floor: return 'host_memory_floor'
            if sample['memory'] * 100 > ceiling * 95: return 'operation_memory_ceiling'
            if sample['oom_events']: return 'operation_oom'
            if sample['swap']: return 'operation_swap'
            if sample['disk_free'] < self.disk_floor: return 'disk_floor'
            if sample['logs'] > self.log_max: return 'log_budget'
            if sample['generation'] > self.generation_max: return 'generation_budget'
            if sample['identity_valid'] is not True: return 'ownership_lost'
            if any(type(sample[k]) is not int or sample[k] < 0 for k in
                   ('available', 'memory', 'oom_events', 'swap', 'disk_free', 'logs', 'generation')):
                return 'monitor_invalid'
        except (KeyError, TypeError, ValueError):
            return 'monitor_invalid'
        return None


def serialized(function):
    @wraps(function)
    def call(self, *args, **kwargs):
        with self.mutex:
            return function(self, *args, **kwargs)
    return call


class HostGate:
    """Keep the lock inode permanent; an interrupted journal blocks new owners.

    All users of one physical host must share this root, including users of
    distinct databases. Identity is read afresh by the runtime, including boot ID
    and Docker daemon identity. Cleanup may never infer death from lease expiry.
    """
    def __init__(self, root, runtime, policy=None):
        self.root, self.runtime = Path(root).absolute(), runtime
        self.pid = os.getpid()
        self.generation = uuid.uuid4().hex
        self.policy = policy or ResourcePolicy()
        self.fd = None
        self.mutex = threading.RLock()
        self.state = None
        self.inflight_launches = 0
        self.path = self.root / 'workload.json'

    def _validate(self, state):
        """Treat persisted state as untrusted, including after a clean exit."""
        phases = {'acquired', 'launch_intent', 'running', 'termination_intent', 'cleaned',
                  'postflight', 'commit_intent', 'committed', 'complete'}
        try:
            valid = (
                type(state) is dict
                and state['schema'] == 'mldsafail.workload.v1'
                and state['policy_sha256'] == self.policy.sha256
                and isinstance(state['workload_id'], str)
                and len(state['workload_id']) == 32
                and all(c in '0123456789abcdef' for c in state['workload_id'])
                and state['kind'] in ('evaluation', 'administration')
                and type(state['reference']) is dict
                and type(state['identity']) is dict
                and all(isinstance(state['identity'][k], str) and state['identity'][k]
                        for k in ('boot_id', 'daemon_id'))
                and type(state['ceiling']) is int and state['ceiling'] > 0
                and state['phase'] in phases
                and type(state['paused']) is bool
                and type(state['resources']) is list
                and all(type(resource) is dict and resource for resource in state['resources'])
                and (not state['paused'] or
                     isinstance(state.get('reason'), str) and bool(state['reason']))
                and (state['phase'] != 'acquired' or not state['resources'])
                and (state['phase'] != 'running' or bool(state['resources']))
                and (state['phase'] not in ('commit_intent', 'committed') or
                     type(state.get('database_commit')) is dict and bool(state['database_commit']))
            )
        except (KeyError, TypeError):
            valid = False
        if not valid:
            raise WorkloadBlocked('invalid_workload_journal')
        if 'supervisor_generation' in state and not re.fullmatch('[a-f0-9]{32}', str(state['supervisor_generation'])):
            raise WorkloadBlocked('invalid_supervisor_generation')
        requests = state.get('requests', {})
        generation = state.get('request_generation', 0)
        sequence = state.get('request_sequence', 0)
        completed = state.get('completed_workloads', [])
        if (type(generation) is not int or generation < 0 or
                type(sequence) is not int or sequence < 0 or
                type(completed) is not list or len(completed) > 16 or
                any(type(record) is not dict or
                    type(record.get('generation')) is not int or
                    not 0 <= record['generation'] < generation or
                    not isinstance(record.get('workload_id'), str)
                    for record in completed)):
            raise WorkloadBlocked('invalid_request_generation')
        if [record['generation'] for record in completed] != sorted(
                {record['generation'] for record in completed}):
            raise WorkloadBlocked('invalid_completed_workload_order')
        if type(requests) is not dict or len(requests) > 1024:
            raise WorkloadBlocked('invalid_request_ledger')
        for identifier, entry in requests.items():
            if (not isinstance(identifier, str) or not 1 <= len(identifier) <= 128
                    or type(entry) is not dict
                    or entry.get('phase') not in ('intent', 'complete')
                    or not isinstance(entry.get('sha256'), str)
                    or len(entry['sha256']) != 64
                    or any(c not in '0123456789abcdef' for c in entry['sha256'])
                    or (entry['phase'] == 'complete' and 'result' not in entry)):
                raise WorkloadBlocked('invalid_request_ledger')
            if generation:
                match = re.fullmatch(r'([1-9][0-9]{0,18}):([1-9][0-9]{0,18})', identifier)
                if match is None:
                    raise WorkloadBlocked('invalid_request_generation')
                request_generation, request_sequence = map(int, match.groups())
                if (request_generation > generation or
                        request_generation == generation and request_sequence > sequence):
                    raise WorkloadBlocked('invalid_request_generation')

    @serialized
    def _write(self):
        self._validate(self.state)
        temporary = self.root / (uuid.uuid4().hex + '.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(self.state, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)
        directory = os.open(self.root, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)

    @contextmanager
    def locked(self):
        if os.getpid() != self.pid: raise WorkloadBlocked('forked_host_gate')
        if self.fd is not None: raise WorkloadBlocked('nested_host_gate')
        if any(path.is_symlink() for path in (self.root, *self.root.parents)):
            raise WorkloadBlocked('symlink_host_gate')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise WorkloadBlocked('private_gate_required')
        self.fd = os.open(self.root / 'host.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(self.fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise WorkloadBlocked('unsafe_host_lock')
            try: fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error: raise WorkloadBlocked('host_busy') from error
            self.state = None
            if self.path.exists() or self.path.is_symlink():
                info = self.path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077:
                    raise WorkloadBlocked('unsafe_workload_journal')
                if info.st_size > 1024 * 1024:
                    raise WorkloadBlocked('oversized_workload_journal')
                def unique(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result: raise ValueError('duplicate_journal_key')
                        result[key] = value
                    return result
                descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor) as stream:
                    opened = os.fstat(stream.fileno())
                    if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                        raise WorkloadBlocked('workload_journal_replaced')
                    try: self.state = json.loads(stream.read(1024 * 1024 + 1), object_pairs_hook=unique)
                    except (ValueError, UnicodeError) as error:
                        raise WorkloadBlocked('invalid_workload_journal') from error
                self._validate(self.state)
            yield self
        finally:
            os.close(self.fd)
            self.fd = None

    def _owned(self):
        if os.getpid() != self.pid: raise WorkloadBlocked('forked_host_gate')
        if self.fd is None or not self.state: raise WorkloadBlocked('host_ownership_required')
        if self.runtime.identity() != self.state['identity']:
            self.pause('runtime_identity_changed')
            raise ProtectionAbort('runtime_identity_changed')

    @serialized
    def acquire(self, kind, reference):
        if self.fd is None: raise WorkloadBlocked('host_lock_required')
        if self.inflight_launches: raise WorkloadBlocked('creator_response_pending')
        if self.state and (self.state['phase'] != 'complete' or self.state['paused']):
            raise WorkloadBlocked('cleanup_or_resume_required')
        if kind not in ('evaluation', 'administration'): raise ValueError('invalid_workload_kind')
        if type(reference) is not dict: raise ValueError('invalid_reference')
        identity = self.runtime.identity()
        if not identity.get('boot_id') or not identity.get('daemon_id'):
            raise WorkloadBlocked('runtime_identity_required')
        ceiling = self.runtime.preflight(self.policy)
        if type(ceiling) is not int or ceiling <= 0:
            raise WorkloadBlocked('resource_deferral')
        previous = self.state
        requests = {key: value for key, value in previous.get('requests', {}).items()
                    if value['phase'] != 'complete'} if previous else {}
        completed = list(previous.get('completed_workloads', [])) if previous else []
        if previous:
            completed.append(dict(generation=previous.get('request_generation', 0),
                                  workload_id=previous['workload_id'],
                                  reference=previous['reference'],
                                  database_commit=previous.get('database_commit')))
        self.state = dict(requests=requests, schema='mldsafail.workload.v1', workload_id=uuid.uuid4().hex,
                          request_generation=previous.get('request_generation', 0) + 1 if previous else 1,
                          request_sequence=0, completed_workloads=completed[-16:],
                          identity=identity, supervisor_generation=self.generation, kind=kind, reference=reference,
                          policy_sha256=self.policy.sha256, ceiling=ceiling,
                          phase='acquired', paused=False, resources=[])
        if getattr(self.runtime, 'requires_heartbeat', False):
            self.state['heartbeat_deadline'] = time.time() + 5
        self._write()
        if hasattr(self.runtime, 'prepare'):
            try:
                if self.runtime.prepare(copy.deepcopy(self.state)) is not True:
                    raise WorkloadBlocked('runtime_prepare_unverified')
            except BaseException:
                self.pause('runtime_prepare_failed')
                raise
        return self.state['workload_id']

    def bind(self, reference):
        self._owned()
        if self.state['phase'] != 'acquired' or self.state['paused']:
            raise WorkloadBlocked('binding_phase_invalid')
        if type(reference) is not dict: raise ValueError('invalid_reference')
        self.state['reference'] = reference
        self._write()

    @serialized
    def pause(self, reason):
        self.state.update(paused=True, reason=reason)
        self._write()

    def check(self):
        # The monitor must never wait behind launch/control adapter I/O.
        with self.mutex:
            if os.getpid() != self.pid:
                raise WorkloadBlocked('forked_host_gate')
            if self.fd is None or not self.state:
                raise WorkloadBlocked('host_ownership_required')
            snapshot = copy.deepcopy(self.state)
            if snapshot.get('heartbeat_deadline', time.time()+1) < time.time() and snapshot['phase'] in ('acquired', 'launch_intent', 'running'):
                self.pause('dispatcher_heartbeat_lost')
                raise ProtectionAbort('dispatcher_heartbeat_lost')
            if snapshot['paused']:
                raise ProtectionAbort(snapshot['reason'])
        started = time.monotonic()
        try:
            if self.runtime.identity() != snapshot['identity']:
                reason = 'runtime_identity_changed'
            else:
                sample = self.runtime.sample(snapshot)
                reason = ('monitor_stale' if time.monotonic() - started > 1 else
                          self.policy.violation(sample, snapshot['ceiling']))
        except Exception:
            reason = 'monitor_lost'
        with self.mutex:
            if self.state['workload_id'] != snapshot['workload_id']:
                raise WorkloadBlocked('stale_monitor_response')
            if reason:
                self.pause(reason)
                raise ProtectionAbort(reason)
            if self.state['paused']:
                raise ProtectionAbort(self.state['reason'])

    def launch(self, specification):
        with self.mutex:
            if self.state is None or self.state['phase'] not in ('acquired', 'running'):
                raise WorkloadBlocked('launch_phase_invalid')
            workload_id = self.state['workload_id']
        self.check()
        # Repeat admission immediately before authorizing a creator. An ancestor
        # allowance may shrink between acquisition and launch.
        ceiling = self.runtime.preflight(self.policy)
        with self.mutex:
            if self.state is None or self.state['workload_id'] != workload_id:
                raise WorkloadBlocked('stale_preflight_response')
            if self.state is None or self.state['phase'] not in ('acquired', 'running'):
                raise WorkloadBlocked('launch_phase_invalid')
            if self.state['paused']:
                raise ProtectionAbort(self.state['reason'])
            if type(ceiling) is not int or ceiling < self.state['ceiling']:
                self.pause('launch_resource_deferral')
                raise ProtectionAbort('launch_resource_deferral')
            nonce = uuid.uuid4().hex
            self.state.update(phase='launch_intent', launch_nonce=nonce)
            self._write()
            snapshot = copy.deepcopy(self.state)
            self.inflight_launches += 1
        # Intent survives a lost response; cleanup enumerates this workload's
        # creators even when no birth acknowledgement reaches the journal.
        try:
            birth = self.runtime.launch(snapshot, specification)
            if not birth or self.runtime.inspect(snapshot, birth) is not True:
                raise WorkloadBlocked('launch_identity_unverified')
            with self.mutex:
                if (self.state['workload_id'] != snapshot['workload_id'] or
                        self.state.get('launch_nonce') != nonce or
                        self.state['phase'] != 'launch_intent' or self.state['paused']):
                    raise WorkloadBlocked('stale_launch_response')
                self.state['resources'].append(birth)
                self.state['phase'] = 'running'
                self._write()
        except BaseException:
            with self.mutex:
                if self.state['workload_id'] == snapshot['workload_id']:
                    self.pause('launch_acknowledgement_lost')
            raise
        finally:
            with self.mutex:
                self.inflight_launches -= 1
        return birth

    def heartbeat(self):
        self.check()
        with self.mutex:
            if self.state['phase'] not in ('acquired', 'launch_intent', 'running'):
                raise WorkloadBlocked('heartbeat_phase_invalid')
            self.state['heartbeat_deadline'] = time.time() + 5
            self._write()

    def result(self):
        self.check()
        with self.mutex:
            snapshot = copy.deepcopy(self.state)
        result = self.runtime.result(snapshot)
        with self.mutex:
            if self.state['workload_id'] != snapshot['workload_id'] or self.state['paused']:
                raise WorkloadBlocked('stale_result_response')
        return result

    def reconcile(self):
        self._owned()
        with self.mutex:
            if self.state['phase'] in ('postflight', 'commit_intent', 'committed', 'complete'):
                raise WorkloadBlocked('result_reconciliation_required')
            self.state['phase'] = 'termination_intent'
            self._write()
            snapshot = copy.deepcopy(self.state)
        # Every I/O call has its own .8s bound; termination has a separate 30s
        # verification window, with monitoring free to sample throughout.
        deadline = time.monotonic() + 30
        try:
            if self.runtime.terminate(snapshot) is not True:
                raise WorkloadBlocked('termination_unverified')
            while self.runtime.stopped(snapshot) is not True:
                if time.monotonic() >= deadline:
                    raise WorkloadBlocked('termination_unverified')
                time.sleep(.05)
        except BaseException:
            self.pause('termination_unverified')
            raise
        with self.mutex:
            if self.state['workload_id'] != snapshot['workload_id']:
                raise WorkloadBlocked('stale_cleanup_response')
            self.state['phase'] = 'cleaned'
            self._write()

    def complete(self):
        """Compatibility helper for non-database library callers only."""
        self.postflight()
        self.commit_intent({'disposition': 'no_database_result'})
        self.acknowledge_commit({'disposition': 'no_database_result'})
        self.release()

    def postflight(self):
        with self.mutex:
            if self.state is None or self.state['phase'] not in ('acquired', 'running', 'cleaned'):
                raise WorkloadBlocked('postflight_phase_invalid')
        self.check()
        if self.state['phase'] != 'cleaned': self.reconcile()
        self.check()
        with self.mutex:
            self.state['phase'] = 'postflight'
            self._write()

    def commit_intent(self, binding):
        self._owned()
        with self.mutex:
            failure = (type(binding) is dict and binding.get('disposition') in ('infrastructure_failed', 'cancelled'))
            if not (self.state['phase'] == 'postflight' and not self.state['paused'] or
                    self.state['phase'] == 'cleaned' and failure):
                raise WorkloadBlocked('commit_phase_invalid')
            if type(binding) is not dict or not binding:
                raise WorkloadBlocked('commit_binding_required')
            self.state.update(phase='commit_intent', database_commit=binding)
            self._write()

    def resolve_commit(self, binding, resolution):
        self._owned()
        with self.mutex:
            if (self.state['phase'] != 'commit_intent' or self.state.get('database_commit') != binding or
                    type(resolution) is not dict or resolution.get('disposition') != 'infrastructure_failed' or
                    any(resolution.get(key) != binding.get(key) for key in
                        ('workload_id', 'job_id', 'attempt_id', 'attempt_number', 'submission_id', 'owner'))):
                raise WorkloadBlocked('commit_resolution_invalid')
            self.state['original_database_commit'] = binding
            self.state['database_commit'] = resolution
            self._write()

    def acknowledge_commit(self, binding):
        self._owned()
        with self.mutex:
            if self.state['phase'] != 'commit_intent' or binding != self.state.get('database_commit'):
                raise WorkloadBlocked('commit_acknowledgement_invalid')
            self.state['phase'] = 'committed'
            self._write()

    def release(self):
        self.check()
        with self.mutex:
            snapshot = copy.deepcopy(self.state)
            if self.inflight_launches or self.state['phase'] != 'committed':
                raise WorkloadBlocked('committed_cleanup_required')
        if self.runtime.stopped(snapshot) is not True:
            raise WorkloadBlocked('committed_cleanup_required')
        with self.mutex:
            self.state['phase'] = 'complete'
            self._write()

    def resume(self):
        self._owned()
        with self.mutex:
            if self.inflight_launches: raise WorkloadBlocked('creator_response_pending')
            if self.state['phase'] not in ('cleaned', 'committed', 'complete'):
                raise WorkloadBlocked('result_reconciliation_required')
            snapshot = copy.deepcopy(self.state)
        if self.runtime.stopped(snapshot) is not True:
            raise WorkloadBlocked('verified_cleanup_required')
        ceiling = self.runtime.preflight(self.policy)
        if type(ceiling) is not int or ceiling <= 0: raise WorkloadBlocked('resource_deferral')
        with self.mutex:
            self.state.update(phase='complete', paused=False)
            self._write()


class WorkloadSession:
    """Monitor outside the operation subtree; invalidate results before commit.

    Runtime calls must be bounded. A stuck reader retains ownership and prevents
    completion; a deadline never establishes that the underlying call stopped.
    """
    def __init__(self, gate):
        import threading
        self.gate = gate
        self.stop = threading.Event()
        self.failed = threading.Event()
        self.thread = None
        self.reason = None

    def start(self):
        self.gate.check()
        self.last_sample = time.monotonic()
        self.abort_lock = threading.Lock()
        def fail(reason):
            if not self.abort_lock.acquire(blocking=False): return
            self.reason = reason
            self.failed.set()
            try:
                if not self.gate.state['paused']: self.gate.pause(reason)
                self.gate.reconcile()
            except BaseException: pass
        def monitor():
            deadline = time.monotonic()
            while not self.stop.is_set() and not self.failed.is_set():
                deadline += self.gate.policy.interval
                if self.stop.wait(max(0, deadline-time.monotonic())): return
                try:
                    self.gate.check()
                    self.last_sample = time.monotonic()
                except BaseException as error:
                    fail(str(error) or type(error).__name__)
                    return
        def watch_age():
            while not self.stop.wait(.05) and not self.failed.is_set():
                if time.monotonic()-self.last_sample > 1:
                    fail('monitor_stale')
                    return
        self.thread = threading.Thread(target=monitor, name='heavy-workload-monitor', daemon=True)
        self.age_thread = threading.Thread(target=watch_age, name='heavy-sample-watchdog', daemon=True)
        self.thread.start()
        self.age_thread.start()
        return self

    def checkpoint(self):
        if self.failed.is_set(): raise ProtectionAbort(self.reason or 'monitor_failed')
        self.gate.check()

    def finish_monitor(self):
        self.stop.set()
        threads = [thread for thread in (self.thread, getattr(self, 'age_thread', None)) if thread]
        for thread in threads:
            thread.join(timeout=1)
            if thread.is_alive():
                self.gate.pause('monitor_unresponsive')
                raise ProtectionAbort('monitor_unresponsive')

    def complete(self):
        self.checkpoint()
        self.finish_monitor()
        self.checkpoint()
        self.gate.complete()

    def abort(self):
        self.finish_monitor()
        self.gate.reconcile()
        return not self.gate.state['paused']
