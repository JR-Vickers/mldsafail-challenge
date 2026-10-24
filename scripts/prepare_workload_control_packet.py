"""Prepare one bounded control case for review; never execute or grant authority."""
import argparse
from pathlib import Path
from deploy.workload_installation import exclusive
from deploy.workload_packet_preparation import prepare
from deploy.workload_release import canonical


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal',required=True,type=Path)
    parser.add_argument('--inspection',type=Path)
    parser.add_argument('--fixture-manifest',type=Path,help='Prepare an exact packet within an existing reviewed disposable fixture')
    parser.add_argument('--packet',required=True,type=Path)
    parser.add_argument('--case-output',required=True,type=Path)
    parser.add_argument('--control',required=True)
    parser.add_argument('--scenario',required=True)
    parser.add_argument('--attempt',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    from deploy.workload_installation import private
    attempt=private(args.attempt)[1] if args.attempt else None
    if args.fixture_manifest:
        if args.inspection is None:parser.error('--fixture-manifest requires --inspection')
        if args.attempt is not None:parser.error('fixture execution uses its existing lifecycle journal; omit --attempt')
        from deploy.workload_fixture_control_packet import prepare as fixture_packet
        plan=fixture_packet(args.fixture_manifest,args.proposal,args.inspection,packet_path=args.packet,
            output=args.case_output,control=args.control,scenario=args.scenario)
        if args.output.absolute()!=args.packet.absolute():parser.error('fixture packet must be written at its exact --packet path')
    else:
        plan=prepare(args.proposal,args.inspection,packet_path=args.packet,
            output_path=args.case_output,control=args.control,scenario=args.scenario,attempt=attempt)
    exclusive(args.output,canonical(plan))


if __name__=='__main__':main()
