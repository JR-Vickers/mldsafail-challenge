"""Checked installation effect inventory and protocol-four recovery policy.

An entry enumerates internal effects, not permission to execute or replay them.
External effects have no generic absence/replay exception. Complete acknowledged
operations are accepted only through LinuxBackend's operation-specific observer
and postcondition validator. Partial external operations preserve their resources.
"""
from mldsafail.evaluator.native_workload import require

# action: (observer, ((effect, kind), ...)).  The same inhibition operations are
# deliberately shared by install and rollback, retaining their original receipts.
OPERATIONS = {
    'snapshot': ('snapshot', (('private_snapshot_files', 'exclusive_file'),)),
    'quiesce_supervisor': ('quiesce_supervisor', (('handoff_stop_and_descendant_cleanup', 'service_manager'),)),
    'create_release': ('create_release', (('exclusive_release_directory', 'exclusive_directory'),)),
    'copy_bundle': ('copy_bundle', (('bundle_and_parent_directories', 'exclusive_directory'), ('verified_bundle_files', 'exclusive_file'))),
    'tools': ('tools', (('tools_parent_directory', 'exclusive_directory'), ('verified_tool_trees', 'exclusive_tree'))),
    'dependencies': ('dependencies', (('offline_venv_construction', 'dependency_tree'), ('offline_wheel_installation', 'dependency_tree'), ('project_entrypoints', 'exclusive_file'))),
    'images': ('images', (('private_docker_client_configuration', 'exclusive_file'), ('daemon_image_load_and_tags', 'daemon_image'))),
    'inhibit_scheduling': ('inhibit_scheduling', (('permission_gate_directory', 'exclusive_directory'), ('owner_dropin_directories', 'exclusive_directory'), ('owner_inhibition_files', 'exclusive_file'), ('manager_reload_stop_disable_mask', 'service_manager'))),
    'inhibit_containers': ('inhibit_containers', (('container_restart_policy', 'container'), ('container_stop', 'container'))),
    'units': ('units', (('replacement_temporary_files', 'exclusive_file'), ('unit_atomic_replacement', 'unit'), ('user_manager_reload', 'service_manager'))),
    'prerequisites': ('prerequisites', (('output_backing_allocation', 'exclusive_file'), ('output_mountpoint', 'exclusive_directory'), ('output_ext4_format', 'format'), ('root_mount_unit', 'unit'), ('root_manager_reload', 'service_manager'), ('mount_enable_and_activation', 'mount'), ('mount_ownership', 'mount'), ('delegation_slice_start', 'service_manager'), ('delegation_controllers', 'cgroup'))),
    'configurations': ('configurations', (('configuration_parent_directories', 'exclusive_directory'), ('private_configuration_files', 'exclusive_file'))),
    'verify_release': ('verify_release', (('verify_frozen_release', 'read_only'),)),
    'activate': ('activate', (('activation_candidate_symlink', 'activation'), ('activation_atomic_exchange', 'activation'), ('preserved_previous_pointer', 'activation'))),
    'supervisor_unit': ('supervisor_unit', (('replacement_temporary_files', 'exclusive_file'), ('supervisor_unit_atomic_replacement', 'unit'), ('user_manager_reload', 'service_manager'))),
    'enable_supervisor': ('enable_supervisor', (('verify_generated_supervisor', 'read_only'), ('exclusive_supervisor_enable_marker', 'exclusive_file'))),
    'start_paused': ('start_paused', (('supervisor_manager_start', 'service_manager'), ('supervisor_socket_and_runtime_state', 'runtime'))),
    'verify_paused': ('verify_paused', (('verify_paused_process_and_socket', 'read_only'),)),
    'stop_supervisor': ('stop_supervisor', (('supervisor_manager_stop', 'service_manager'), ('supervisor_enable_marker_removal', 'exclusive_file'))),
    'verify_cleanup': ('verify_cleanup', (('verify_descendants_transactions_and_cgroups', 'read_only'),)),
    'restore_activation': ('restore_activation', (('rollback_candidate_symlink', 'activation'), ('rollback_atomic_exchange', 'activation'), ('preserved_installed_pointer', 'activation'))),
    'restore_units': ('restore_units', (('restoration_temporary_files_and_owner', 'unit'), ('restore_or_remove_owned_units', 'unit'), ('user_manager_reload', 'service_manager'))),
    'verify_rollback': ('verify_rollback', (('verify_compatible_rollback_and_inhibition', 'read_only'),)),
}
KINDS = frozenset(('read_only', 'exclusive_file', 'exclusive_directory', 'exclusive_tree',
    'dependency_tree', 'daemon_image', 'service_manager', 'container', 'unit', 'format',
    'mount', 'cgroup', 'activation', 'runtime'))


