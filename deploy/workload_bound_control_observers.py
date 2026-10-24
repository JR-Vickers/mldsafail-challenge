"""Read-only native observations derived from an installed packet's owned scope.

These observers inject nothing, grant no authority and publish no passing control
receipt. A runner must perform its separately authorized injection and compare
these raw observations. They cannot be satisfied with ordinary fixture files.
"""
from pathlib import Path
import sys
import time

from deploy.workload_acceptance_packet import validate, load_reference
from deploy.workload_installed import cgroup_observation, scheduling
from mldsafail.evaluator.native_workload import birth, process_birth, require, values


def kernel_scope(protocol):
    require(sys.platform == 'linux', 'bound_observer_requires_linux')
    scope = Path(protocol['fixture_cgroup'])
    require(scope.is_relative_to('/sys/fs/cgroup') and scope != Path('/sys/fs/cgroup'),
            'bound_observer_fixture_scope_required')
    # Checking only a filename would allow ordinary files to masquerade as kernel
    # controller observations. The real mount and fixed namespace are required.
    mounts = Path('/proc/self/mountinfo').read_text().splitlines()
    require(any(row.split()[4] == '/sys/fs/cgroup' and
                row.split(' - ', 1)[1].split()[0] == 'cgroup2' for row in mounts),
            'bound_observer_cgroup2_mount_required')
    expected = protocol['identities'].get('fixture_birth')
    require(type(expected) is dict and birth(scope) == expected,
            'bound_observer_fixture_replaced')
    return scope


def process_placement(scope, expected):
    require(type(expected) is list and len(expected) >= 3 and
            len({row['pid'] for row in expected}) == len(expected),
            'bound_observer_process_inventory_required')
    observations = []
    for item in expected:
        require(set(item) == {'pid', 'start_ticks'} and type(item['pid']) is int and
                item['pid'] > 0 and type(item['start_ticks']) is int and item['start_ticks'] > 0,
                'bound_observer_process_identity_required')
        require(process_birth(item['pid']) == item, 'bound_observer_process_replaced')
        raw = (Path('/proc')/str(item['pid'])/'cgroup').read_text()
        rows = raw.splitlines()
        require(len(rows) == 1 and rows[0].startswith('0::/'), 'bound_observer_process_cgroup_invalid')
        path = Path('/sys/fs/cgroup')/rows[0].removeprefix('0::/').lstrip('/')
        require(process_birth(item['pid']) == item, 'bound_observer_process_replaced')
        observations.append(dict(**item, cgroup=str(path), raw_cgroup=raw,
            outside_scope=not path.is_relative_to(scope)))
    return dict(processes=observations, inspected_processes=len(observations),
                outside_heavy=sum(row['outside_scope'] for row in observations))


def observe(packet, control, scenario):
    validate(packet)
    require(packet['stage'] == 'installed' and packet['protocol']['origin'] in
            ('local_linux', 'installed_native'), 'bound_observer_installed_context_required')
    require((control, scenario) in {
        ('common_cgroup', 'controller_worker_descendants'),
        ('delegation', 'missing_controller'), ('delegation', 'inspected_limits'),
        ('scheduling_exclusion', 'retained_trigger_inventory')}, 'bound_observer_case_unsupported')
    protocol = packet['protocol']; scope = kernel_scope(protocol)
    before = birth(scope); started = time.monotonic_ns()
    if control == 'common_cgroup':
        raw = process_placement(scope, protocol['identities'].get('processes'))
    elif control == 'delegation':
        raw = dict(scope=cgroup_observation(scope), events=values(scope/'cgroup.events'))
    else:
        proposal = load_reference(packet['proposal'])
        raw = dict(scheduling=scheduling(proposal),
            inventory=proposal['identities']['scheduling'],
            inventory_disposition='frozen_classification_checked_against_installed_observations')
    require(birth(scope) == before, 'bound_observer_fixture_replaced')
    return dict(schema='mldsafail.bound-control-observation.v1',
        origin=protocol['origin'], control=control, scenario=scenario,
        fixture_birth=before, started_monotonic_ns=started,
        finished_monotonic_ns=time.monotonic_ns(), raw=raw,
        disposition='observation_only_injection_and_assertions_still_required',
        execution_authority=False)
