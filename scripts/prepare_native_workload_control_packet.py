"""Prepare one exact installed-native control packet; never execute it."""
import argparse
from pathlib import Path
from deploy.workload_installation import exclusive
from deploy.workload_native_packet import prepare
from deploy.workload_release import canonical


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal',required=True,type=Path)
    parser.add_argument('--inspection',type=Path)
    parser.add_argument('--facts',type=Path)
    parser.add_argument('--packet',required=True,type=Path)
    parser.add_argument('--watchdog-root',required=True,type=Path)
    parser.add_argument('--generation',required=True)
    parser.add_argument('--control',required=True)
    parser.add_argument('--scenario',required=True)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--publish-packet',action='store_true')
    args=parser.parse_args()
    report=prepare(args.proposal,args.inspection,packet_path=args.packet,watchdog_root=args.watchdog_root,
        control=args.control,scenario=args.scenario,generation=args.generation,facts_path=args.facts)
    exclusive(args.output,canonical(report))
    if args.publish_packet and report['packet'] is not None:exclusive(args.packet,canonical(report['packet']))


if __name__=='__main__':main()
