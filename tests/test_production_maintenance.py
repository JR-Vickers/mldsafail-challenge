import copy
import hashlib
import pytest
from deploy.production_maintenance import privileged_receipt, packet_state, capacity
from deploy.privileged_scheduling import SECTIONS, ROOTS


def receipt():
    result = dict(schema='mldsafail.privileged-scheduling.v1', host='host', uid=0,
                collector_sha256='hash', provenance='owner_root_console', time=1000,
                sections={k: dict(command=v, error=None, truncated=False, returncode=0)
                          for k, v in SECTIONS.items()},
                paths=[dict(path=p, absent=True) for p in ROOTS],
                at_state='installed_and_inspected', classification_complete=True,
                unclassified_paths=[])
    result['sections']['at_queue']['sha256'] = hashlib.sha256(b'').hexdigest()
    return result


def test_receipt_valid():
    assert privileged_receipt(receipt(), 'host', 'hash', now=1100, execution=True) == 'installed_and_inspected'


@pytest.mark.parametrize('mutation', ['stale', 'host', 'hash', 'provenance', 'incomplete', 'hidden', 'path_error', 'missing'])
def test_receipt_rejects(mutation):
    r = receipt()
    if mutation == 'stale': r['time'] = 0
    if mutation == 'host': r['host'] = 'other'
    if mutation == 'hash': r['collector_sha256'] = 'other'
    if mutation == 'provenance': r['provenance'] = 'unverified'
    if mutation == 'incomplete': r['classification_complete'] = False
    if mutation == 'hidden': r['unclassified_paths'] = ['/root']
    if mutation == 'path_error': r['paths'][0]['error'] = 'PermissionError'
    if mutation == 'missing': del r['sections']['root_crontab']
    with pytest.raises(ValueError): privileged_receipt(r, 'host', 'hash', now=1100, execution=True)


def test_verified_at_absence():
    r = receipt(); r['at_state'] = 'verified_absent'
    r['sections']['at_service']['output'] = 'LoadState=not-found\n'
    r['sections']['at_queue'].update(error='FileNotFoundError', returncode=None)
    r['paths'] += [dict(path=p, absent=True) for p in ('/var/spool/at', '/var/spool/atjobs', '/var/spool/cron/atjobs')]
    assert privileged_receipt(r, 'host', 'hash', now=1100) == 'verified_absent'
    r['paths'] = [p for p in r['paths'] if p['path'] != '/var/spool/atjobs']
    with pytest.raises(ValueError): privileged_receipt(r, 'host', 'hash', now=1100)


def test_proposal_never_execution():
    p = dict(schema='mldsafail.production-operation.v2', state='maintenance_proposal')
    m = dict(scheduling_exclusion_verified=False)
    packet_state(p, m)
    with pytest.raises(ValueError): packet_state(p, m, execution=True)
    m['scheduling_exclusion_verified'] = True
    with pytest.raises(ValueError): packet_state(p, m)


def test_capacity_uses_observations_and_ancestors():
    assert capacity({'configured_limits': [2048, 512]}) == 'unresolved'
    e = dict(physical_ram=2000, available_ram=1500, swap=10000, configured_limits=[2048,512],
             observed_simultaneous_peak=800, retained_services_peak=200, headroom=300,
             ancestor_memory_limits=['max', 1800], source_compatible=True, measurement_sha256='a'*64)
    assert capacity(e) == 'supported'
    restrictive = copy.deepcopy(e); restrictive['ancestor_memory_limits'] = [1000]
    assert capacity(restrictive) == 'resize_decision_required'
    e['source_compatible'] = False
    assert capacity(e) == 'unresolved'


def test_hidden_root_and_root_at_jobs_rejected():
    r = receipt(); r['paths'].pop()
    with pytest.raises(ValueError): privileged_receipt(r, 'host', 'hash', now=1100)
    r = receipt(); r['sections']['at_queue']['sha256'] = hashlib.sha256(b'job').hexdigest()
    with pytest.raises(ValueError): privileged_receipt(r, 'host', 'hash', now=1100)


@pytest.mark.parametrize('key,value', [('headroom',-1), ('swap', 'huge'), ('retained_services_peak', -50), ('ancestor_memory_limits', [False]), ('measurement_sha256','unbound')])
def test_capacity_malformed_is_unresolved(key,value):
    e = dict(physical_ram=2000, available_ram=1500, swap=0, configured_limits=[2048,512],
             observed_simultaneous_peak=800, retained_services_peak=200, headroom=300,
             ancestor_memory_limits=['max'], source_compatible=True, measurement_sha256='a'*64)
    e[key] = value
    assert capacity(e) == 'unresolved'
