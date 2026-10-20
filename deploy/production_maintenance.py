"""Fail-closed evidence checks; no provisioning, database writes or evaluation."""
import hashlib
import re
from pathlib import Path
from deploy.production_preparation import read_manifest
import time


def require(value):
    if not value:
        raise ValueError('maintenance_evidence_incomplete_or_invalid')


def privileged_receipt(receipt, host, collector_hash, *, now=None, execution=False):
    if receipt['schema'] == 'mldsafail.privileged-scheduling.v2':
        return reviewed_receipt(receipt, host, collector_hash, now=now, execution=execution)
    require(receipt['schema'] == 'mldsafail.privileged-scheduling.v1')
    require(receipt['host'] == host and receipt['uid'] == 0)
    require(receipt['collector_sha256'] == collector_hash)
    require(receipt['provenance'] == 'owner_root_console')
    require(0 <= (time.time() if now is None else now) - receipt['time'] < (300 if execution else 86400))
    from deploy.privileged_scheduling import SECTIONS, ROOTS
    require(set(receipt['sections']) == set(SECTIONS))
    require(set(ROOTS) <= {p['path'] for p in receipt['paths']})
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
    if receipt['at_state'] == 'installed_and_inspected':
        require(receipt['sections']['at_queue']['sha256'] == hashlib.sha256(b'').hexdigest())
    require(receipt['classification_complete'] is True and not receipt['unclassified_paths'])
    return receipt['at_state']


def bound_privileged(packet, *, execution=False):
    path = Path(packet['privileged_receipt'])
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == packet['privileged_receipt_sha256'])
    collector = hashlib.sha256(Path('deploy/privileged_scheduling.py').read_bytes()).hexdigest()
    receipt = read_manifest(path)
    if packet['schema'] == 'mldsafail.production-operation.v3':
        require(receipt['schema'] == 'mldsafail.privileged-scheduling.v2')
    return privileged_receipt(receipt, packet['hostname'], collector, execution=execution)


def packet_state(packet, maintenance, *, execution=False):
    require(packet['schema'] in ('mldsafail.production-operation.v2', 'mldsafail.production-operation.v3'))
    require(packet['state'] in ('maintenance_proposal', 'execution_ready'))
    if packet['state'] == 'maintenance_proposal':
        require(not execution and maintenance['scheduling_exclusion_verified'] is False)
    else:
        require(maintenance['scheduling_exclusion_verified'] is True)
        bound_privileged(packet, execution=execution)
        path = Path(packet['capacity_receipt'])
        data = path.read_bytes()
        require(hashlib.sha256(data).hexdigest() == packet['capacity_receipt_sha256'])
        assessment = read_manifest(path)
        require(assessment['host'] == packet['hostname'] and assessment['source'] == packet['source'])
        if packet['schema'] == 'mldsafail.production-operation.v3':
            require(assessment['measurement_scopes'] == {
                'observed_simultaneous_peak': 'operation_resources',
                'retained_services_peak': 'retained_services_excluding_operation',
                'available_ram': 'host_available_excluding_retained_usage'})
        require(capacity(assessment) == 'supported')
        measurement = Path(assessment['measurement'])
        require(not measurement.is_absolute() and '..' not in measurement.parts)
        require(hashlib.sha256((path.parent / measurement).read_bytes()).hexdigest() == assessment['measurement_sha256'])
    if execution:
        require(packet['state'] == 'execution_ready')


def capacity(evidence):
    """Use compatible simultaneous observations, never summed configured maxima."""
    required = ('physical_ram', 'available_ram', 'swap', 'configured_limits',
                'observed_simultaneous_peak', 'retained_services_peak', 'headroom',
                'ancestor_memory_limits', 'source_compatible', 'measurement_sha256')
    if any(k not in evidence for k in required):
        return 'unresolved'
    if evidence['source_compatible'] is not True or not re.fullmatch('[a-f0-9]{64}', str(evidence['measurement_sha256'])):
        return 'unresolved'
    for key in ('physical_ram', 'available_ram', 'swap', 'observed_simultaneous_peak', 'retained_services_peak', 'headroom'):
        if type(evidence[key]) is not int or evidence[key] < 0:
            return 'unresolved'
    if not isinstance(evidence['ancestor_memory_limits'], list) or not evidence['ancestor_memory_limits']:
        return 'unresolved'
    if any(x != 'max' and (type(x) is not int or x <= 0) for x in evidence['ancestor_memory_limits']):
        return 'unresolved'
    demand = evidence['observed_simultaneous_peak'] + evidence['retained_services_peak'] + evidence['headroom']
    if any(evidence[k] <= 0 for k in ('physical_ram', 'available_ram', 'observed_simultaneous_peak', 'headroom')):
        return 'unresolved'
    limits = [evidence['physical_ram'], *[x for x in evidence['ancestor_memory_limits'] if x != 'max']]
    return 'supported' if demand <= min(limits) and evidence['observed_simultaneous_peak'] + evidence['headroom'] <= evidence['available_ram'] else 'resize_decision_required'


