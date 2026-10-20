"""Explicit investigation interfaces. No default execution or automatic retry."""
import argparse
import json
from pathlib import Path

from deploy.production_preparation import read_manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    validate=sub.add_parser('validate-capture')
    validate.add_argument('root',type=Path)
    for name in ('execute','cleanup'):
        command=sub.add_parser(name)
        command.add_argument('root',type=Path)
        command.add_argument('packet',type=Path)
        command.add_argument('configuration',type=Path)
        if name=='execute': command.add_argument('authorization',type=Path)
    args=parser.parse_args()
    if args.action=='validate-capture':
        from deploy.capacity_monitor import validate_capture
        result=validate_capture(args.root)
        result.update(capacity='unresolved',source_compatible=False)
        print(json.dumps(result,sort_keys=True))
        return
    from deploy.investigation_runtime import NativeInvestigation
    packet=read_manifest(args.packet)
    configuration=read_manifest(args.configuration,expected_sha256=packet['configuration_sha256'])
    runtime=NativeInvestigation(args.root,packet,configuration,configuration_sha256=packet['configuration_sha256'])
    if args.action=='execute':
        runtime.run(read_manifest(args.authorization))
    else:
        # Recover recorded controller IDs only; never call run/admission/launch.
        if not runtime.cleanup():
            raise RuntimeError('investigation_cleanup_unverified')
        from deploy.recovery_journal import atomic_json
        atomic_json(args.root/'cleanup-only.json',dict(cleanup_only=True,scheduling_restored=False))


if __name__=='__main__':
    main()
