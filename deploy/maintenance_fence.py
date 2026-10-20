"""Local maintenance control. No scheduler mutation, draining, or implicit resume.

Transport and container identity are injected by the caller. This module is not a
VPS entry point. A production transport requires separate review and authority.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
import uuid

from deploy.recovery_journal import atomic_json, safe_path, sync_directory
from deploy.production_preparation import read_manifest

KEY = 1296843841
PHASES = {'stop', 'create', 'audit', 'inspection', 'cleanup', 'restoration', 'margin'}


def require(value, message='maintenance_fence_invalid'):
    if not value:
        raise RuntimeError(message)


def prepare(root, *, database, container, lifetime, ceilings):
    """Persist a unique intent without opening a connection or acquiring locks."""
    require(type(lifetime) is int and 0 < lifetime <= 9000)
    require(set(ceilings) == PHASES and all(type(v) is int and v > 0 for v in ceilings.values()))
    require(sum(ceilings.values()) + 2 <= lifetime, 'maintenance_budget_insufficient')
    require(isinstance(database, dict) and database and isinstance(container, str) and container)
    root = safe_path(Path(root).absolute())
    root.mkdir(mode=0o700)  # Exclusive generation, never overwrite old authority.
    require(root.stat().st_uid == os.getuid() and not root.stat().st_mode & 0o077)
    intent = dict(schema='mldsafail.maintenance-fence.v1', tag='maintenance-' + uuid.uuid4().hex,
                  database=database, container=container, lifetime=lifetime, ceilings=ceilings,
                  started=datetime.now(timezone.utc).isoformat(), state='prepared')
    atomic_json(root / 'intent.json', intent)
    sync_directory(root.parent)
    return intent


def database_identity(connection):
    row = connection.execute("SELECT current_database(), (SELECT oid FROM pg_database WHERE datname=current_database()), "
                             "pg_postmaster_start_time()::text, inet_server_addr()::text, inet_server_port()").fetchone()
    return dict(zip(('name', 'oid', 'postmaster_start', 'address', 'port'), row))


def backends(connection, tag):
    return connection.execute("SELECT pid, backend_start::text FROM pg_stat_activity "
                              "WHERE application_name=%s AND datname=current_database()", (tag,)).fetchall()


def locks(connection, pid):
    return connection.execute("SELECT "
        "EXISTS(SELECT 1 FROM pg_locks WHERE pid=%s AND locktype='advisory' AND classid=0 "
        "AND objid=%s AND objsubid=1 AND mode='ExclusiveLock' AND granted), "
        "EXISTS(SELECT 1 FROM pg_locks WHERE pid=%s AND database=(SELECT oid FROM pg_database "
        "WHERE datname=current_database()) AND relation='public.evaluation_jobs'::regclass "
        "AND locktype='relation' AND mode='ShareLock' AND granted)", (pid, KEY, pid)).fetchone() == (True, True)


class Fence:
    """One process owns the holder thread; verification uses a separate connection.

    connect must enforce a bounded connect timeout. Its connections must be new,
    autocommit psycopg connections. identity must return the actual container ID
    with bounded I/O, not a cached caller-supplied label.
    """
    def __init__(self, root, connect, identity):
        self.root = safe_path(Path(root).absolute())
        self.intent = read_manifest(self.root / 'intent.json')
        require(self.intent['schema'] == 'mldsafail.maintenance-fence.v1')
        import re
        require(re.fullmatch('maintenance-[a-f0-9]{32}', self.intent['tag']))
        require(type(self.intent['lifetime']) is int and 0 < self.intent['lifetime'] <= 9000)
        ceilings = self.intent['ceilings']
        require(set(ceilings) == PHASES and all(type(v) is int and v > 0 for v in ceilings.values()))
        require(sum(ceilings.values()) + 2 <= self.intent['lifetime'])
        self.connect, self.identity = connect, identity
        self.failed, self.stop_monitor = threading.Event(), threading.Event()
        self.mutex = threading.RLock()
        self.abort = None
        self.backend = None
        self.holder = None
        self.monitor = None
        self.verifier = None
        self.holder_error = None
        self.deadline = 0
        self.phase_deadline = None
        self.used_phases = set()
        self.abort_done = threading.Event()
        self.abort_started = False
        self.cleanup_error = None

    def _record(self, state, **extra):
        atomic_json(self.root / 'state.json', dict(state=state, **extra))

    def _identity(self, connection):
        require(self.identity() == self.intent['container'], 'maintenance_container_changed')
        require(database_identity(connection) == self.intent['database'], 'maintenance_database_changed')

    def _verify(self):
        require(not self.failed.is_set() and self.holder is not None and self.holder.is_alive(), 'maintenance_holder_lost')
        require(time.monotonic() < self.deadline, 'maintenance_expired')
        require(self.phase_deadline is None or time.monotonic() < self.phase_deadline, 'maintenance_phase_expired')
        self._identity(self.verifier)
        require(backends(self.verifier, self.intent['tag']) == [self.backend], 'maintenance_backend_changed')
        require(locks(self.verifier, self.backend[0]), 'maintenance_locks_lost')
        require(self.verifier.execute("SELECT count(*) FROM public.evaluation_jobs WHERE status IN "
                                      "('queued','claimed','running')").fetchone()[0] == 0, 'maintenance_pending_work')

    def verify(self):
        with self.mutex:
            try:
                started = time.monotonic()
                self._verify()
                require(time.monotonic() - started < .8, 'maintenance_verification_timeout')
            except BaseException:
                self.failed.set()
                raise
        return True

    def acquire(self):
        require(not (self.root / 'acquisition.json').exists(), 'maintenance_reconciliation_required')
        atomic_json(self.root / 'acquisition.json', dict(tag=self.intent['tag'], state='intent'))
        self._record('acquiring')
        self.deadline = time.monotonic() + self.intent['lifetime']
        self.verifier = self.connect()
        require(self.verifier.autocommit, 'maintenance_autocommit_required')
        self.verifier.execute("SET statement_timeout='100ms'")
        self.verifier.execute("SET lock_timeout='100ms'")
        self._identity(self.verifier)
        # Birth and PID are persisted before lock acquisition, closing lost-ack
        # ambiguity without matching arbitrary backends solely by tag.
        connection = self.connect()
        try:
            require(connection.autocommit, 'maintenance_autocommit_required')
            self._identity(connection)
            connection.execute("SELECT set_config('application_name', %s, false)", (self.intent['tag'],))
            self.backend = connection.execute('SELECT pg_backend_pid(), backend_start::text FROM pg_stat_activity '
                                              'WHERE pid=pg_backend_pid()').fetchone()
            atomic_json(self.root / 'authority.json', dict(backend=self.backend, tag=self.intent['tag']))
        except BaseException:
            connection.close()
            self._record('reconciliation_required')
            raise

        def hold():
            try:
                # One server-timed statement covers acquisition, check and sleep.
                # Any error terminates this transaction and the connection.
                connection.execute("SET statement_timeout = '" + str(self.intent['lifetime'] * 1000) + "ms'")
                connection.execute("SET lock_timeout='2s'")
                connection.execute("BEGIN")
                connection.execute("DO $$ BEGIN PERFORM pg_advisory_xact_lock(" + str(KEY) + "); "
                    "LOCK TABLE public.evaluation_jobs IN SHARE MODE; "
                    "IF EXISTS(SELECT 1 FROM public.evaluation_jobs WHERE status IN ('queued','claimed','running')) "
                    "THEN RAISE EXCEPTION 'maintenance_pending_work'; END IF; "
                    "PERFORM pg_sleep(" + str(self.intent['lifetime']) + "); END $$")
            except BaseException as error:
                self.holder_error = type(error).__name__
            finally:
                connection.close()
                self.failed.set()
        self.holder = threading.Thread(target=hold, name=self.intent['tag'], daemon=True)
        self.holder.start()
        until = time.monotonic() + 3
        try:
            while not locks(self.verifier, self.backend[0]):
                require(self.holder.is_alive() and not self.failed.is_set(), 'maintenance_acquisition_failed')
                require(time.monotonic() < until, 'maintenance_acquisition_timeout')
                time.sleep(.02)
            # Holding both locks precedes the pending check in the server block;
            # this independent read also rejects the brief pre-check interval.
            self.verify()
            self._record('held', backend=self.backend)
            self.monitor = threading.Thread(target=self._watch, name='maintenance-verifier', daemon=True)
            self.monitor.start()
            return self
        except BaseException:
            self.failed.set()
            self._record('reconciliation_required')
            raise

    def _watch(self):
        while not self.stop_monitor.wait(.1):
            try:
                self.verify()
            except BaseException:
                # Abort is registered before phase launch and remains registered
                # through owned-resource cleanup. No scheduler restoration here.
                try:
                    self._abort_active()
                finally:
                    self._record('reconciliation_required')
                return

    def _abort_active(self):
        with self.mutex:
            abort = self.abort
            if abort is None:
                return
            first = not self.abort_started
            self.abort_started = True
        if first:
            try:
                abort()
            except BaseException as error:
                self.cleanup_error = type(error).__name__
            finally:
                self.abort_done.set()
        else:
            require(self.abort_done.wait(self.intent['ceilings']['cleanup']), 'maintenance_cleanup_timeout')
        require(self.cleanup_error is None, 'maintenance_cleanup_reconciliation_required')

    @contextmanager
    def phase(self, name, terminate):
        require(name in PHASES - {'margin'}, 'maintenance_phase_unknown')
        with self.mutex:
            self.verify()
            require(self.abort is None and name not in self.used_phases, 'maintenance_phase_already_active')
            require(time.monotonic() + sum(v for k, v in self.intent['ceilings'].items() if k not in self.used_phases) <= self.deadline,
                    'maintenance_phase_budget_insufficient')
            self.abort_started = False
            self.abort_done.clear()
            self.abort = terminate
            self.used_phases.add(name)
            self.phase_deadline = time.monotonic() + self.intent['ceilings'][name]
        try:
            yield self
            self.verify()
        except BaseException:
            self.failed.set()
            self._abort_active()
            self._record('reconciliation_required')
            raise
        finally:
            with self.mutex:
                self.abort = None
                self.phase_deadline = None

    def release(self):
        require(self.abort is None, 'maintenance_phase_active')
        require(self.cleanup_error is None, 'maintenance_cleanup_reconciliation_required')
        self.stop_monitor.set()
        if self.monitor:
            self.monitor.join(timeout=2)
            require(not self.monitor.is_alive(), 'maintenance_verifier_not_terminated')
        try:
            reconcile(self.root, self.connect, self.identity)
            if self.holder:
                self.holder.join(timeout=2)
                require(not self.holder.is_alive(), 'maintenance_client_not_terminated')
            self._record('released', backend_absent=True, locks_absent=True, client_terminated=True)
        finally:
            if self.verifier:
                self.verifier.close()


def reconcile(root, connect, identity):
    """Cleanup only: no acquisition, phase continuation or scheduler restoration."""
    root = safe_path(Path(root).absolute())
    intent = read_manifest(root / 'intent.json')
    authority_path = root / 'authority.json'
    require(authority_path.exists(), 'maintenance_unacknowledged_acquisition')
    authority = read_manifest(authority_path)
    require(authority['tag'] == intent['tag'])
    backend = tuple(authority['backend'])
    with connect() as connection:
        connection.execute("SET statement_timeout='100ms'")
        require(identity() == intent['container'] and database_identity(connection) == intent['database'],
                'maintenance_identity_drift')
        rows = backends(connection, intent['tag'])
        require(not rows or rows == [backend], 'maintenance_backend_changed')
        if rows:
            require(connection.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid=%s "
                "AND backend_start=%s::timestamptz AND application_name=%s AND datname=current_database()",
                (*backend, intent['tag'])).fetchone() == (True,), 'maintenance_termination_unacknowledged')
        until = time.monotonic() + 2
        while backends(connection, intent['tag']):
            require(time.monotonic() < until, 'maintenance_backend_remains')
            time.sleep(.02)
        require(connection.execute('SELECT count(*) FROM pg_locks WHERE pid=%s', (backend[0],)).fetchone()[0] == 0,
                'maintenance_locks_remain')
    atomic_json(root / 'reconciled.json', dict(backend_absent=True, locks_absent=True,
                client_termination_verified=False, scheduling_restored=False))
    return True


# Deliberately no CLI transport: later execution must supply a reviewed live fence.
from contextvars import ContextVar
from functools import wraps
_ACTIVE = ContextVar('maintenance_operation', default=None)


@contextmanager
def bind_operation(fence, packet):
    require(isinstance(fence, Fence))
    fence.verify()
    require(packet['maintenance_fence_tag'] == fence.intent['tag'])
    require(packet['maintenance_database_identity'] == fence.intent['database'])
    require(packet['maintenance_database_container'] == fence.intent['container'])
    token = _ACTIVE.set((fence, packet['operation_id']))
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def operation_phase(name):
    """All epoch mutators require the same continuously monitored live owner."""
    def decorate(function):
        @wraps(function)
        def guarded(packet_path, *args, **kwargs):
            from scripts.production_epoch_operation import read_packet, terminate_owned
            packet = read_packet(packet_path)
            active = _ACTIVE.get()
            if active is None or active[1] != packet['operation_id']:
                raise ValueError('live_maintenance_fence_required')
            fence = active[0]
            def abort():
                # Before operation directory creation no request can be launched.
                if Path(packet['operation']).exists():
                    terminate_owned(packet)
            with fence.phase(name, abort):
                return function(packet_path, *args, **kwargs)
        return guarded
    return decorate
