"""Preparation-only compiler for one installed-native watchdog packet.

Facts are private observations, never inferred identities or execution authority.
Missing facts produce a review report without an executable packet.
"""
from pathlib import Path
import re
import time

from deploy.workload_acceptance_packet import SCHEMA,reference,load_reference,inspection_command
from deploy.workload_control_registry import get_runner
from deploy.workload_release import canonical,digest
from deploy.workload_v3 import validate_proposal,installed
from deploy.workload_watchdog import validate as validate_protocol
from mldsafail.evaluator.native_workload import require

FACTS='mldsafail.native-control-packet-facts.v1'
ENVELOPE=dict(startup=30,case=90,cleanup=45,postflight=15)


def required_source():
    from scripts.rehearse_workload_installation_fixture import REVIEW_FILES
    return set(REVIEW_FILES)|{'deploy/workload_native_packet.py','deploy/workload_native_context.py',
        'deploy/workload_native_supervision.py','deploy/workload_native_attempt.py','deploy/workload_native_resources.py','deploy/workload_watchdog.py',
        'scripts/workload_control_case.py','src/mldsafail/evaluator/native_workload.py',
        'src/mldsafail/evaluator/workload.py','src/mldsafail/evaluator/workload_socket.py',
        'src/mldsafail/web/models.py'}


def native_command(packet_path,proposal,control,scenario,output,phase):
    require(phase in ('case','cleanup','postflight'),'native_packet_phase_invalid')
    get_runner(control,scenario)
    from scripts.workload_control_case import case_command
    return [*case_command(packet_path,proposal,control,scenario,output),'--native-phase',phase]


