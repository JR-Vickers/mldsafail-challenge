"""Offline packet rendering never contacts or changes a host."""
from copy import deepcopy

import pytest

from deploy.workload_deployment import inspected_commands
from deploy.workload_units import render
from mldsafail.evaluator.workload import WorkloadBlocked
from scripts.prepare_workload_packet import prepare
from pathlib import Path


def inspection():
    installation = dict(python='/srv/release/.venv/bin/python', release='/srv/release',
        configuration='/srv/workload/supervisor.json', gate_root='/srv/workload',
        heavy_path='/sys/fs/cgroup/user.slice/mldsafail.slice/mldsafail-heavy.slice',
        memory_ceiling=2*1024**3, uid=1000, unit_directory='/home/operator/.config/systemd/user')
    service = dict(id='a'*64, image='sha256:'+'b'*64, started_at='birth', restart_policy='no', running=True)
    return dict(schema='mldsafail.workload-host-inspection.v1', hostname='fixture', uid=1000,
        boot_id='boot', daemon_id='daemon', captured_at=1000, installation=installation,
        delegation=dict(path=installation['heavy_path'], device=1, inode=2, controllers=['cpu','memory','pids'],
                        ancestors=[dict(path='/sys/fs/cgroup/user.slice',device=1,inode=3,memory_max='max')]),
        socket=dict(path='/srv/workload/supervisor.sock', uid=1000, directory_mode=0o700, mode=0o600, device=1,inode=4),
        retained_services={key:dict(service) for key in ('web','database','proxy','coordinator')},
        scheduling=dict(unclassified=0,references_open=0,receipt_sha256='c'*64,
                        units=['coordinator.service','retained.timer'], computational_units=['coordinator.service']),
        rollback=dict(release='/srv/rollback', python='/srv/rollback/.venv/bin/python',
                      configuration='/srv/rollback/production.env', active_configuration='/srv/current/production.env',
                      coordinator_image='sha256:'+'d'*64, configuration_sha256='e'*64,
                      schema_sha256='f'*64,installed_schema_sha256='f'*64,
                      compatibility_receipt_sha256='0'*64, coordinator_unit='coordinator.service'),
        original_settings={key:dict(active=True,enabled=True,masked=False) for key in ('coordinator.service','retained.timer')},
        acceptance_inputs=dict(native_configuration='/srv/workload/native.json',controller_configuration='/srv/workload/controller.json',fence_root='/srv/fence',database_credentials='/srv/credentials.json',client_journal='/srv/client',result_receipt='/srv/receipt.json',signing_key='/srv/key'), output_volume=dict(path='/srv/output',filesystem='ext4',bytes=1024**3,mount_options=['noexec','nosuid','nodev'],mount_id=42,source_device='/dev/loop9',backing_free=6*1024**3), release_files={'/srv/release/source.py':'a'*64}, worker_environment={'image_id':'sha256:'+'b'*64},
        configuration_files={path:dict(sha256='a'*64,uid=1000,mode=0o600,bytes=100) for path in ('/srv/workload/supervisor.json','/srv/workload/native.json','/srv/workload/controller.json')})


def test_units_keep_supervisor_and_independent_cleanup_outside_heavy():
    units = render(inspection()['installation'])
    service = units['mldsafail-workload-supervisor.service']
    assert 'Slice=app.slice' in service
    assert 'ExecStopPost=' in service and 'workload_service cleanup' in service
    assert 'WatchdogSec=5s' in service
    assert 'MemorySwapMax=0' in units['mldsafail-heavy.slice']
    assert 'TasksMax=448' in units['mldsafail-heavy.slice']


def test_complete_inspection_renders_exact_paused_recovery_commands():
    packet = inspected_commands(inspection(), now=1100)
    assert packet['execution_authority'] is False
    assert all('coordinator.service' not in command for command in packet['commands']['restoration'] if ' start ' in command)
    assert any('retained.timer' in command for command in packet['commands']['restoration'])
    assert any('update --restart=no' in command for command in packet['commands']['rollback'])
    assert packet['commands']['cleanup'][-1].startswith('/srv/release/.venv/bin/python')


@pytest.mark.parametrize('mutation', [
    lambda record: record.pop('rollback'),
    lambda record: record['delegation'].update(controllers=['cpu']),
    lambda record: record['socket'].update(uid=0),
    lambda record: record['scheduling'].update(references_open=1),
    lambda record: record['rollback'].update(installed_schema_sha256='1'*64),
    lambda record: record.update(captured_at=-90000),
    lambda record: record['installation'].update(python='/bin/python;touch /bad'),
])
def test_incomplete_or_changed_identities_never_render_commands(mutation):
    record = inspection(); mutation(record)
    with pytest.raises((WorkloadBlocked, KeyError)): inspected_commands(record, now=1100)


def test_offline_review_without_host_identities_has_no_executable_commands():
    packet = prepare(Path(__file__).resolve().parents[1])
    assert packet['deployment'] is None
    assert 'installation' in packet['missing_inspection_fields']
    assert packet['execution_authority'] is False
    assert all('implementation_missing' not in blocker for blocker in packet['blockers'])
    assert packet['native_acceptance']['requires_separate_owner_authorization']