def reviewed_receipt(receipt, host, collector_hash, *, now=None, execution=False):
    """Review binds immutable collection and raw bytes; no completeness override."""
    collection_path = Path(receipt['collection'])
    from deploy.recovery_journal import safe_path
    import os, stat
    raw_path = safe_path(receipt['raw_evidence'])
    st = raw_path.stat()
    require(stat.S_ISREG(st.st_mode) and st.st_uid == os.getuid() and st.st_nlink == 1
            and not st.st_mode & 0o077 and raw_path.parent.stat().st_uid == os.getuid()
            and not raw_path.parent.stat().st_mode & 0o077)
    require(hashlib.sha256(collection_path.read_bytes()).hexdigest() == receipt['collection_sha256'])
    require(hashlib.sha256(raw_path.read_bytes()).hexdigest() == receipt['raw_sha256'])
    c = read_manifest(collection_path)
    require(c['schema'] == 'mldsafail.scheduling-collection.v2')
    require(c['host'] == host and c['uid'] == 0 and c['collector_sha256'] == collector_hash)
    require(c['provenance'] == 'owner_root_console' and c['complete'] is True)
    require(c['raw_sha256'] == receipt['raw_sha256'])
    require(0 <= (time.time() if now is None else now) - c['time'] < (300 if execution else 86400))
    from deploy.privileged_scheduling import ROOTS, SECTIONS
    require(set(c['sections']) == set(SECTIONS))
    import json
    raw_rows = raw_path.read_bytes().splitlines(keepends=True)
    require(len(raw_rows) == len(SECTIONS))
    require({json.loads(r)['section'] for r in raw_rows} == set(SECTIONS))
    for raw in raw_rows:
        parsed = json.loads(raw)
        section = c['sections'][parsed['section']]
        require(section['raw_sha256'] == hashlib.sha256(raw).hexdigest())
        if section['error'] is None:
            require(section['sha256'] == hashlib.sha256(bytes.fromhex(parsed['stdout']) + bytes.fromhex(parsed['stderr'])).hexdigest())
        else:
            require(parsed.get('error') == section['error'])
        if parsed['section'].endswith('crontab') and section['error'] is None:
            require(section['no_crontab'] == (b'no crontab for' in bytes.fromhex(parsed['stderr'])))
        if parsed['section'] == 'at_service':
            require(section.get('not_found', False) == (b'LoadState=not-found' in bytes.fromhex(parsed['stdout'])))
    paths = c['paths']
    require(set(ROOTS) | set(c['reviewed_paths']) <= {p['path'] for p in paths})
    require(all('error' not in p for p in paths))
    # A disposition covers a path's exact evidence, including its link chain.
    evidence = {p['path']: hashlib.sha256(__import__('json').dumps(p, sort_keys=True).encode()).hexdigest() for p in paths}
    classifications = receipt['classifications']
    require(len(classifications) == len(evidence))
    require({x['path'] for x in classifications} == set(evidence))
    by_path = {p['path']: p for p in paths}
    for row in classifications:
        p = by_path[row['path']]
        if row['disposition'] == 'absent': require(p.get('absent') is True)
        if row['disposition'] == 'mask': require(p.get('mask') is True)
        if row['disposition'] in ('alias', 'wants'): require(bool(p.get('chain')))
        require(row['evidence_sha256'] == evidence[row['path']])
        require(row['disposition'] in ('absent', 'unrelated', 'scheduling', 'alias', 'wants', 'mask'))
        require(isinstance(row['rationale'], str) and bool(row['rationale'].strip()))
        require(set(row['references']) <= set(evidence))
        require(row['references_reviewed'] is True)
        if row['disposition'] == 'scheduling':
            require(set(row['unit_states']) == {'installed', 'loaded', 'active', 'masked', 'triggerable'})
            require(all(type(v) is bool for v in row['unit_states'].values()))
    # Final resolved targets must themselves have reviewed evidence.
    require(all(p.get('final_target', p['path']) in evidence for p in paths))
    state = receipt['at_state']
    require(state in ('verified_absent', 'installed_and_inspected'))
    for name, row in c['sections'].items():
        require(row['command'] == SECTIONS[name] and not row['truncated'])
        if name == 'at_queue' and state == 'verified_absent':
            require(row['error'] == 'FileNotFoundError' and row['returncode'] is None)
        else:
            require(row['error'] is None)
            require(row['returncode'] == 0 or (name.endswith('crontab') and row['returncode'] == 1 and row['no_crontab']))
    if state == 'verified_absent':
        require(c['sections']['at_service']['not_found'] is True)
        require(all(any(p['path'] == spool and p.get('absent') is True for p in paths)
                    for spool in ('/var/spool/at', '/var/spool/atjobs', '/var/spool/cron/atjobs')))
    else:
        require(c['sections']['at_queue']['sha256'] == hashlib.sha256(b'').hexdigest())
    return state
