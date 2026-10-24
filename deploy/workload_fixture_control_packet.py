"""Frozen one-case packets for the existing disposable fixture authority.

No packet field is an execution grant. Execution still requires the original
root-owned VM marker, immutable source, component review, lifecycle lock and
single-use worker request. Installed-native owner authority is never inferred.
"""
from pathlib import Path
import os
import re

from deploy.workload_acceptance_packet import reference,load_reference
from deploy.workload_installation import exclusive,private,identity
from deploy.workload_release import canonical,digest
from deploy.workload_v3 import validate_proposal,installed
from mldsafail.evaluator.native_workload import require

SCHEMA='mldsafail.fixture-control-packet.v1'
FIELDS={'schema','fixture_only','execution_authority','fixture','proposal','inspection','control','scenario','output','envelope_seconds'}
ENVELOPE=dict(startup=30,case=90,cleanup=45,postflight=15)


def validate(packet,*,now=None):
    require(type(packet) is dict and set(packet)==FIELDS and packet['schema']==SCHEMA and
        packet['fixture_only'] is True and packet['execution_authority'] is False and
        packet['envelope_seconds']==ENVELOPE,'fixture_control_packet_schema')
    manifest=load_reference(packet['fixture']);proposal=load_reference(packet['proposal'])
    observation=load_reference(packet['inspection']);validate_proposal(proposal)
    root=Path(packet['fixture']['path']).parent
    require(Path(packet['fixture']['path'])==root/'manifest.json' and
        manifest.get('schema')=='mldsafail.installation-fixture.v1' and manifest.get('fixture_only') is True and
        manifest.get('root')==identity(root) and manifest.get('execution_authority') is False and
        manifest.get('vps_authority') is False and re.fullmatch('[a-f0-9]{32}',manifest.get('generation','')),
        'fixture_control_packet_namespace_changed')
    require(packet['proposal']['path']==str(root/'proposal.json') and
        proposal['identities']['origin']=='local_linux','fixture_control_packet_proposal_scope')
    paths=manifest['final_paths'];source=proposal['identities']
    require(all(paths.get(name)==str(root/name) for name in
        ('release','previous','frozen','output','gate','proposal.json')) and
        source['resources']['release']['path']==paths['release'] and
        source['rollback']['release']==paths['previous'] and
        source['recipe']['bundle_root']==paths['frozen'] and
        source['recipe']['proposal_path']==paths['proposal.json'], 'fixture_control_packet_final_paths_changed')
    require(observation.get('schema')=='mldsafail.installation-fixture.v1' and
        observation.get('fixture_only') is True and observation.get('generation')==manifest['generation'] and
        observation.get('manifest_sha256')==packet['fixture']['sha256'] and
        observation.get('runtime_suitability_verified') is True and observation.get('execution_authority') is False,
        'fixture_control_packet_inspection_binding_changed')
    installed(observation['resources']['installed'],proposal,now=now)
    output=Path(packet['output'])
    require(output.is_absolute() and str(output)==str(output.resolve(strict=False)) and output.parent==root/'artifacts' and
        re.fullmatch('case-[a-f0-9]{32}\\.json',output.name) is not None,'fixture_control_packet_output_scope')
    from deploy.workload_fixture_controls import CASES
    require((packet['control'],packet['scenario']) in CASES,'fixture_control_packet_case_unimplemented')
    return packet


def prepare(manifest_path,proposal_path,inspection_path,*,control,scenario,output,now=None):
    packet=dict(schema=SCHEMA,fixture_only=True,execution_authority=False,
        fixture=reference(manifest_path),proposal=reference(proposal_path),inspection=reference(inspection_path),
        control=control,scenario=scenario,output=str(output),envelope_seconds=ENVELOPE.copy())
    return validate(packet,now=now)


def execute(packet_path,control,scenario,output):
    """Use the fixture's existing lock/worker, not packet-manufactured authority."""
    raw,packet=private(packet_path);validate(packet)
    require((control,scenario,str(Path(output).absolute()))==(packet['control'],packet['scenario'],packet['output']),
        'fixture_control_packet_selection_changed')
    root=Path(packet['fixture']['path']).parent;output=Path(packet['output'])
    from scripts.workload_installation_fixture import Fixture,lifecycle_lock
    from scripts.rehearse_workload_installation_fixture import component_review
    with lifecycle_lock(root) as fd:
        fixture=Fixture(root);fixture.lock_fd=fd;fixture.require_target();component_review(fixture)
        # Revalidate exact private references while holding generation ownership.
        validate(packet)
        require(fixture.binding==packet['fixture']['sha256'],'fixture_control_packet_generation_changed')
        require(fixture.proposal()[0]==private(packet['proposal']['path'],parse=False)[0],
            'fixture_control_packet_proposal_changed')
        require(fixture.deadline()>=180,'fixture_control_insufficient_attempt_budget')
        parent=output.parent.stat()
        require(parent.st_uid==os.getuid() and not parent.st_mode&0o077,'fixture_control_packet_private_output_required')
        exclusive(output,canonical(dict(schema='mldsafail.fixture-control-case-intent.v1',
            packet_sha256=digest(raw),generation=fixture.manifest['generation'],control=control,scenario=scenario)))
        try:
            receipt=fixture.control(control,scenario)
        except BaseException as error:
            exclusive(output.with_name(output.name+'.failure.json'),canonical(dict(
                packet_sha256=digest(raw),type=type(error).__name__,message=str(error),ownership='blocked_preserve')))
            raise
        require(receipt.get('fixture_only') is True and receipt.get('generation')==fixture.manifest['generation'] and
            receipt.get('control')==control and receipt.get('scenario')==scenario and
            receipt.get('origin')=='local_linux' and receipt.get('installed_native_eligible') is False,
            'fixture_control_packet_receipt_changed')
        exclusive(output.with_name(output.name+'.result.json'),canonical(dict(packet_sha256=digest(raw),receipt=receipt)))
        return receipt
