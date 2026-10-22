"""Private v3 control packets with external frozen proposal/inspection references.

This adapter connects the independently supervised runner without granting old
packets new authority. A passing packet covers only its explicitly bound cases.
"""
from pathlib import Path

from deploy.workload_installation import private
from deploy.workload_release import digest
from deploy.workload_v3 import validate_proposal, installed
from deploy.workload_watchdog import validate as validate_watchdog, execute as supervise
from mldsafail.evaluator.native_workload import require

SCHEMA = 'mldsafail.workload-control-packet.v3'


def reference(path):
    path = Path(path).absolute()
    raw, _ = private(path)
    return dict(path=str(path), sha256=digest(raw))


def load_reference(row):
    require(type(row) is dict and set(row)=={'path','sha256'} and
            type(row['path']) is str and Path(row['path']).is_absolute(),
            'acceptance_private_reference_invalid')
    raw, value = private(row['path'])
    require(digest(raw)==row['sha256'],'acceptance_reference_changed')
    return value


def validate(packet, *, now=None):
    require(type(packet) is dict and set(packet)=={'schema','stage','proposal','inspection','protocol'} and
            packet['schema']==SCHEMA and packet['stage'] in ('bootstrap','installed'),
            'acceptance_packet_schema')
    proposal=load_reference(packet['proposal']);validate_proposal(proposal)
    protocol=validate_watchdog(packet['protocol'])
    source=proposal['identities']
    expected_origin={'synthetic':'synthetic','local_linux':'local_linux','host_observation':'installed_native'}[source['origin']]
    require(protocol['origin']==expected_origin,'acceptance_origin_changed')
    bindings=dict(proposal=packet['proposal'],inspection=packet['inspection'],
        release_sha256=proposal['manifest_sha256'],hostname=source['host']['hostname'],
        uid=source['host']['uid'],boot_id=source['host']['boot_id'])
    require(protocol['identities'].get('installation')==bindings,'acceptance_installation_binding_changed')
    require(protocol['identities'].get('retained_services')==source['retained_services'],
            'acceptance_retained_binding_changed')
    if packet['stage']=='installed':
        observation=load_reference(packet['inspection'])
        installed(observation,proposal,now=now)
        require(protocol['fixture_cgroup'].startswith(source['installation']['heavy_path']+'/'),
                'acceptance_fixture_outside_owned_parent')
    else:
        require(packet['inspection'] is None,'acceptance_bootstrap_inspection_forbidden')
    return packet


def inspection_command(packet_path,proposal):
    release=Path(proposal['identities']['resources']['release']['path'])
    return ['/usr/bin/env','PYTHONPATH='+str(release/'bundle/src')+':'+str(release/'bundle'),
            'PYTHONDONTWRITEBYTECODE=1','PYTHONNOUSERSITE=1',str(release/'.venv/bin/python'),
            '-P','-m','scripts.workload_control_packet','--verify-installed','--packet',str(Path(packet_path).absolute())]


def verify_installed(packet_path):
    _,packet=private(packet_path);validate(packet)
    require(packet['stage']=='installed','acceptance_installed_packet_required')
    proposal=load_reference(packet['proposal'])
    from deploy.workload_installed import collect
    installed(collect(proposal),proposal)


def execute(packet_path,root,*,review_path=None,authorization_path=None):
    _,packet=private(packet_path)
    validate(packet)
    require(packet['stage']=='installed','acceptance_installed_packet_required')
    proposal=load_reference(packet['proposal'])
    require(packet['protocol']['startup']['argv']==inspection_command(packet_path,proposal),
            'acceptance_fresh_installed_startup_required')
    # Actual collection runs as startup inside the supervised packet deadline.
    # Native authority is checked and consumed by the independent supervisor.
    return supervise(packet['protocol'],root,review_path=review_path,authorization_path=authorization_path)
