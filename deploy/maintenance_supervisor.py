"""Durable fail-closed supervisor contract; no production CLI or implicit resume."""
from pathlib import Path
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
        if self.path.exists():
            raise RuntimeError('maintenance_reconciliation_required')

    def record(self, phase, **values):
        atomic_json(self.path, dict(schema='mldsafail.maintenance-supervisor.v1', phase=phase,
                                   operation_id=self.packet['operation_id'], **values))

    def action(self, name):
        self.fence.verify()
        self.record(name + '_intent')
        if self.actions[name]() is not True:
            raise RuntimeError('maintenance_supervisor_action_unverified')
        self.fence.verify()
        self.record(name + '_verified')

    def run(self, authorization):
        if (authorization.get('purpose') != 'production_maintenance'
                or authorization.get('state') != 'execution_ready'
                or self.packet.get('state') != 'execution_ready'):
            raise ValueError('maintenance_authorization_required')
        self.record('acquisition_intent')
        try:
            self.fence.acquire()
            self.action('exclude_scheduling')
            with self.fence.phase('stop', self.actions['terminate']):
                self.action('stop_coordinator')
            # Epoch APIs retain their own live operation scopes and phase gates.
            with bind_operation(self.fence, self.packet):
                for name in ('create', 'audit', 'inspection'):
                    self.action(name)
            with self.fence.phase('cleanup', self.actions['terminate']):
                self.action('terminate')
                self.fence.resources_stopped(self.actions['resources_stopped'])
            self.action('postflight')
            with self.fence.phase('restoration', self.actions['terminate']):
                self.action('restore')
            self.fence.release()
            self.record('complete')
        except BaseException:
            self.record('termination_intent', scheduling_restored=False)
            try:
                # Deadline/ownership enforcement belongs to the bounded adapter.
                stopped = self.actions['terminate']() is True and self.actions['resources_stopped']() is True
            except BaseException:
                stopped = False
            self.record('reconciliation_required', scheduling_restored=False, resources_stopped=stopped)
            # Never restore after an ambiguous launch or failed postflight.
            raise

    @staticmethod
    def reconcile(root, cleanup):
        path = Path(root) / 'supervisor.json'
        state = read_manifest(path)
        if cleanup() is not True:
            raise RuntimeError('maintenance_cleanup_unverified')
        atomic_json(path, dict(state, phase='cleanup_only', scheduling_restored=False))
