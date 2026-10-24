"""Run one exactly bound synthetic control case; this creates no authority."""
import argparse
import json
import os
from pathlib import Path

from deploy.workload_acceptance_packet import validate, load_reference
from deploy.workload_control_fixture import execute
from deploy.workload_control_registry import get_runner
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


def run(packet_path, control, scenario, output):
    raw,packet=private(packet_path);validate(packet)
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
    # Keep intent immutable. Publish the completed observation exclusively too.
    result=output.with_name(output.name+'.result.json')
    descriptor=os.open(result,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'wb') as stream:
        stream.write(canonical(receipt));stream.flush();os.fsync(stream.fileno())
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet',type=Path,required=True)
    parser.add_argument('--control',required=True)
    parser.add_argument('--scenario',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    receipt=run(args.packet,args.control,args.scenario,args.output)
    print(json.dumps(dict(origin=receipt['origin'],packet_sha256=receipt['packet_sha256'],
        control=args.control,scenario=args.scenario,installed_native_eligible=False),sort_keys=True))


if __name__=='__main__':main()
