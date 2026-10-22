"""Run an installed v3 control packet under independent deadline supervision."""
import argparse
from pathlib import Path
from deploy.workload_acceptance_packet import execute,verify_installed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet',required=True,type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--verify-installed',action='store_true')
    parser.add_argument('--review',type=Path)
    parser.add_argument('--authorization',type=Path)
    args=parser.parse_args()
    if args.verify_installed:
        verify_installed(args.packet);return
    if args.output is None:parser.error('--output is required for execution')
    receipt=execute(args.packet,args.output,review_path=args.review,authorization_path=args.authorization)
    raise SystemExit(0 if receipt['passed'] else 2)


if __name__=='__main__':main()
