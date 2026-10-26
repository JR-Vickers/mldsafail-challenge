"""Run one exactly bound control case or authorized native stage; grants no authority."""
import argparse
import json
import os
from pathlib import Path

from deploy.workload_acceptance_packet import validate, load_reference
from deploy.workload_control_fixture import execute
from deploy.workload_control_registry import get_runner
from deploy.workload_controls import SCENARIOS
from deploy.workload_installation import private
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.native_workload import require


def case_command(packet_path, proposal, control, scenario, output):
    get_runner(control,scenario)
    release=Path(proposal['identities']['resources']['release']['path'])
    return ['/usr/bin/env','PYTHONPATH='+str(release/'bundle/src')+':'+str(release/'bundle'),
        'PYTHONDONTWRITEBYTECODE=1','PYTHONNOUSERSITE=1',str(release/'.venv/bin/python'),
        '-P','-m','scripts.workload_control_case','--packet',str(Path(packet_path).absolute()),
        '--control',control,'--scenario',scenario,'--output',str(Path(output).absolute())]


def assertions(receipt):
    """Compare observed values; missing measurements never become healthy defaults."""
    control=receipt['control'];scenario=receipt['scenario']
    observed=receipt['observations'];expected=SCENARIOS[control][scenario]
    checks=[]
    for field,value in expected.items():
        present=field in observed
        checks.append(dict(field=field,measured=present,passed=present and
            type(observed[field]) is type(value) and observed[field]==value))
    if control=='continuous_monitor':
        for field,limit in (('abort_latency_ms',1100),('control_read_ms',850)):
            value=observed.get(field)
            checks.append(dict(field=field,measured=field in observed,
                passed=type(value) in (int,float) and 0<=value<=limit))
    if control=='bounded_output':
        checks.append(dict(field='kernel_enforcement',measured='enforcement' in observed,
            passed=observed.get('enforcement')=='kernel'))
    cleanup=receipt.get('fixture_cleanup',{})
    checks.append(dict(field='fixture_cleanup',measured=bool(cleanup),
        passed=cleanup.get('live_runtime_resources_after') is False))
    regression_passed=all(row['passed'] for row in checks)
    required=get_runner(control,scenario)['required_origin']
    origin_accepted=(receipt['origin']=='installed_native' if required=='installed_native' else
        receipt['origin'] in ('synthetic','disposable_database','local_linux'))
    # A process-only adapter cannot prove Docker/cgroup/full installed behavior.
    full_context=receipt.get('scope')!='generation_owned_inert_processes_only'
    return dict(checks=checks,unmeasured=[row['field'] for row in checks if not row['measured']],
        regression_passed=regression_passed,required_origin=required,origin_accepted=origin_accepted,
        full_scenario_passed=regression_passed and origin_accepted and full_context)


def run(packet_path, control, scenario, output):
    raw,packet=private(packet_path)
    from deploy.workload_fixture_control_packet import SCHEMA as FIXTURE_SCHEMA, execute as fixture_execute
    if packet.get('schema')==FIXTURE_SCHEMA:return fixture_execute(packet_path,control,scenario,output)
    validate(packet)
    require(packet['protocol']['origin'] in ('synthetic','local_linux'),'control_case_native_context_adapter_required')
    runner=execute
    if packet['protocol']['origin']=='local_linux':
        from deploy.workload_control_linux import CASES, execute as linux_execute
        require((control,scenario) in CASES,'linux_control_fixture_case_not_implemented')
        runner=linux_execute
    proposal=load_reference(packet['proposal'])
    command=case_command(packet_path,proposal,control,scenario,output)
    matches=[row for row in packet['protocol']['cases'] if row['argv']==command]
    require(len(matches)==1,'control_case_not_bound_to_packet')
    output=Path(output).absolute()
    require(not any(path.is_symlink() for path in (output,*output.parents)), 'control_output_symlink')
    parent=output.parent.stat()
    require(parent.st_uid==os.getuid() and not parent.st_mode&0o077,'control_output_parent_not_private')
    # Reserve output before any effect. Failed or interrupted cases cannot reuse
    # the same packet-bound path; the intent stays available for reconciliation.
    descriptor=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'wb') as stream:
        intent=dict(schema='mldsafail.control-case-intent.v1',packet_sha256=digest(raw),control=control,scenario=scenario)
        stream.write(canonical(intent));stream.flush();os.fsync(stream.fileno())
    receipt=runner(control,scenario,output.with_name(output.name+'.fixture'))
    receipt['packet_sha256']=digest(raw)
    receipt['assertions']=assertions(receipt)
    # Keep intent immutable. Publish the completed observation exclusively too.
    result=output.with_name(output.name+'.result.json')
    descriptor=os.open(result,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'wb') as stream:
        stream.write(canonical(receipt));stream.flush();os.fsync(stream.fileno())
    return receipt


def run_native(packet_path,control,scenario,output,phase):
    require(phase in ('case','cleanup','postflight'),'control_native_phase_invalid')
    from deploy.workload_native_context import NativeContext
    context=NativeContext.open(packet_path,stage=phase)
    operation={'case':context.run_case,'cleanup':context.cleanup_case,'postflight':context.postflight_case}[phase]
    receipt=operation(control,scenario,output)
    if phase=='case':
        require(receipt.get('origin')=='installed_native' and receipt.get('case_observed') is True and
            receipt.get('accepted') is False,'control_native_case_observation_missing')
    elif phase=='cleanup':require(receipt.get('verified') is True,'control_native_cleanup_unverified')
    else:
        require(receipt.get('schema')=='mldsafail.workload-control-postflight.v3' and
            receipt.get('origin')=='installed_native','control_native_postflight_observation_missing')
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet',type=Path,required=True)
    parser.add_argument('--control',required=True)
    parser.add_argument('--scenario',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--native-phase',choices=('case','cleanup','postflight'))
    args=parser.parse_args()
    if args.native_phase:
        receipt=run_native(args.packet,args.control,args.scenario,args.output,args.native_phase)
        if args.native_phase=='postflight':print(canonical(receipt).decode())
        else:print(json.dumps(dict(origin='installed_native',stage=args.native_phase,accepted=False,
            case_observed=receipt.get('case_observed'),verified=receipt.get('verified')),sort_keys=True))
        return
    receipt=run(args.packet,args.control,args.scenario,args.output)
    print(json.dumps(dict(origin=receipt['origin'],packet_sha256=receipt['packet_sha256'],
        control=args.control,scenario=args.scenario,installed_native_eligible=False,
        assertions=receipt['assertions']),sort_keys=True))
    raise SystemExit(0 if (receipt['assertions'].get('full_scenario_passed') or receipt['assertions'].get('fixture_scenario_passed')) else 2)


if __name__=='__main__':main()
