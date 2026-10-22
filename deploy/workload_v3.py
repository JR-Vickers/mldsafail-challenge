"""V3 deployment compiler. Inputs are private; outputs propose, never authorize.

Historical v1/v2 packets keep their validators. Resources awaiting creation have
creation/preservation conditions and no invented kernel birth identities.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import shlex
import time

from deploy.workload_release import canonical, validate as validate_release
from deploy.workload_units import render_v3 as render
from mldsafail.evaluator.native_workload import require

BOOTSTRAP = 'mldsafail.workload-bootstrap-inspection.v3'
PROPOSAL = 'mldsafail.workload-bootstrap-proposal.v3'
INSTALLED = 'mldsafail.workload-installed-inspection.v3'
HEX = re.compile('[a-f0-9]{64}')


def absolute(value):
    require(type(value) is str and re.fullmatch(r'/(?:[A-Za-z0-9_./@:+-]|\\x[0-9A-Fa-f]{2})+',value) and
            '..' not in Path(value).parts and len(value)<4096,'v3_path_invalid')
    return value


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def fields(value, expected, reason):
    require(type(value) is dict and set(value) == set(expected.split()), reason)


def hashed(value):
    require(type(value) is str and HEX.fullmatch(value) is not None, 'v3_hash_invalid')
    return value


def observed(value):
    require(type(value) is dict and value.get('state') == 'observed', 'v3_resource_not_observed')
    require(type(value.get('device')) is int and value['device'] >= 0 and
            type(value.get('inode')) is int and value['inode'] > 0, 'v3_birth_missing')
    absolute(value['path'])


def resource(value, kind):
    require(value.get('state') in ('observed', 'proposed'), 'v3_resource_state_invalid')
    absolute(value['path'])
    if value['state'] == 'observed':
        observed(value)
    else:
        require(not ({'device', 'inode', 'mount_id', 'pid', 'start_ticks'} & set(value)),
                'v3_proposed_birth_forbidden')
        require(value.get('creation') and value.get('preserve'), 'v3_creation_conditions_missing:'+kind)


def mapping_valid(mapping, uid):
    fields(mapping, 'coordinator_container_uid supervisor_host_uid uid_map receipt_sha256', 'v3_uid_mapping_missing')
    hashed(mapping['receipt_sha256'])
    require(type(mapping['coordinator_container_uid']) is int and mapping['coordinator_container_uid'] >= 0 and
            mapping['supervisor_host_uid'] == uid, 'v3_uid_mapping_invalid')
    rows = mapping['uid_map']
    require(type(rows) is list and rows, 'v3_uid_map_empty')
    for row in rows:
        require(type(row) is list and len(row) == 3 and all(type(v) is int and v >= 0 for v in row)
                and row[2] > 0, 'v3_uid_map_invalid')
    for index, (inside, outside, count) in enumerate(rows):
        for other_inside, other_outside, other_count in rows[index+1:]:
            require(inside+count <= other_inside or other_inside+other_count <= inside, 'v3_uid_map_overlap')
            require(outside+count <= other_outside or other_outside+other_count <= outside, 'v3_uid_map_overlap')
    peer = [outside+mapping['coordinator_container_uid']-inside for inside, outside, count in rows
            if inside <= mapping['coordinator_container_uid'] < inside+count]
    require(peer == [uid], 'v3_peer_uid_mismatch')


def bootstrap(inspection, *, now=None):
    from deploy.workload_schedule_v3 import proposal as schedule,unit_name
    fields(inspection, 'schema origin captured_at host installation manifest recipe resources scheduling '
           'unit_directories permission_root containers inventory admission rollback retained_services uid_mapping',
           'v3_bootstrap_fields_missing')
    require(inspection['schema'] == BOOTSTRAP and inspection['origin'] in ('synthetic', 'local_linux', 'host_observation'),
            'v3_bootstrap_schema')
    now = time.time() if now is None else now
    require(type(inspection['captured_at']) in (int, float) and 0 <= now-inspection['captured_at'] <= 300,
            'v3_observation_expired')
    host = inspection['host']
    fields(host, 'hostname uid boot_id daemon_id runtime_identity user_manager', 'v3_host_fields')
    require(type(host['uid']) is int and host['uid'] > 0 and
            all(type(host[k]) is str and host[k] for k in ('hostname', 'boot_id', 'daemon_id')), 'v3_host_identity')
    runtime_identity=host['runtime_identity']
    fields(runtime_identity,'boot_id daemon_id daemon_mode daemon_birth daemon_executable socket_birth','v3_runtime_identity_missing')
    require(runtime_identity['boot_id']==host['boot_id'] and runtime_identity['daemon_id']==host['daemon_id'] and
            runtime_identity['daemon_mode']==dict(driver='systemd',version='2',rootless=True),'v3_runtime_identity_changed')
    require(all(type(runtime_identity['daemon_birth'].get(k)) is int and runtime_identity['daemon_birth'][k]>0
                for k in ('pid','start_ticks')),'v3_daemon_birth_missing')
    for row in (runtime_identity['daemon_executable'],runtime_identity['socket_birth']):
        require(type(row.get('device')) is int and type(row.get('inode')) is int and row['inode']>0,'v3_daemon_resource_birth_missing')
    observed(host['user_manager'])
    require(inspection['installation']['heavy_path']==host['user_manager']['path']+'/mldsafail.slice/mldsafail-heavy.slice',
            'v3_heavy_manager_hierarchy_changed')
    mapping_valid(inspection['uid_mapping'], host['uid'])
    installation = inspection['installation']
    units = render(installation)
    require(installation['uid'] == host['uid'], 'v3_install_uid_changed')
    manifest = validate_release(inspection['manifest'])
    require(manifest['units'] == ['generated/'+name for name in units] and
            all(manifest['files']['generated/'+name]['sha256'] == hashlib.sha256(data.encode()).hexdigest()
                for name, data in units.items()), 'v3_generated_units_changed')
    recipe = inspection['recipe']
    fields({k:v for k,v in recipe.items() if k not in ('bootstrap_interpreter','private_artifacts')}, 'bundle_root artifact_root interpreter installer dependency_plan installed_files '
           'configuration_sources configuration_templates activation_pointer proposal_path journal_root', 'v3_recipe_incomplete')
    for key in ('bundle_root', 'artifact_root', 'activation_pointer', 'proposal_path', 'journal_root'):
        absolute(recipe[key])
    for key in ('interpreter', 'installer'):
        fields(recipe[key], 'path sha256 bytes version', 'v3_bound_tool_missing')
        absolute(recipe[key]['path']); hashed(recipe[key]['sha256'])
        require(type(recipe[key]['bytes']) is int and recipe[key]['bytes'] > 0, 'v3_tool_empty')
    require(recipe['interpreter']['version']=='3.12.10','v3_native_interpreter_version_unsupported')
    if 'tools' in manifest:
        bootstrap=recipe.get('bootstrap_interpreter',{})
        fields(bootstrap,'path sha256 bytes version','v3_bootstrap_interpreter_missing')
        absolute(bootstrap['path']);hashed(bootstrap['sha256'])
        require(bootstrap['version'].startswith('3.12.') and type(bootstrap['bytes']) is int and bootstrap['bytes']>0,
                'v3_bootstrap_interpreter_invalid')
        root=Path(inspection['resources']['release']['path'])/'tools'
        for role,row in manifest['tools'].items():
            entry=row['members'][row['entrypoint']]
            require(recipe[role]==dict(path=str(root/role/row['entrypoint']),sha256=entry['sha256'],bytes=entry['bytes'],version=row['version']),
                    'v3_release_tool_recipe_changed')
        require(recipe['dependency_plan']==manifest['dependency_plan'],'v3_release_dependency_plan_changed')
    else:
        require(inspection['origin']=='synthetic','v3_complete_offline_tools_required')
    dependency = recipe['dependency_plan']
    fields(dependency, 'lock_sha256 wheels requirements_sha256 target', 'v3_dependency_plan_missing')
    hashed(dependency['lock_sha256']); hashed(dependency['requirements_sha256'])
    require(dependency['lock_sha256'] == manifest['files']['uv.lock']['sha256'] and
            set(dependency['wheels']) == set(manifest['dependencies']) and
            all(dependency['wheels'][name] == manifest['files'][name]['sha256'] for name in manifest['dependencies']),
            'v3_dependency_plan_changed')
    require(dependency['target'] == 'cpython-3.12-linux-x86_64-glibc2.28' and
            manifest['interpreter'].get('minimum_glibc') == '2.28', 'v3_dependency_target')
    require(type(recipe['installed_files']) is dict and recipe['installed_files'], 'v3_installed_file_expectations_missing')
    for name, record in recipe['installed_files'].items():
        from deploy.workload_release import relative
        relative(name)
        fields(record, 'sha256 bytes mode', 'v3_installed_file_expectation_invalid')
        hashed(record['sha256'])
        require(type(record['bytes']) is int and record['bytes']>=0,'v3_dependency_file_size_invalid')
        require(record['mode'] in (0o600, 0o644, 0o700, 0o755), 'v3_dependency_file_mode_invalid')
    release_path=Path(inspection['resources']['release']['path'])
    require(all(row['path']==str(release_path/'config'/(role+'.json')) for role,row in manifest['configurations'].items()) and
            installation['configuration']==manifest['configurations']['supervisor']['path'],'v3_configuration_final_paths_required')
    if inspection['origin']!='synthetic':
        require('images' in manifest,'v3_offline_images_required')
        from deploy.workload_configuration import validate_runtime_templates
        validate_runtime_templates(inspection)
    configs = recipe['configuration_sources']
    require(set(configs) == set(manifest['configurations']), 'v3_private_configuration_missing')
    for path in configs.values(): absolute(path)
    require(len(set(configs.values())) == 3, 'v3_private_configuration_alias')
    from deploy.workload_configuration import templates
    templates(inspection)
    resources = inspection['resources']
    fields(resources, 'release socket delegation output activation', 'v3_resources_missing')
    for kind, value in resources.items(): resource(value, kind)
    require(resources['release']['state'] == resources['socket']['state'] == 'proposed' and
            resources['release']['path'] == str(Path(installation['release']).parent) and
            resources['socket']['path'] == installation['gate_root']+'/supervisor.sock' and
            resources['delegation']['path'] == installation['heavy_path'] and
            resources['activation']['state'] == 'observed' and
            resources['activation']['path'] == recipe['activation_pointer'], 'v3_resource_paths_changed')
    require(installation['python'] == resources['release']['path']+'/.venv/bin/python' and
            installation['release'] == resources['release']['path']+'/bundle', 'v3_final_path_required')
    delegation = resources['delegation']
    require(set(delegation.get('controllers', [])) >= {'cpu', 'memory', 'pids'} and delegation.get('ancestors'),
            'v3_delegation_prerequisite_missing')
    expected_ancestors=[]
    parent=Path(delegation['path']).parent
    while True:
        expected_ancestors.append(str(parent))
        if str(parent)=='/sys/fs/cgroup':break
        require(parent!=parent.parent,'v3_cgroup_root_missing');parent=parent.parent
    require([row['path'] for row in delegation['ancestors']]==expected_ancestors,'v3_full_cgroup_ancestry_required')
    for index,parent in enumerate(delegation['ancestors']):
        resource(parent,'delegation_ancestor')
        require(set(parent.get('controllers', []))>={'cpu','memory','pids'} and
                type(parent.get('writable')) is bool and type(parent.get('retained_service_ancestor')) is bool,
                'v3_ancestor_permissions_missing')
        if parent['state']=='observed':
            from deploy.workload_installed import CGROUP_LIMITS
            require(type(parent.get('limits')) is dict and set(parent['limits'])==set(CGROUP_LIMITS) and
                    all(value is None or type(value) is str and '\n' not in value for value in parent['limits'].values()),
                    'v3_ancestor_limits_missing')
        if parent['state']=='proposed':
            require(index==0 and parent['path']==host['user_manager']['path']+'/mldsafail.slice' and
                    parent['writable'] is True and parent['retained_service_ancestor'] is False,
                    'v3_unapproved_ancestor_creation')
    require(delegation['ancestors'][0]['writable'] is True,'v3_delegation_parent_not_writable')
    output = resources['output']
    require(output.get('filesystem') in ('ext4', 'xfs') and type(output.get('bytes')) is int and
            0 < output['bytes'] <= 1024**3 and
            set(output.get('mount_options', [])) >= {'noexec', 'nosuid', 'nodev'}, 'v3_output_enforcement_missing')
    if output['state'] == 'proposed':
        require(output['filesystem'] == 'ext4' and output.get('exclusive_backing_file') is True,
                'v3_output_allocation_not_exclusive')
        absolute(output['backing_file'])
    admission = inspection['admission']
    fields(admission, 'memory_available backing_free', 'v3_admission_missing')
    from deploy.workload_release import remaining_allocation
    allocation = (output['bytes'] if output['state'] == 'proposed' else 0)+remaining_allocation(manifest,recipe['installed_files'])
    require(type(admission['memory_available']) is int and admission['memory_available'] >= 1024**3 and
            type(admission['backing_free']) is int and admission['backing_free']-allocation >= 5*1024**3,
            'v3_admission_floor')
    inventory = inspection['inventory']
    fields({key:value for key,value in inventory.items() if key not in ('manager_units','execution_references','absent_files')}, 'receipt_sha256 errors truncations unknown_owners unresolved_references raw_sha256 original_files manager_settings',
           'v3_scheduling_inventory_missing')
    hashed(inventory['receipt_sha256']); hashed(inventory['raw_sha256'])
    if inspection['origin']!='synthetic':
        from deploy.workload_registry import validate as validate_registry
        require('manager_units' in inventory,'v3_manager_registry_missing');validate_registry(inspection)
        from deploy.workload_registry import REFERENCE_FIELDS
        refs=inventory.get('execution_references',{})
        require(set(refs)==set(inspection['scheduling']['owners']) and
                all(set(row)==set(REFERENCE_FIELDS) and all(type(value) is str for value in row.values()) for row in refs.values()),
                'v3_execution_references_missing')
        require(type(inventory.get('absent_files')) is list,'v3_absent_reference_files_missing')
        for path in inventory['absent_files']:absolute(path)
        from deploy.workload_registry import validate_reference_files
        validate_reference_files(inspection)
    require(type(inventory['original_files']) is dict and inventory['original_files'],'v3_original_scheduling_files_missing')
    for path,digest in inventory['original_files'].items(): absolute(path);hashed(digest)
    require(all(type(inventory[k]) is int and inventory[k] == 0 for k in
                ('errors', 'truncations', 'unknown_owners', 'unresolved_references')), 'v3_scheduling_inventory_open')
    require(set(inventory['manager_settings'])==set(inspection['scheduling']['units']),'v3_original_manager_settings_missing')
    for unit,row in inventory['manager_settings'].items():
        fields(row,'ActiveState UnitFileState Restart Triggers','v3_original_manager_setting_fields')
        require(all(type(value) is str for value in row.values()),'v3_manager_setting_invalid')
        owner=inspection['scheduling']['owners'][unit]
        require((row['ActiveState']=='active')==owner['active'] and
                row['UnitFileState'].startswith('enabled')==owner['enabled'] and
                row['UnitFileState'].startswith('masked')==owner['masked'] and
                (row['Restart'] or 'no')==owner['restart'] and
                sorted(row['Triggers'].split())==sorted(unit_name(trigger,inspection['scheduling']['owners'][trigger]) for trigger in owner['triggers']),'v3_manager_settings_inconsistent')
    scheduling = schedule(inspection['scheduling'], host['uid'], inspection['permission_root'], inspection['unit_directories'])
    require(inspection['scheduling']['receipt_sha256'] == inventory['receipt_sha256'], 'v3_inventory_receipt_changed')
    containers = inspection['containers']
    require(type(containers) is list and len({r['id'] for r in containers}) == len(containers), 'v3_container_inventory_invalid')
    for row in containers:
        fields(row, 'id daemon_id owner_uid restart_policy running disposition image created_at started_at process_birth', 'v3_container_owner_missing')
        hashed(row['id'])
        require(re.fullmatch('sha256:[a-f0-9]{64}',row['image']) is not None and
                all(type(row[k]) is str and row[k] for k in ('created_at','started_at')),'v3_container_birth_missing')
        require((type(row['process_birth']) is dict and all(type(row['process_birth'].get(k)) is int and row['process_birth'][k]>0 for k in ('pid','start_ticks')))
                if row['running'] else row['process_birth'] is None,'v3_container_process_birth_missing')
        require(row['daemon_id'] == host['daemon_id'] and row['owner_uid'] == host['uid'] and
                row['restart_policy'] in ('no','always','unless-stopped','on-failure') and
                type(row['running']) is bool and row['disposition'] in ('pause','retain'), 'v3_container_policy_invalid')
    rollback = inspection['rollback']
    fields(rollback, 'release manifest_sha256 configuration_hashes coordinator_image schema_sha256 '
           'installed_schema_sha256 compatibility_receipt_sha256 compatibility_receipt_path verified_files target manifest installed_files python_sha256 schema', 'v3_rollback_missing')
    absolute(rollback['release'])
    absolute(rollback['compatibility_receipt_path'])
    validate_release(rollback['manifest'])
    require(sha(rollback['manifest'])==rollback['manifest_sha256'] and rollback['installed_files'] and
            rollback['manifest']['coordinator_image']==rollback['coordinator_image'],'v3_rollback_manifest_changed')
    hashed(rollback['python_sha256'])
    fields(rollback['schema'],'container_id database username','v3_schema_binding_missing')
    require(rollback['schema']['container_id']==inspection['retained_services']['database']['id'] and
            all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,62}',rollback['schema'][key]) for key in ('database','username')),
            'v3_schema_binding_changed')
    for key in ('manifest_sha256','schema_sha256','installed_schema_sha256','compatibility_receipt_sha256'): hashed(rollback[key])
    require(rollback['schema_sha256'] == rollback['installed_schema_sha256'] and rollback['verified_files'] is True and
            rollback['target'] == resources['activation'].get('target') and
            rollback['release'] == rollback['target'] and rollback['release'] != resources['release']['path'],
            'v3_rollback_incompatible')
    require(re.fullmatch('sha256:[a-f0-9]{64}', rollback['coordinator_image']) is not None and
            set(rollback['configuration_hashes']) == {'supervisor','native','controller'}, 'v3_rollback_artifacts_missing')
    for value in rollback['configuration_hashes'].values(): hashed(value)
    require(type(inspection['retained_services']) is dict and
            set(inspection['retained_services']) >= {'web','database','proxy'}, 'v3_retained_services_missing')
    for row in inspection['retained_services'].values():
        require(row.get('running') is True and row.get('id') and row.get('image') and row.get('started_at'),
                'v3_retained_service_birth_missing')
    from deploy.workload_installation import compile_steps
    from deploy.workload_prerequisites import proposal as prerequisites
    result = dict(schema=PROPOSAL, stage='bootstrap', identities=deepcopy(inspection),
                  manifest_sha256=sha(manifest), units=units, scheduling=scheduling, prerequisites=prerequisites(inspection),
                  preparation_blockers=[], execution_requirements=['independent_review_of_exact_proposal',
                    'exact_byte_owner_authorization', 'fresh_host_admission_and_identity_revalidation'],
                  execution_authority=False, installed_acceptance=False)
    result['steps'] = compile_steps(result)
    result['commands'] = {phase: list(dict.fromkeys(shlex.join(step['argv']) for step in result['steps'] if step['phase'] == phase))
                          for phase in ('install','rollback')}
    result['proposal_sha256'] = sha(result)
    return result


def validate_proposal(proposal):
    require(type(proposal) is dict and proposal.get('schema') == PROPOSAL, 'v3_proposal_schema')
    expected = bootstrap(proposal['identities'], now=proposal['identities']['captured_at'])
    require(proposal == expected, 'v3_frozen_proposal_changed')
    return proposal


def installed(inspection, proposal, *, now=None):
    validate_proposal(proposal)
    fields(inspection, 'schema origin captured_at proposal_sha256 host resources release_sha256 '
           'configuration_hashes dependency_files units uid_mapping paused retained_services scheduling supervisor',
           'v3_installed_fields_missing')
    require(inspection['schema'] == INSTALLED and inspection['origin'] == proposal['identities']['origin'] and
            inspection['proposal_sha256'] == sha(proposal), 'v3_installed_proposal_changed')
    require(0 <= (time.time() if now is None else now)-inspection['captured_at'] <= 300, 'v3_installed_observation_expired')
    source = proposal['identities']
    from deploy.workload_configuration import hashes as configuration_hashes
    require(inspection['host'] == source['host'] and inspection['uid_mapping'] == source['uid_mapping'], 'v3_installed_host_changed')
    require(inspection['paused'] is True and inspection['retained_services'] == source['retained_services'],
            'v3_installed_not_paused_or_retained_changed')
    require(inspection['release_sha256'] == proposal['manifest_sha256'] and
            inspection['configuration_hashes'] == configuration_hashes(source,inspection['resources']) and
            inspection['dependency_files'] == source['recipe']['installed_files'] and
            inspection['units'] == {name: hashlib.sha256(data.encode()).hexdigest() for name,data in proposal['units'].items()},
            'v3_installed_bytes_changed')
    require(set(inspection['resources']) == set(source['resources']), 'v3_installed_resources_missing')
    for name, row in inspection['resources'].items():
        observed(row)
        previous = source['resources'][name]
        if previous['state'] == 'observed' and name not in ('activation','delegation'):
            require(row == previous, 'v3_observed_resource_changed:'+name)
        else:
            require(row['path'] == previous['path'], 'v3_installation_transition_path_changed:'+name)
        if name == 'activation':
            require(row.get('target') == source['resources']['release']['path'], 'v3_activation_target_changed')
        if name == 'delegation':
            if previous['state']=='observed':
                require(all(row.get(key)==value for key,value in previous.items() if key!='enforced_limits'),'v3_observed_delegation_changed')
            limits=row.get('enforced_limits',{})
            require(set(limits)=={'memory.max','memory.swap.max','pids.max','cpu.max'} and
                    limits['memory.max'].isdigit() and 0<int(limits['memory.max'])<=source['installation']['memory_ceiling'] and
                    limits['memory.swap.max']=='0' and limits['pids.max']=='448' and limits['cpu.max']=='100000 100000',
                    'v3_installed_aggregate_limits_changed')
            require(set(row.get('controllers', []))>={'cpu','memory','pids'} and
                    len(row.get('ancestors',[]))==len(previous['ancestors']),'v3_installed_delegation_changed')
            for actual,expected in zip(row['ancestors'],previous['ancestors']):
                observed(actual)
                if expected['state']=='observed':require(actual==expected,'v3_observed_ancestor_changed')
                else:require(actual['path']==expected['path'],'v3_proposed_ancestor_path_changed')
        if name == 'output':
            require(all(row.get(key) == previous[key] for key in ('filesystem','bytes','mount_options')) and
                    type(row.get('mount_id')) is int and row['mount_id'] > 0, 'v3_installed_output_changed')
    supervisor = inspection['supervisor']
    fields(supervisor, 'pid start_ticks boot_id uid cgroup', 'v3_supervisor_birth_missing')
    require(all(type(supervisor[k]) is int and supervisor[k] > 0 for k in ('pid','start_ticks')) and
            supervisor['boot_id'] == source['host']['boot_id'] and supervisor['uid'] == source['host']['uid'] and
            not Path(supervisor['cgroup']).is_relative_to(source['installation']['heavy_path']), 'v3_supervisor_identity_changed')
    require(inspection['scheduling'] == dict(permission_files_absent=True, computational_units_stopped=True,
                computational_containers_stopped=True, restart_policies_inhibited=True,
                dropin_hashes={row['path']:hashlib.sha256(row['contents'].encode()).hexdigest()
                              for row in proposal['scheduling']['resources']}), 'v3_installed_inhibition_missing')
    return dict(schema='mldsafail.workload-installed-acceptance.v3', stage='installed',
                identities=deepcopy(inspection), proposal_sha256=sha(proposal), execution_authority=False,
                preparation_blockers=[], execution_requirements=['separate_exact_native_acceptance_authorization'],
                installed_acceptance=False, commands={})
