"""Read-only verification of the preserved rollback; no installation authority."""
import argparse
from pathlib import Path

from deploy.workload_installation import exclusive,private
from deploy.workload_installed import observe_rollback
from deploy.workload_release import canonical
from mldsafail.evaluator.native_workload import require


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspection',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();_,source=private(args.inspection)
    require(source.get('schema')=='mldsafail.workload-bootstrap-inspection.v3',
            'rollback_v3_inspection_required')
    parent=args.output.absolute().parent
    import os
    require(not any(path.is_symlink() for path in (parent,*parent.parents)) and
            parent.stat().st_uid==os.getuid() and parent.stat().st_mode&0o077==0,
            'rollback_private_output_directory_required')
    exclusive(args.output,canonical(observe_rollback(source)))


if __name__=='__main__':main()
