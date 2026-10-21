"""Versioned bootstrap proposal and installed observation validation.

Neither stage grants execution authority. Historical v1 packets retain their
original contract; proposed births cannot be promoted into installed evidence.
"""
import hashlib
import json
import re
import shlex
import stat
from pathlib import Path

from deploy.workload_deployment import REQUIRED, _commands, inspected_commands
from deploy.workload_units import absolute
from mldsafail.evaluator.native_workload import require


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def manager_prefix(owner, uid):
    prefix = ['/usr/bin/systemctl']
    if owner['manager'] == 'system':
        return ['/usr/bin/sudo', '-n', *prefix]
    prefix += ['--user']
    if owner['uid'] != uid:
        return ['/usr/bin/sudo', '-n', '-u', owner['account'], '/usr/bin/env',
                f"XDG_RUNTIME_DIR=/run/user/{owner['uid']}", *prefix]
    return prefix


def scheduling_commands(record, uid):
    require(set(record) == {'unclassified', 'references_open', 'receipt_sha256', 'units',
                            'computational_units', 'owners'}, 'workload_scheduling_owners_missing')
    require(set(record['owners']) == set(record['units']) and
            len(record['units']) == len(set(record['units'])), 'workload_scheduling_owner_ambiguous')
    commands = dict(maintenance=[], restoration=[])
    for unit in record['units']:
        owner = record['owners'][unit]
        require(set(owner) == {'manager', 'account', 'uid', 'restart', 'triggers', 'disposition',
                               'active', 'enabled', 'masked'}, 'workload_scheduling_owner_incomplete')
        require(re.fullmatch('[a-z_][a-z0-9_-]*', owner['account']) and
                type(owner['uid']) is int and owner['uid'] >= 0 and
                all(type(owner[key]) is bool for key in ('active', 'enabled', 'masked')),
                'workload_scheduling_account_invalid')
        require(owner['restart'] in ('no', 'always', 'on-failure', 'on-success', 'on-abnormal',
                                    'on-abort', 'on-watchdog') and
                type(owner['triggers']) is list and set(owner['triggers']) <= set(record['units']) and
                owner['disposition'] in ('pause', 'retain'), 'workload_scheduling_disposition_missing')
        require((unit in record['computational_units']) == (owner['disposition'] == 'pause'),
                'workload_scheduling_disposition_changed')
        # A retained timer/socket/path must never reactivate a computational unit.
        if owner['disposition'] == 'pause':
            require(all(record['owners'][trigger]['disposition'] == 'pause'
                        for trigger in owner['triggers']), 'workload_scheduling_trigger_unfenced')
        manager = owner['manager']
        require(manager in ('system', 'user'), 'workload_non_systemd_trigger_requires_reviewed_adapter')
        require(manager != 'system' or owner['uid'] == 0, 'workload_system_manager_owner_invalid')
        prefix = manager_prefix(owner, uid)
        def command(*args): return shlex.join([*prefix, *args, unit])
        if owner['disposition'] == 'pause':
            # Runtime masks fence indirect starts and survive supervisor restart.
            commands['maintenance'] += [command('mask', '--runtime'), command('stop'), command('is-active')]
        commands['restoration'] += [command('mask' if owner['masked'] else 'unmask', '--runtime')]
        # Restoration intentionally never starts computational scheduling.
        if owner['active'] and owner['disposition'] == 'retain':
            commands['restoration'].append(command('start'))
    return commands


