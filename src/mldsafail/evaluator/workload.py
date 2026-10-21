"""Durable physical-host execution gate, independent of database leases.

The runtime adapter must provide bounded, inspected cgroup/container operations.
No adapter is implicitly trusted or selected; this module grants no Docker access.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
from functools import wraps
import uuid


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
        self.policy = policy or ResourcePolicy()
        self.fd = None
        self.mutex = threading.RLock()
        self.state = None
        self.path = self.root / 'workload.json'

    def _write(self):
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
            if self.path.exists():
                info = self.path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077:
                    raise WorkloadBlocked('unsafe_workload_journal')
                self.state = json.loads(self.path.read_text())
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
        if self.state and (self.state['phase'] != 'complete' or self.state['paused']):
            raise WorkloadBlocked('cleanup_or_resume_required')
        if kind not in ('evaluation', 'administration'): raise ValueError('invalid_workload_kind')
        identity = self.runtime.identity()
        if not identity.get('boot_id') or not identity.get('daemon_id'):
            raise WorkloadBlocked('runtime_identity_required')
        ceiling = self.runtime.preflight(self.policy)
        if type(ceiling) is not int or ceiling <= 0:
            raise WorkloadBlocked('resource_deferral')
        self.state = dict(schema='mldsafail.workload.v1', workload_id=uuid.uuid4().hex,
                          identity=identity, kind=kind, reference=reference,
                          policy_sha256=self.policy.sha256, ceiling=ceiling,
                          phase='acquired', paused=False, resources=[])
        self._write()
        return self.state['workload_id']

    @serialized
    def bind(self, reference):
        self._owned()
        self.state['reference'] = reference
        self._write()

    @serialized
    def pause(self, reason):
        self.state.update(paused=True, reason=reason)
        self._write()

    @serialized
    def check(self):
        self._owned()
        if self.state['paused']: raise ProtectionAbort(self.state['reason'])
        try: reason = self.policy.violation(self.runtime.sample(self.state), self.state['ceiling'])
        except Exception: reason = 'monitor_lost'
        if reason:
            self.pause(reason)
            raise ProtectionAbort(reason)

    @serialized
    def launch(self, specification):
        self.check()
        # Intent survives lost launch acknowledgement. Runtime uses workload ID
        # to enumerate creators and resources, including an unacknowledged birth.
        self.state['phase'] = 'launch_intent'
        self._write()
        try:
            birth = self.runtime.launch(self.state, specification)
            if not birth or self.runtime.inspect(self.state, birth) is not True:
                raise WorkloadBlocked('launch_identity_unverified')
            self.state['resources'].append(birth)
            self.state['phase'] = 'running'
            self._write()
        except BaseException:
            self.pause('launch_acknowledgement_lost')
            raise
        return birth

    @serialized
    def reconcile(self):
        self._owned()
        self.state['phase'] = 'termination_intent'
        self._write()
        if self.runtime.terminate(self.state) is not True or self.runtime.stopped(self.state) is not True:
            self.pause('termination_unverified')
            raise WorkloadBlocked('termination_unverified')
        self.state['phase'] = 'cleaned'
        self._write()

    @serialized
    def complete(self):
        self.check()
        self.reconcile()
        self.check()  # Includes parent OOM/events after worker exit.
        self.state['phase'] = 'complete'
        self._write()

    @serialized
    def resume(self):
        self._owned()
        if self.state['phase'] != 'cleaned' or self.runtime.stopped(self.state) is not True:
            raise WorkloadBlocked('verified_cleanup_required')
        ceiling = self.runtime.preflight(self.policy)
        if type(ceiling) is not int or ceiling <= 0: raise WorkloadBlocked('resource_deferral')
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
        import threading
        self.gate.check()
        def monitor():
            while not self.stop.wait(self.gate.policy.interval):
                try: self.gate.check()
                except BaseException as error:
                    self.reason = type(error).__name__
                    self.failed.set()
                    # Stop resources on detection, even if the controller is
                    # blocked waiting for a worker. Preserve the pause journal.
                    try: self.gate.reconcile()
                    except BaseException: pass
                    return
        self.thread = threading.Thread(target=monitor, name='heavy-workload-monitor', daemon=True)
        self.thread.start()
        return self

    def checkpoint(self):
        if self.failed.is_set(): raise ProtectionAbort(self.reason or 'monitor_failed')
        self.gate.check()

    def finish_monitor(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)
            if self.thread.is_alive():
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
