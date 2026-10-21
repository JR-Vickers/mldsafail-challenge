"""Owner-specific persistent inhibition proposal, without execution authority.

Drop-ins require an owner-specific, persistent permission file. Unlike runtime masks they survive
reboot and work for units with existing unit files. Unknown scheduler adapters
remain blockers. Removing inhibition requires a later owner-reviewed operation.
"""
import re
import shlex
from pathlib import Path

from deploy.workload_preparation import manager_prefix, scheduling_commands
from mldsafail.evaluator.native_workload import require


def proposal(record, uid, gate, unit_directories):
    # Reuse all owner, trigger and disposition checks in the historical renderer.
    scheduling_commands(record, uid)
    gate = Path(gate)
    require(gate.is_absolute() and '..' not in gate.parts and
            re.fullmatch(r'/[A-Za-z0-9_./-]+', str(gate)) is not None,
            'scheduling_gate_path_invalid')
    require(record['unclassified'] == 0 and record['references_open'] == 0 and
            re.fullmatch('[a-f0-9]{64}', record['receipt_sha256']) is not None and
            set(record['computational_units']) <= set(record['units']) and
            all(re.fullmatch(r'[A-Za-z0-9@_.:-]+\.(service|timer|socket|path)', unit)
                for unit in record['units']), 'scheduling_closure_required')
    owners = record['owners']
    resources, commands, observations = [], [], []
    seen = set()
    for unit in record['computational_units']:
        owner = owners[unit]
        require(owner['manager'] == 'system' or owner['uid'] == uid,
                'scheduling_cross_owner_gate_visibility_requires_adapter')
        key = f"{owner['manager']}:{owner['uid']}"
        require(key in unit_directories, 'scheduling_unit_directory_missing')
        directory = Path(unit_directories[key])
        require(directory.is_absolute() and '..' not in directory.parts and
                re.fullmatch(r'/[A-Za-z0-9_./-]+', str(directory)) is not None,
                'scheduling_unit_directory_invalid')
        # Explicit paths must match their owner; never write another manager's
        # overrides through a convenient shared directory.
        if owner['manager'] == 'system':
            require(directory == Path('/etc/systemd/system'), 'scheduling_system_directory_invalid')
        else:
            require(str(directory).endswith('/.config/systemd/user'), 'scheduling_user_directory_invalid')
        path = directory/(unit+'.d')/'90-mldsafail-paused.conf'
        permission = str(gate / (owner['manager']+'-'+str(owner['uid'])+'.allow'))
        resources.append(dict(state='proposed', path=str(path), owner_uid=owner['uid'],
                              contents='[Unit]\nConditionPathExists='+permission+'\n',
                              precondition='absent_destination_preserve_original_unit_and_dropins'))
        prefix = manager_prefix(owner, uid)
        if key not in seen:
            commands.append(shlex.join([*prefix, 'daemon-reload']))
            seen.add(key)
        commands.append(shlex.join([*prefix, 'stop', unit]))
        observations.append(shlex.join([*prefix, 'show', unit,
                                       '--property=ActiveState,Conditions,DropInPaths']))
    return dict(schema='mldsafail.workload-scheduling-proposal.v3',
                execution_authority=False,
                gate=dict(state='proposed', path=str(gate), mode=0o700,
                          permission_files='must_remain_absent_no_creation_authorized',
                          precondition='exclusive_creation_persistent_owner_private_directory'),
                resources=resources, commands_after_exclusive_resource_creation=commands,
                observation_commands=observations,
                rollback='preserve_absent_permissions_and_dropins_keep_computation_stopped',
                restoration='separate_review_and_owner_authorization_required')