def inventory():
    from deploy.workload_installation import INSTALL, ROLLBACK
    require(set(OPERATIONS) == set(INSTALL) | set(ROLLBACK), 'recovery_operation_inventory_incomplete')
    rows = []
    for phase, actions in (('install', INSTALL), ('rollback', ROLLBACK)):
        for action in actions:
            observer, effects = OPERATIONS[action]
            require(observer == action and effects and len({name for name, _ in effects}) == len(effects),
                    'recovery_effect_inventory_invalid')
            for effect, kind in effects:
                require(kind in KINDS, 'recovery_effect_kind_unsupported')
                rows.append(dict(step=phase+':'+action, operation=action, effect=effect, kind=kind,
                    observer='LinuxBackend.observe:'+observer,
                    mutation=kind != 'read_only',
                    unacknowledged='repeat_read_only_verification' if kind == 'read_only' else
                        'operation_specific_proof_or_preserve_and_block',
                    acknowledged='require_identity_and_complete_operation_postconditions'))
    require(len({(row['step'], row['effect']) for row in rows}) == len(rows),
            'recovery_effect_inventory_duplicate')
    return rows


def transition(step):
    rows = [row for row in inventory() if row['step'] == step['id']]
    require(rows and all(row['operation'] == step['action'] for row in rows),
            'recovery_operation_unsupported')
    return dict(operation=step['action'], effects=[row['effect'] for row in rows],
                postcondition='complete_operation_specific_observation')


def disposition(effect, *, acknowledged, identity_matches, postconditions, safe_absence=False):
    """Pure conservative decision used by inventory tests and recovery reporting.

    safe_absence must come from an operation-specific proof; it is intentionally
    ignored for images, formats, mounts and service-manager effects.
    """
    require(effect in inventory(), 'recovery_effect_not_in_inventory')
    if not effect['mutation']:
        return 'verify_read_only'
    if acknowledged:
        return 'completed' if identity_matches and postconditions else 'replaced_or_incomplete_preserve_and_block'
    if safe_absence and effect['kind'] in ('exclusive_file', 'exclusive_directory'):
        return 'proven_absent_requires_fresh_execution_authority'
    return 'unacknowledged_preserve_and_block'


PREREQUISITE_RESOURCES = frozenset(('output_backing','output_mountpoint','output_format',
    'output_mount_unit','output_daemon_reload','output_mount_activation','output_mount_owner',
    'delegation_start','delegation_controllers'))


def observe_prerequisite(resource,source,command):
    """Re-read the exact identity-bound observations used at prerequisite effects.

    This function only observes. A matching format header or manager setting
    cannot authorize replay; partial prerequisite operations remain blocked.
    """
    from pathlib import Path
    import os
    from deploy.workload_installation import identity
    from deploy.workload_release import digest
    from deploy.workload_prerequisites import mount_unit, mount_namespace
    require(resource in PREREQUISITE_RESOURCES,'recovery_prerequisite_resource_unsupported')
    output=source['resources']['output'];root=Path(source['resources']['delegation']['path'])
    if resource=='delegation_start':return identity(root)
    if resource=='delegation_controllers':
        return dict(identity=identity(root),subtree_control=(root/'cgroup.subtree_control').read_text().strip())
    backing=Path(output['backing_file']);mount=Path(output['path'])
    if resource=='output_backing':return identity(backing,content=False)
    if resource in ('output_mountpoint','output_mount_owner'):return identity(mount)
    if resource=='output_format':
        before=identity(backing,content=False)
        require(before['state']=='observed' and not backing.is_symlink(),'recovery_backing_not_regular')
        descriptor=os.open(backing,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(descriptor,'rb') as stream:header=stream.read(4096)
        require(identity(backing,content=False)==before,'recovery_backing_changed_during_observation')
        return dict(identity=before,header_sha256=digest(header))
    name,_=mount_unit(output);unit=Path('/etc/systemd/system')/name
    if resource=='output_mount_unit':return identity(unit,content=False)
    if resource=='output_daemon_reload':return mount_namespace(name,command)
    if resource=='output_mount_activation':
        return dict(unit=mount_namespace(name,command),
                    link=identity(Path('/etc/systemd/system/local-fs.target.wants')/name),directory=identity(mount))
    require(False,'recovery_prerequisite_resource_unsupported')