def bootstrap_commands(inspection, *, now=None):
    if isinstance(inspection, dict) and inspection.get('schema') == 'mldsafail.workload-bootstrap-inspection.v3':
        from deploy.workload_v3 import bootstrap
        return bootstrap(inspection, now=now)
    require(type(inspection) is dict and set(inspection) == REQUIRED | {'uid_mapping'},
            'workload_bootstrap_inspection_incomplete')
    mapping = inspection['uid_mapping']
    require(set(mapping) == {'coordinator_container_uid', 'supervisor_host_uid', 'uid_map', 'receipt_sha256'},
            'workload_uid_mapping_missing')
    require(type(mapping['coordinator_container_uid']) is int and mapping['coordinator_container_uid'] >= 0 and
            mapping['supervisor_host_uid'] == inspection['uid'] and
            re.fullmatch('[a-f0-9]{64}', mapping['receipt_sha256']), 'workload_uid_mapping_invalid')
    matches = []
    for row in mapping['uid_map']:
        require(type(row) is list and len(row) == 3 and all(type(v) is int and v >= 0 for v in row) and row[2] > 0,
                'workload_uid_mapping_invalid')
        inside, outside, count = row
        if inside <= mapping['coordinator_container_uid'] < inside+count:
            matches.append(outside+mapping['coordinator_container_uid']-inside)
    require(matches == [inspection['uid']], 'workload_coordinator_peer_uid_mismatch')
    core = {key: value for key, value in inspection.items() if key != 'uid_mapping'}
    result = _commands(core, now=now, bootstrap=True)
    # All three configurations must be independently bound, not aliases.
    paths = [core['installation']['configuration'], core['acceptance_inputs']['native_configuration'],
             core['acceptance_inputs']['controller_configuration']]
    require(len(set(paths)) == 3, 'workload_configuration_alias')
    require(set(core['original_settings']) == set(core['scheduling']['units']), 'workload_original_settings_missing')
    for unit, original in core['original_settings'].items():
        require(original == {key: core['scheduling']['owners'][unit][key] for key in ('active', 'enabled', 'masked')},
                'workload_original_settings_changed')
    coordinator = core['rollback']['coordinator_unit']
    stop = shlex.join([*manager_prefix(core['scheduling']['owners'][coordinator], core['uid']), 'stop', coordinator])
    result['commands']['rollback'][1] = stop
    # The historical rollback commands fence the coordinator and restore its
    # configuration only. They do not restore executable release/image bytes.
    # Never publish those incomplete commands as a runnable v2 rollback.
    result['rollback_fence_commands'] = result['commands'].pop('rollback')
    result['rollback_disposition'] = 'blocked_until_exact_release_and_image_restoration_bound'
    result['command_fragments'] = result.pop('commands')
    result['commands'] = {}
    result.update(schema='mldsafail.workload-bootstrap-proposal.v2' , identities=inspection,
                  proposal_sha256=sha(inspection), stage='bootstrap',
                  blockers=['independent_review_required', 'exact_packet_owner_authorization_required',
                            'fresh_release_dependency_configuration_installation_required',
                            'exact_release_image_rollback_restoration_required'],
                  installed_acceptance=False)
    return result


