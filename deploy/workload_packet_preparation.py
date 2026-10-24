"""Preparation-only acceptance plans. Missing host facts never become identities.

These documents are deliberately not executable control packets or authority.
They freeze the one-case command and references for subsequent independent review.
"""
from pathlib import Path
import time

from deploy.workload_acceptance_packet import reference, load_reference
from deploy.workload_release import canonical, digest
from deploy.workload_v3 import validate_proposal, installed
from mldsafail.evaluator.native_workload import require

ENVELOPE = dict(startup=30, case=90, cleanup=45, postflight=15)
SCHEMA = 'mldsafail.workload-control-preparation.v1'


def remaining_attempt(attempt, *, now_monotonic=None, boot_id=None):
    """One attempt owns all split packets, including the cleanup reserve."""
    now = time.monotonic() if now_monotonic is None else now_monotonic
    require(type(attempt) is dict and set(attempt)=={'started_monotonic','boot_id','generation'},
            'packet_attempt_binding_missing')
    require(type(attempt['started_monotonic']) in (int,float) and attempt['generation'] and
            type(attempt['boot_id']) is str and attempt['boot_id']==boot_id,
            'packet_attempt_identity_changed')
    elapsed = now-attempt['started_monotonic']
    require(0<=elapsed<1500, 'packet_attempt_expired')
    return 1500-elapsed


def prepare(proposal_path, inspection_path, *, packet_path, output_path, control, scenario,
            attempt=None, now=None, now_monotonic=None):
    from deploy.workload_controls import SCENARIOS
    require(control in SCENARIOS and scenario in SCENARIOS[control], 'packet_scenario_unsupported')
    proposal_ref=reference(proposal_path); proposal=load_reference(proposal_ref)
    validate_proposal(proposal)
    inspection_ref=reference(inspection_path) if inspection_path is not None else None
    blockers=[]
    if inspection_ref is None:
        blockers.append('fresh_installed_inspection_required')
    else:
        installed(load_reference(inspection_ref),proposal,now=now)
    source=proposal['identities']; release=Path(source['resources']['release']['path'])
    packet_path=Path(packet_path); output_path=Path(output_path)
    require(packet_path.is_absolute() and output_path.is_absolute() and
            str(packet_path)==str(packet_path.resolve(strict=False)) and
            str(output_path)==str(output_path.resolve(strict=False)), 'packet_paths_must_be_exact_absolute')
    require(packet_path!=output_path and packet_path not in output_path.parents,
            'packet_output_overlaps_packet')
    origin={'synthetic':'synthetic','local_linux':'local_linux','host_observation':'installed_native'}[source['origin']]
    files=source['manifest']['files']
    required=['scripts/workload_control_case.py','deploy/workload_control_runners.py',
              'deploy/workload_controls.py','deploy/workload_watchdog.py',
              'deploy/workload_acceptance_packet.py']
    hashes={name:files[name]['sha256'] for name in required if name in files}
    for name in required:
        if name not in hashes:blockers.append('frozen_runner_source_missing:'+name)
    command=['/usr/bin/env','PYTHONPATH='+str(release/'bundle/src')+':'+str(release/'bundle'),
             'PYTHONDONTWRITEBYTECODE=1','PYTHONNOUSERSITE=1',str(release/'.venv/bin/python'),
             '-P','-m','scripts.workload_control_case','--packet',str(packet_path),
             '--control',control,'--scenario',scenario,'--output',str(output_path)]
    # Lifecycle commands need generation-owned fixture bindings. Do not invent
    # a scope, journal, ownership receipt, daemon birth or cleanup command.
    blockers.extend(['generation_owned_fixture_and_lifecycle_bindings_required',
                     'bound_cleanup_and_postflight_commands_required',
                     'matching_runner_context_acceptance_required'])
    if attempt is None:
        blockers.append('existing_fixture_attempt_budget_required')
    else:
        require(remaining_attempt(attempt,now_monotonic=now_monotonic,
                                  boot_id=source['host']['boot_id'])>=sum(ENVELOPE.values()),
                'packet_does_not_fit_remaining_attempt')
    return dict(schema=SCHEMA,purpose='preparation_only',execution_authority=False,
        proposal=proposal_ref,inspection=inspection_ref,origin=origin,
        selection=[dict(control=control,scenario=scenario)],case_order=[control+'/'+scenario],
        envelope_seconds=ENVELOPE.copy(),timeout_seconds=sum(ENVELOPE.values()),
        case_command=command,source_hashes=hashes,
        configuration_hashes=source['manifest'].get('private_artifacts',{}),
        resource_identities=source['resources'],attempt=attempt,
        blockers=sorted(set(blockers)),execution_requirements=[
            'complete_executable_packet','independent_exact_packet_review',
            'separate_exact_owner_authorization','single_use_authority_claim'])


def binding(plan):
    require(plan.get('schema')==SCHEMA and plan.get('execution_authority') is False,
            'packet_preparation_schema')
    return digest(canonical(plan))