def prepare(proposal_path,inspection_path,*,packet_path,watchdog_root,control,scenario,generation,attempt_generation,facts_path=None,now=None):
    get_runner(control,scenario);now=time.time() if now is None else now
    require(type(generation) is str and re.fullmatch('[a-f0-9]{32}',generation),'native_packet_generation_invalid')
    require(type(attempt_generation) is str and re.fullmatch('[a-f0-9]{32}',attempt_generation),'native_packet_attempt_generation_required')
    proposal_ref=reference(proposal_path);proposal=load_reference(proposal_ref);validate_proposal(proposal)
    inspection_ref=reference(inspection_path) if inspection_path else None
    blockers=[];source=proposal['identities']
    for name in sorted(required_source()):
        if name not in source['manifest']['files']:blockers.append('frozen_native_source_missing:'+name)
    if source['origin']!='host_observation':blockers.append('installed_native_host_observation_required')
    if inspection_ref is None:blockers.append('fresh_installed_inspection_required')
    else:installed(load_reference(inspection_ref),proposal,now=now)
    packet_path=Path(packet_path);watchdog_root=Path(watchdog_root)
    require(all(path.is_absolute() and '..' not in path.parts for path in (packet_path,watchdog_root)),
        'native_packet_absolute_paths_required')
    require(watchdog_root.parent==Path(source['recipe']['journal_root']) and watchdog_root.name=='native-control-'+generation,
        'native_packet_output_namespace_changed')
    facts_ref=reference(facts_path) if facts_path else None;facts=load_reference(facts_ref) if facts_ref else None
    if facts is None:blockers.append('native_control_scope_journal_and_image_facts_required')
    else:
        require(type(facts) is dict and set(facts)<= {'schema','origin','captured_at','host','authority_journal','fixture_cgroup','postgres_image','execution_mode_fact'} and
            facts.get('schema')==FACTS and facts.get('origin')=='host_observation','native_packet_facts_schema')
        for key in ('host','captured_at','authority_journal','fixture_cgroup','postgres_image'):
            if key not in facts:blockers.append('native_control_fact_missing:'+key)
        if 'host' in facts:
            require(facts['host']=={key:source['host'][key] for key in ('hostname','uid','boot_id')},'native_packet_fact_host_changed')
        if 'captured_at' in facts:
            require(type(facts['captured_at']) in (int,float) and 0<=now-facts['captured_at']<=900,'native_packet_facts_expired')
        if 'authority_journal' in facts:
            row=facts['authority_journal']
            require(row.get('state')=='observed' and row.get('path')==source['recipe']['journal_root'] and
                row.get('uid')==source['host']['uid'] and row.get('mode')==0o700 and
                all(type(row.get(k)) is int and row[k]>0 for k in ('device','inode')),'native_packet_authority_journal_fact_invalid')
        if 'fixture_cgroup' in facts:
            row=facts['fixture_cgroup']
            require(set(row)=={'path','device','inode','populated','processes'} and type(row['path']) is str and
                row['path'].startswith(source['installation']['heavy_path']+'/') and '..' not in Path(row['path']).parts and
                str(Path(row['path']))==row['path'] and type(row['populated']) is int and row['populated']==0 and row['processes']==[] and
                all(type(row[k]) is int and row[k]>0 for k in ('device','inode')),'native_packet_scope_fact_invalid')
        if 'postgres_image' in facts:
            require(type(facts['postgres_image']) is str and re.fullmatch('sha256:[a-f0-9]{64}',facts['postgres_image']),
                'native_packet_postgres_image_fact_invalid')
    if facts is not None and 'execution_mode_fact' in facts:
        mode=load_reference(facts['execution_mode_fact'])
        require(mode.get('schema')=='mldsafail.fixture-execution-mode.v1' and mode.get('mode') in ('native','emulated') and
            mode.get('hostname')==source['host']['hostname'] and mode.get('boot_id')==source['host']['boot_id'],
            'native_packet_execution_mode_fact_changed')
        if control=='native_linux_acceptance' and mode['mode']!='native':blockers.append('native_execution_mode_is_emulated')
    if control=='native_linux_acceptance' and (facts is None or 'execution_mode_fact' not in facts):
        blockers.append('reviewed_native_execution_mode_fact_required')
    if blockers:
        return dict(schema='mldsafail.native-control-preparation.v1',execution_authority=False,
            proposal=proposal_ref,inspection=inspection_ref,facts=facts_ref,selection=[dict(control=control,scenario=scenario)],
            envelope_seconds=ENVELOPE.copy(),blockers=sorted(set(blockers)),packet=None)
    context_root=watchdog_root/'context';output=context_root/'artifacts'/('case-'+generation+'.json')
    context=dict(generation=generation,attempt_generation=attempt_generation,watchdog_root=str(watchdog_root),postgres_image=facts['postgres_image'],
        control=control,scenario=scenario,case_output=str(output),facts=facts_ref,
        global_hold=dict(state='proposed',path=source['installation']['gate_root']+'/native-control-hold.json',
            creation='exclusive',precondition='absent',effect='deny_admission_only'))
    if 'execution_mode_fact' in facts:context['execution_mode_fact']=facts['execution_mode_fact']
    bindings=dict(proposal=proposal_ref,inspection=inspection_ref,release_sha256=proposal['manifest_sha256'],
        hostname=source['host']['hostname'],uid=source['host']['uid'],boot_id=source['host']['boot_id'])
    scope={key:facts['fixture_cgroup'][key] for key in ('path','device','inode')}
    identities=dict(installation=bindings,retained_services=source['retained_services'],native_context=context,
        authority_journal=facts['authority_journal'],fixture_birth=scope,
        **{key:source['host'][key] for key in ('hostname','uid','boot_id')})
    row=lambda name,argv,seconds:dict(name=name,argv=argv,seconds=seconds)
    protocol=dict(origin='installed_native',identities=identities,fixture_cgroup=scope['path'],timeout_seconds=180,
        startup=row('startup',inspection_command(packet_path,proposal),30),
        cases=[row(control+'/'+scenario,native_command(packet_path,proposal,control,scenario,output,'case'),90)],
        cleanup=row('cleanup',native_command(packet_path,proposal,control,scenario,output,'cleanup'),45),
        postflight=row('postflight',native_command(packet_path,proposal,control,scenario,output,'postflight'),15))
    validate_protocol(protocol)
    packet=dict(schema=SCHEMA,stage='installed',proposal=proposal_ref,inspection=inspection_ref,protocol=protocol)
    return dict(schema='mldsafail.native-control-preparation.v1',execution_authority=False,
        proposal=proposal_ref,inspection=inspection_ref,facts=facts_ref,selection=[dict(control=control,scenario=scenario)],
        envelope_seconds=ENVELOPE.copy(),blockers=[],packet=packet,
        execution_requirements=['independent_exact_source_and_protocol_review','separate_exact_owner_authorization','single_use_watchdog_claim'])
