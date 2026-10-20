"""Fail-closed evidence checks; no provisioning, database writes or evaluation."""
import hashlib
import json
from pathlib import Path
import time


def require(value):
    if not value:
        raise ValueError('maintenance_evidence_incomplete_or_invalid')


def privileged_receipt(receipt, host, collector_hash, *, now=None, execution=False):
    require(receipt['schema'] == 'mldsafail.privileged-scheduling.v1')
    require(receipt['host'] == host and receipt['uid'] == 0)
    require(receipt['collector_sha256'] == collector_hash)
    require(receipt['provenance'] == 'owner_root_console')
    require(0 <= (time.time() if now is None else now) - receipt['time'] < (300 if execution else 86400))
    from deploy.privileged_scheduling import SECTIONS
    require(set(receipt['sections']) == set(SECTIONS))
    require(receipt['paths'] and all('error' not in p and not p.get('symlink') for p in receipt['paths']))
    if receipt['at_state'] == 'verified_absent':
        require('LoadState=not-found' in receipt['sections']['at_service']['output'])
        for spool in ('/var/spool/at', '/var/spool/atjobs', '/var/spool/cron/atjobs'):
            require(any(p['path'] == spool and p.get('absent') is True for p in receipt['paths']))
    for name, row in receipt['sections'].items():
        require(row['command'] == SECTIONS[name])
        if name == 'at_queue' and receipt['at_state'] == 'verified_absent':
            require(row['error'] == 'FileNotFoundError' and row['returncode'] is None)
            continue
        require(row['error'] is None and not row['truncated'])
        require(row['returncode'] == 0 or (name.endswith('crontab') and
                row['returncode'] == 1 and row['no_crontab'] is True))
    require(receipt['at_state'] in ('installed_and_inspected', 'verified_absent'))
    require(receipt['classification_complete'] is True and not receipt['unclassified_paths'])
    return receipt['at_state']


def bound_privileged(packet, *, execution=False):
    path = Path(packet['privileged_receipt'])
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == packet['privileged_receipt_sha256'])
    collector = hashlib.sha256(Path('deploy/privileged_scheduling.py').read_bytes()).hexdigest()
    return privileged_receipt(json.loads(data), packet['hostname'], collector, execution=execution)


def packet_state(packet, maintenance, *, execution=False):
    require(packet['schema'] == 'mldsafail.production-operation.v2')
    require(packet['state'] in ('maintenance_proposal', 'execution_ready'))
    if packet['state'] == 'maintenance_proposal':
        require(not execution and maintenance['scheduling_exclusion_verified'] is False)
    else:
        require(maintenance['scheduling_exclusion_verified'] is True)
        bound_privileged(packet, execution=execution)
    if execution:
        require(packet['state'] == 'execution_ready')


def capacity(evidence):
    """Use compatible simultaneous observations, never summed configured maxima."""
    required = ('physical_ram', 'available_ram', 'swap', 'configured_limits',
                'observed_simultaneous_peak', 'retained_services_peak', 'headroom',
                'ancestor_memory_limits', 'source_compatible', 'measurement_sha256')
    if any(k not in evidence for k in required):
        return 'unresolved'
    if not evidence['source_compatible'] or not evidence['measurement_sha256']:
        return 'unresolved'
    demand = evidence['observed_simultaneous_peak'] + evidence['retained_services_peak'] + evidence['headroom']
    if any(evidence[k] <= 0 for k in ('physical_ram', 'available_ram', 'observed_simultaneous_peak', 'headroom')):
        return 'unresolved'
    limits = [evidence['physical_ram'], *[x for x in evidence['ancestor_memory_limits'] if x != 'max']]
    return 'supported' if demand <= min(limits) and evidence['observed_simultaneous_peak'] + evidence['headroom'] <= evidence['available_ram'] else 'resize_decision_required'
