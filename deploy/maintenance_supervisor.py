"""Durable fail-closed supervisor contract; no production CLI or implicit resume."""
from pathlib import Path
from contextvars import copy_context
import threading
import time
from deploy.production_preparation import read_manifest
from deploy.recovery_journal import atomic_json
from deploy.maintenance_fence import bind_operation


class Supervisor:
    """Injected actions must enforce deadlines and inspected ownership themselves.

    This contract is locally testable; adapters are not production certification.
    Restarts always require cleanup-only reconciliation, never continuation.
    """
    def __init__(self, root, fence, packet, actions):
        self.root, self.fence, self.packet, self.actions = Path(root), fence, packet, actions
        self.path = self.root / 'supervisor.json'
        self.restoration_attempted = False
        self.pending = []
        self.watch_stop = threading.Event()
        self.watch_error = threading.Event()
        self.watcher = None
        if self.path.exists():
            raise RuntimeError('maintenance_reconciliation_required')

    def record(self, phase, **values):
        atomic_json(self.path, dict(schema='mldsafail.maintenance-supervisor.v1', phase=phase,
                                   operation_id=self.packet['operation_id'], **values))

    def call(self, name, *, cleanup=False):
        ceilings = getattr(self.fence, 'intent', {}).get('ceilings', {})
        budget = .8 if name == 'watch_state' else ceilings.get(name, ceilings.get('cleanup', 1) if cleanup else 20)
        phase_deadline = getattr(self.fence, 'phase_deadline', None)
        deadline = time.monotonic() + budget
        if phase_deadline is not None and not cleanup:
            deadline = min(deadline, phase_deadline)
        done, results, errors = threading.Event(), [], []
        context = copy_context()
        def execute():
            try:
                results.append(context.run(self.actions[name]))
            except BaseException as error:
                errors.append(error)
            finally:
                done.set()
        thread = threading.Thread(target=execute, name='maintenance-action-' + name, daemon=True)
        self.pending = [t for t in self.pending if t.is_alive()]
        self.pending.append(thread)
        thread.start()
        while not done.wait(min(.05, max(0, deadline - time.monotonic()))):
            if time.monotonic() >= deadline:
                failed = getattr(self.fence, 'failed', None)
                if failed is not None:
                    failed.set()
                raise RuntimeError('maintenance_supervisor_action_deadline')
            failed = getattr(self.fence, 'failed', None)
            if not cleanup and (self.watch_error.is_set() or (failed is not None and failed.is_set())):
                if failed is not None:
                    failed.set()
                raise RuntimeError('maintenance_supervisor_ownership_lost')
        if errors:
            raise errors[0]
        if results != [True]:
            raise RuntimeError('maintenance_supervisor_action_unverified')
        return True

    def action(self, name):
        self.fence.verify()
        if self.watch_error.is_set():
            raise RuntimeError('maintenance_restart_interference')
        if name == 'restore':
            self.restoration_attempted = True
        self.record(name + '_intent')
        self.call(name)
        self.fence.verify()
        self.record(name + '_verified')

    def watch(self):
        if 'watch_state' not in self.actions:
            raise RuntimeError('maintenance_restart_monitor_required')
        def observe():
            while not self.watch_stop.wait(.25):
                try:
                    self.call('watch_state')
                except BaseException:
                    failed = getattr(self.fence, 'failed', None)
                    if failed is not None:
                        failed.set()
                    self.watch_error.set()
                    return
        self.watcher = threading.Thread(target=observe, name='maintenance-restart-monitor', daemon=True)
        self.watcher.start()

    def stop_watch(self):
        self.watch_stop.set()
        if self.watcher:
            self.watcher.join(timeout=2)
            if self.watcher.is_alive():
                raise RuntimeError('maintenance_restart_monitor_remains')
        if any(t.is_alive() for t in self.pending):
            raise RuntimeError('maintenance_action_reconciliation_required')

    def run(self, authorization):
        if (authorization.get('purpose') != 'production_maintenance'
                or authorization.get('state') != 'execution_ready'
                or self.packet.get('state') != 'execution_ready'):
            raise ValueError('maintenance_authorization_required')
        self.record('acquisition_intent')
        try:
            self.fence.acquire()
            self.fence.verify()
            with self.fence.phase('stop', self.actions['terminate']):
                self.action('exclude_scheduling')
                self.action('stop_coordinator')
            self.watch()
            # Epoch APIs retain their own live operation scopes and phase gates.
            with bind_operation(self.fence, self.packet):
                for name in ('create', 'audit', 'inspection'):
                    self.action(name)
            with self.fence.phase('cleanup', self.actions['terminate']):
                self.action('terminate')
                self.fence.resources_stopped(lambda: self.call('resources_stopped', cleanup=True))
                self.action('postflight')
            self.stop_watch()
            with self.fence.phase('restoration', self.actions['terminate']):
                self.action('restore')
            self.fence.release()
            self.record('complete')
        except BaseException:
            self.record('termination_intent', restoration_attempted=self.restoration_attempted,
                        restoration_status='ambiguous' if self.restoration_attempted else 'not_attempted',
                        scheduling_restored=None if self.restoration_attempted else False)
            try:
                # Deadline/ownership enforcement belongs to the bounded adapter.
                self.watch_stop.set()
                self.call('terminate', cleanup=True)
                self.call('resources_stopped', cleanup=True)
                self.stop_watch()
                stopped = not any(t.is_alive() for t in self.pending)
            except BaseException:
                stopped = False
            self.record('reconciliation_required',
                        restoration_attempted=self.restoration_attempted,
                        restoration_status='ambiguous' if self.restoration_attempted else 'not_attempted',
                        scheduling_restored=None if self.restoration_attempted else False, resources_stopped=stopped)
            # Never restore after an ambiguous launch or failed postflight.
            raise

    @staticmethod
    def reconcile(root, cleanup):
        path = Path(root) / 'supervisor.json'
        state = read_manifest(path)
        if cleanup() is not True:
            raise RuntimeError('maintenance_cleanup_unverified')
        atomic_json(path, dict(state, phase='cleanup_only',
                              scheduling_restored=state.get('scheduling_restored'),
                              restoration_status=state.get('restoration_status', 'unknown')))
