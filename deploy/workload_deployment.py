"""Offline exact installation/recovery command packet; no host mutations."""
import hashlib
from pathlib import Path
import re
import shlex
import time

from deploy.workload_units import absolute, render
from mldsafail.evaluator.native_workload import require

REQUIRED = {'schema', 'hostname', 'uid', 'boot_id', 'daemon_id', 'captured_at', 'installation',
            'delegation', 'socket', 'retained_services', 'scheduling', 'rollback', 'original_settings', 'release_files', 'worker_environment', 'configuration_files', 'acceptance_inputs', 'output_volume'}


def inspected_commands(inspection, *, now=None):
    """Historical v1 installed-only contract; never accepts bootstrap proposals."""
    return _commands(inspection, now=now, bootstrap=False)


def _commands(inspection, *, now=None, bootstrap=False):
    now = time.time() if now is None else now
    require(type(inspection) is dict and set(inspection) == REQUIRED and
            inspection['schema'] == ('mldsafail.workload-bootstrap-inspection.v2' if bootstrap else 'mldsafail.workload-host-inspection.v1'), 'workload_host_inspection_incomplete')
    require(isinstance(inspection['hostname'], str) and inspection['hostname'] and
            type(inspection['uid']) is int and inspection['uid'] > 0 and
            inspection['boot_id'] and inspection['daemon_id'] and
            0 <= now-inspection['captured_at'] < 86400, 'workload_host_inspection_stale')
    installation = inspection['installation']
    units = render(installation)
    require(installation['uid'] == inspection['uid'], 'workload_service_uid_changed')
    delegation = inspection['delegation']
    require(delegation['path'] == installation['heavy_path'] and
            {'cpu', 'memory', 'pids'} <= set(delegation['controllers']) and
            type(delegation['device']) is int and type(delegation['inode']) is int and
            delegation['inode'] > 0 and delegation['ancestors'], 'workload_delegation_uninspected')
    for scope in delegation['ancestors']:
        absolute(scope['path'])
        require(type(scope['device']) is int and type(scope['inode']) is int and scope['inode'] > 0 and
                (scope['memory_max'] == 'max' or type(scope['memory_max']) is int and scope['memory_max'] > 0),
                'workload_ancestor_uninspected')
    socket = inspection['socket']
    if bootstrap:
        require(socket == {'path': str(Path(installation['gate_root'])/'supervisor.sock'),
                           'state': 'proposed'}, 'workload_bootstrap_socket_must_be_proposed')
    else:
        require(socket['path'] == str(Path(installation['gate_root'])/'supervisor.sock') and
                socket['uid'] == inspection['uid'] and socket['directory_mode'] == 0o700 and
                socket['mode'] == 0o600 and socket['device'] >= 0 and socket['inode'] > 0,
                'workload_socket_identity_uninspected')
    output = inspection['output_volume']
    absolute(output['path'])
    require(output['filesystem'] in ('ext4', 'xfs') and type(output['bytes']) is int and 0 < output['bytes'] <= 1024**3 and
            {'noexec', 'nosuid', 'nodev'} <= set(output['mount_options']) and
            type(output['mount_id']) is int and output['mount_id'] > 0 and output['source_device'] and
            output['backing_free'] >= 5*1024**3, 'workload_generation_quota_uninspected')
    retained = inspection['retained_services']
    require(set(retained) >= {'web', 'database', 'proxy', 'coordinator'}, 'workload_retained_inventory_missing')
    for service in retained.values():
        require(re.fullmatch('[a-f0-9]{64}', service['id']) and
                re.fullmatch('sha256:[a-f0-9]{64}', service['image']) and service['started_at'] and
                type(service['running']) is bool and
                service['restart_policy'] in ('no', 'always', 'unless-stopped', 'on-failure'), 'workload_service_birth_missing')
    scheduling = inspection['scheduling']
    if bootstrap:
        from deploy.workload_preparation import scheduling_commands
        owner_commands = scheduling_commands(scheduling, inspection['uid'])
    require(scheduling['unclassified'] == 0 and scheduling['references_open'] == 0 and
            re.fullmatch('[a-f0-9]{64}', scheduling['receipt_sha256']) and scheduling['units'] and
            set(scheduling['computational_units']) <= set(scheduling['units']), 'workload_scheduling_closure_missing')
    for unit in scheduling['units']:
        require(re.fullmatch(r'[A-Za-z0-9@_.:-]+\.(service|timer|socket|path)', unit), 'workload_scheduling_unit_invalid')
    rollback = inspection['rollback']
    for key in ('release', 'python', 'configuration', 'active_configuration'): absolute(rollback[key])
    require(re.fullmatch('sha256:[a-f0-9]{64}', rollback['coordinator_image']) and
            re.fullmatch('[a-f0-9]{64}', rollback['configuration_sha256']) and
            rollback['schema_sha256'] == rollback['installed_schema_sha256'] and
            rollback['compatibility_receipt_sha256'] and rollback['coordinator_unit'] in scheduling['units'],
            'workload_compatible_rollback_uninspected')
    require(inspection['original_settings'] and inspection['release_files'], 'workload_restoration_identity_missing')
    for name, digest in inspection['release_files'].items():
        absolute(name)
        require(re.fullmatch('[a-f0-9]{64}', digest), 'workload_release_bytes_missing')
    require(inspection['configuration_files'], 'workload_configuration_bytes_missing')
    for name, record in inspection['configuration_files'].items():
        absolute(name)
        require(set(record) == {'sha256', 'uid', 'mode', 'bytes'} and record['uid'] == inspection['uid'] and
                record['mode'] == 0o600 and type(record['bytes']) is int and 0 < record['bytes'] <= 1024**2 and
                re.fullmatch('[a-f0-9]{64}', record['sha256']), 'workload_configuration_identity_invalid')
    require(installation['configuration'] in inspection['configuration_files'], 'workload_supervisor_configuration_uninspected')
    inputs=inspection['acceptance_inputs']
    require(set(inputs)=={'native_configuration','controller_configuration','fence_root','database_credentials','client_journal','result_receipt','signing_key'}, 'workload_acceptance_inputs_missing')
    for path in inputs.values(): absolute(path)
    require(all(inputs[key] in inspection['configuration_files'] for key in ('native_configuration','controller_configuration')), 'workload_acceptance_configuration_uninspected')
    quote = shlex.quote
    systemctl = ['/usr/bin/systemctl', '--user']
    def command(arguments): return ' '.join(quote(value) for value in arguments)
    python, config = installation['python'], installation['configuration']
    cleanup = [python, '-m', 'mldsafail.evaluator.workload_service', 'cleanup', '--configuration', config]
    # The command list is proposed only. Separate owner authorization binds these
    # exact bytes plus the inspected snapshot before installation or acceptance.
    commands = {
        'maintenance': [command([*systemctl, 'stop', *scheduling['units']]),
                        command([*systemctl, 'is-active', *scheduling['units']])],
        'install': [command(['/usr/bin/install', '-m', '600', str(Path(installation['release'])/'generated'/name),
                             str(Path(installation['unit_directory'])/name)]) for name in units],
        'start_paused': [command([*systemctl, 'daemon-reload']),
                         command([*systemctl, 'start', 'mldsafail-workload-supervisor.service'])],
        'cleanup': [command([*systemctl, 'stop', 'mldsafail-workload-supervisor.service']), command(cleanup)],
        'rollback': [command(cleanup), command([*systemctl, 'stop', rollback['coordinator_unit']]),
                     command(['/usr/bin/docker', '--host', 'unix:///run/user/'+str(inspection['uid'])+'/docker.sock',
                              'update', '--restart=no', retained['coordinator']['id']]),
                     command(['/usr/bin/install', '-m', '600', rollback['configuration'], rollback['active_configuration']])],
        'restoration': [],
    }
    for unit, setting in inspection['original_settings'].items():
        require(unit in scheduling['units'] and set(setting) == {'active', 'enabled', 'masked'} and
                all(type(value) is bool for value in setting.values()), 'workload_original_settings_missing')
        commands['restoration'].append(command([*systemctl, 'mask' if setting['masked'] else 'unmask', unit]))
        commands['restoration'].append(command([*systemctl, 'enable' if setting['enabled'] else 'disable', unit]))
        # Computational scheduling stays stopped. Explicit restoration authority
        # may start retained non-computational units after postflight only.
        if setting['active'] and unit not in scheduling['computational_units']:
            commands['restoration'].append(command([*systemctl, 'start', unit]))
    commands['native_acceptance'] = [command([python, '-m', 'deploy.workload_native_acceptance',
        '--packet', str(Path(installation['release'])/'generated/native-acceptance.json'),
        '--authorization', str(Path(installation['release'])/'generated/native-authorization.json')])]
    if bootstrap:
        commands.update(owner_commands)
        commands.pop('native_acceptance')
    return dict(identities=inspection, units=units, commands=commands, execution_authority=False,
                expected_statuses={'maintenance_is_active': [3]},
                installation_prerequisites=['inspected_delegation', 'existing_bounded_persistent_volume', 'retained_compatible_rollback'],
                restoration_precondition='verified_absent_containers_empty_owned_cgroups_fresh_preflight',
                rollback_disposition='restore_inspected_compatible_release_with_scheduling_paused')