def installed_commands(inspection, proposal, *, now=None):
    if isinstance(proposal, dict) and proposal.get('schema') == 'mldsafail.workload-bootstrap-proposal.v3':
        from deploy.workload_v3 import installed
        return installed(inspection, proposal, now=now)
    require(type(proposal) is dict and proposal.get('schema') == 'mldsafail.workload-bootstrap-proposal.v2' and
            proposal.get('stage') == 'bootstrap' and proposal.get('proposal_sha256') == sha(proposal['identities']),
            'workload_bootstrap_binding_changed')
    # Revalidate rather than trusting editable generated command bytes.
    rebuilt = bootstrap_commands(proposal['identities'], now=proposal['identities']['captured_at'])
    require(proposal == rebuilt, 'workload_bootstrap_commands_changed')
    require(set(inspection) == REQUIRED | {'installed'} and
            inspection['schema'] == 'mldsafail.workload-installed-inspection.v2', 'workload_installed_inspection_incomplete')
    require(set(inspection['socket']) == {'path', 'uid', 'directory_mode', 'mode', 'device', 'inode'},
            'workload_installed_socket_not_observed')
    observed = inspection['installed']
    require(set(observed) == {'proposal_sha256', 'supervisor', 'configuration_hashes', 'release_hashes',
                             'paused', 'uid_mapping', 'dependency_receipt_sha256'}, 'workload_installed_evidence_missing')
    require(observed['proposal_sha256'] == sha(proposal) and observed['paused'] is True and
            re.fullmatch('[a-f0-9]{64}', observed['dependency_receipt_sha256']), 'workload_installed_binding_changed')
    proposed = proposal['identities']
    for key in ('hostname', 'uid', 'boot_id', 'daemon_id', 'installation', 'release_files', 'configuration_files',
                'worker_environment', 'acceptance_inputs', 'rollback', 'scheduling', 'original_settings',
                'retained_services', 'delegation', 'output_volume'):
        require(inspection[key] == proposed[key], 'workload_installed_identity_changed:'+key)
    require(observed['uid_mapping'] == proposed['uid_mapping'], 'workload_installed_uid_mapping_changed')
    require(observed['configuration_hashes'] == {p: r['sha256'] for p, r in inspection['configuration_files'].items()} and
            observed['release_hashes'] == inspection['release_files'], 'workload_installed_artifacts_changed')
    supervisor = observed['supervisor']
    require(set(supervisor) == {'pid', 'start_ticks', 'boot_id', 'uid', 'cgroup'} and
            all(type(supervisor[k]) is int and supervisor[k] > 0 for k in ('pid', 'start_ticks')) and
            supervisor['uid'] == inspection['uid'] and supervisor['boot_id'] == inspection['boot_id'],
            'workload_supervisor_birth_missing')
    absolute(supervisor['cgroup'])
    require(not Path(supervisor['cgroup']).is_relative_to(inspection['installation']['heavy_path']),
            'workload_supervisor_inside_heavy')
    core = {key: value for key, value in inspection.items() if key != 'installed'}
    core['schema'] = 'mldsafail.workload-host-inspection.v1'
    result = inspected_commands(core, now=now)
    result['command_fragments'] = {'native_acceptance': result['commands']['native_acceptance']}
    result['commands'] = {}
    result['blockers'] = list(proposal['blockers']) + ['complete_native_control_runner_coverage_required']
    result.update(schema='mldsafail.workload-installed-acceptance.v2', stage='installed', identities=inspection,
                  proposal_sha256=sha(proposal), installed_acceptance=False)
    return result


def verify_installed_files(inspection):
    """Fresh local kernel/filesystem observations, called only on installed host."""
    from mldsafail.evaluator.native_workload import process_birth
    socket = inspection['socket']
    st = Path(socket['path']).lstat()
    parent = Path(socket['path']).parent.lstat()
    require(stat.S_ISSOCK(st.st_mode) and not stat.S_ISLNK(parent.st_mode) and
            st.st_uid == socket['uid'] and parent.st_uid == socket['uid'] and
            stat.S_IMODE(st.st_mode) == socket['mode'] and stat.S_IMODE(parent.st_mode) == socket['directory_mode'] and
            st.st_dev == socket['device'] and st.st_ino == socket['inode'], 'workload_installed_socket_changed')
    for name, record in inspection['configuration_files'].items():
        path = Path(name); before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_uid == record['uid'] and
                stat.S_IMODE(before.st_mode) == record['mode'] and before.st_size == record['bytes'] and
                hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'] and before == path.lstat(),
                'workload_installed_configuration_changed')
    for name, digest in inspection['release_files'].items():
        path = Path(name); before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and hashlib.sha256(path.read_bytes()).hexdigest() == digest and
                before == path.lstat(), 'workload_installed_release_changed')
    expected = inspection['installed']['supervisor']
    birth = process_birth(expected['pid'])
    require(birth['pid'] == expected['pid'] and birth['start_ticks'] == expected['start_ticks'] and
            Path('/proc/sys/kernel/random/boot_id').read_text().strip() == expected['boot_id'] and
            Path('/proc/'+str(expected['pid'])).stat().st_uid == expected['uid'], 'workload_installed_supervisor_changed')
    path = Path('/proc/'+str(expected['pid'])+'/cgroup').read_text().strip()
    require(path == '0::/'+str(Path(expected['cgroup']).relative_to('/sys/fs/cgroup')),
            'workload_installed_supervisor_cgroup_changed')
