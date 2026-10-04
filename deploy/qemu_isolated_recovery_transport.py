"""Actual SSH transport loss on an owned fresh disposable QEMU overlay."""
import argparse
import json
from pathlib import Path
from deploy.qemu_isolated_recovery_powerloss import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('base','output','source','review-packet','bootstrap-artifact'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--cleanup',action='store_true')
    args=parser.parse_args()
    result=run(args.base,args.output,args.source,args.review_packet,args.cleanup,args.bootstrap_artifact,transport_loss=True)
    print(json.dumps({key:result.get(key) for key in ('passed','actual_ssh_drop','same_boot_id','same_owner_pid','owned_vm_stopped','cleanup_errors')}))

if __name__=='__main__':main()
