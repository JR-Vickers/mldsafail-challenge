"""Offline operation materialization and purpose-specific investigation gate."""
import hashlib
import json
from pathlib import Path
import re
import time

from deploy.recovery_journal import atomic_json
from deploy.production_preparation import read_manifest


def worker_wrapper(operation, parent, worker_image):
    """Frozen Docker command router with exact ownership on lifecycle operations.

    The controller's Docker API surface and wrapper invocation require Linux
    acceptance before use. This shim provides no authority to launch by itself.
    """
    if not re.fullmatch('[a-f0-9]{32}', operation) or not re.fullmatch('[A-Za-z0-9_.-]+', parent):
        raise ValueError('investigation_identity_invalid')
    if not re.fullmatch('sha256:[a-f0-9]{64}', worker_image):
        raise ValueError('investigation_image_invalid')
    return '''#!/app/.venv/bin/python
# org.mldsafail.capacity-investigation ownership is enforced by the router.
import json, runpy, sys
sys.path.insert(0, '/operation-tools')
config = '/operation-tools/router.json'
with open(config) as stream:
    values = json.load(stream)
if (values['operation_id'], values['parent'], values['image']) != %r:
    raise SystemExit('investigation router binding changed')
sys.argv = ['investigation_docker', '--config', config] + sys.argv[1:]
runpy.run_path('/operation-tools/investigation_docker.py', run_name='__main__')
''' % ((operation, parent, worker_image),)



def admission(packet, authorization, *, now=None):
    """Investigation can never accept maintenance or production epoch authority."""
    now = time.time() if now is None else now
    if (packet.get('state') != 'execution_ready' or packet.get('execution_authority') is not True
            or packet.get('blockers') or authorization.get('purpose') != 'capacity_investigation_only'
            or authorization.get('operation_id') != packet.get('operation_id')
            or not packet.get('host') or not packet.get('provider_size') or not packet.get('execution_window')
            or not 0 <= now - authorization.get('time', 0) < 300):
        raise ValueError('capacity_investigation_not_authorized')
    digest = hashlib.sha256(json.dumps(packet, sort_keys=True).encode()).hexdigest()
    if authorization.get('packet_sha256') != digest:
        raise ValueError('capacity_investigation_packet_changed')


class Runner:
    """Single-attempt runner with durable launch intent and cleanup-only recovery.

    launch, stop and inspect are reviewed bounded owned-resource adapters. No
    default Docker adapter is supplied: preparation cannot silently become launch.
    """
    def __init__(self, root, packet, launch, stop, inspect, guard, *, monitor=None):
        self.root, self.packet = Path(root), packet
        self.launch, self.stop, self.inspect, self.guard = launch, stop, inspect, guard
        self.monitor = monitor
        self.client = None

    def run(self, authorization):
        admission(self.packet, authorization)
        if self.monitor is None or self.monitor.operation_id != self.packet['operation_id']:
            raise ValueError('capacity_continuous_monitor_required')
        if [c['phase'] for c in self.packet['commands']] != ['create_and_reference', 'audit']:
            raise ValueError('capacity_phase_protocol_invalid')
        attempt = self.root / 'attempt.json'
        # Exclusive publication protects against retry after lost acknowledgement.
        from scripts.production_epoch_operation import publish
        publish(attempt, dict(state='intent', operation_id=self.packet['operation_id']))
        try:
            self.monitor.start()
            for command in self.packet['commands']:
                if self.guard() is not True or self.monitor.guard() is not True:
                    raise RuntimeError('investigation_guard_rejected')
                self.monitor.transition('create' if command['phase'] == 'create_and_reference' else 'audit')
                atomic_json(self.root / 'phase.json', dict(phase=command['phase'], state='launch_intent'))
                self.client = self.launch(command)
                deadline = time.monotonic() + command['timeout']
                while self.client.poll() is None:
                    if self.guard() is not True or self.monitor.guard() is not True:
                        raise RuntimeError('investigation_guard_rejected')
                    if time.monotonic() >= deadline:
                        raise RuntimeError('investigation_phase_deadline')
                    time.sleep(.05)
                self.monitor.guard()
                if self.client.poll() != 0:
                    raise RuntimeError('investigation_phase_failed')
                if self.stop() is not True or self.inspect() is not True:
                    raise RuntimeError('investigation_termination_unverified')
            self.monitor.transition('cleanup')
            if self.stop() is not True or self.inspect() is not True:
                raise RuntimeError('investigation_termination_unverified')
            self.monitor.finish()
            atomic_json(attempt, dict(state='terminated', operation_id=self.packet['operation_id'], capture_complete=True,
                                           validated=False, capacity='unresolved'))
        except BaseException:
            atomic_json(attempt, dict(state='termination_intent', capacity='unresolved'))
            stopped = False
            try:
                stopped = self.stop() is True and self.inspect() is True
                stopped = stopped and (self.client is None or self.client.poll() is not None)
            finally:
                try:
                    self.monitor.abort()
                finally:
                    atomic_json(attempt, dict(state='reconciliation_required', capacity='unresolved',
                                             resources_stopped=stopped))
            raise

    def reconcile(self):
        read_manifest(self.root / 'attempt.json')
        if self.stop() is not True or self.inspect() is not True:
            raise RuntimeError('investigation_cleanup_unverified')
        atomic_json(self.root / 'cleanup.json', dict(cleanup_only=True, scheduling_restored=False))


def output_budget(root, logs, samples):
    """Bound exclusive generation bytes; reject links and nonregular artifacts."""
    import stat
    import os
    root = Path(root)
    total = 0
    deadline = time.monotonic() + .1
    for index, path in enumerate(root.rglob('*')):
        if index >= 16384 or time.monotonic() > deadline:
            raise ValueError('investigation_output_scan_bound')
        st = path.lstat()
        if st.st_dev != root.stat().st_dev or st.st_uid != os.getuid():
            raise ValueError('investigation_output_ownership_ambiguous')
        if stat.S_ISDIR(st.st_mode):
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_dev != root.stat().st_dev:
            raise ValueError('investigation_output_ownership_ambiguous')
        total += st.st_size
        if total > 1024**3:
            raise ValueError('investigation_generation_output_limit')
    for paths, limit in ((logs, 128 * 1024**2), (samples, 64 * 1024**2)):
        if any(not Path(p).is_relative_to(root) for p in paths) or sum(Path(p).stat().st_size for p in paths) > limit:
            raise ValueError('investigation_stream_output_limit')
    return total
