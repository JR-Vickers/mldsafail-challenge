"""Offline operation materialization and purpose-specific investigation gate."""
import hashlib
import json
from pathlib import Path
import re
import time

from deploy.recovery_journal import atomic_json
from deploy.production_preparation import read_manifest


def worker_wrapper(operation, parent, worker_image):
    """Exact Docker argv shim: reject all actions except the frozen worker run.

    The controller's Docker API surface and wrapper invocation require Linux
    acceptance before use. This shim provides no authority to launch by itself.
    """
    if not re.fullmatch('[a-f0-9]{32}', operation) or not re.fullmatch('[A-Za-z0-9_.-]+', parent):
        raise ValueError('investigation_identity_invalid')
    if not re.fullmatch('sha256:[a-f0-9]{64}', worker_image):
        raise ValueError('investigation_image_invalid')
    return '''#!/usr/bin/python3
import os, sys
args = sys.argv[1:]
if not args or args[0] != 'run' or %r not in args:
    raise SystemExit('frozen worker run required')
if any(a == '--privileged' or a.startswith('--cgroup-parent') or a.startswith('--label') for a in args):
    raise SystemExit('worker ownership override rejected')
os.execv('/usr/bin/docker', ['/usr/bin/docker', 'run', '--label', %r, '--cgroup-parent', %r] + args[1:])
''' % (worker_image, 'org.mldsafail.capacity-investigation=' + operation, parent)


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
    def __init__(self, root, packet, launch, stop, inspect, guard):
        self.root, self.packet = Path(root), packet
        self.launch, self.stop, self.inspect, self.guard = launch, stop, inspect, guard

    def run(self, authorization):
        admission(self.packet, authorization)
        attempt = self.root / 'attempt.json'
        # Exclusive publication protects against retry after lost acknowledgement.
        from scripts.production_epoch_operation import publish
        publish(attempt, dict(state='intent', operation_id=self.packet['operation_id']))
        try:
            for command in self.packet['commands']:
                self.guard()  # Must certify sampler, scheduling and host health.
                atomic_json(self.root / 'phase.json', dict(phase=command['phase'], state='launch_intent'))
                client = self.launch(command)
                result = client.wait(timeout=command['timeout'])
                self.guard()
                if result != 0:
                    raise RuntimeError('investigation_phase_failed')
                if self.stop() is not True or self.inspect() is not True:
                    raise RuntimeError('investigation_termination_unverified')
            atomic_json(attempt, dict(state='terminated', measured=False, capacity='unresolved'))
        except BaseException:
            atomic_json(attempt, dict(state='reconciliation_required', capacity='unresolved'))
            self.stop()
            raise

    def reconcile(self):
        read_manifest(self.root / 'attempt.json')
        if self.stop() is not True or self.inspect() is not True:
            raise RuntimeError('investigation_cleanup_unverified')
        atomic_json(self.root / 'cleanup.json', dict(cleanup_only=True, scheduling_restored=False))


def output_budget(root, logs, samples):
    """Bound exclusive generation bytes; reject links and nonregular artifacts."""
    import stat
    root = Path(root)
    total = 0
    for path in root.rglob('*'):
        st = path.lstat()
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
