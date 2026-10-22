"""Read-only current-user cgroup prerequisites; no controller writes or authority."""
import argparse
import os
from pathlib import Path
import socket
import time

from deploy.workload_installed import cgroup_observation
from deploy.workload_installation import exclusive,identity
from deploy.workload_release import canonical
from mldsafail.evaluator.native_workload import require


def collect(uid=None):
    uid=os.getuid() if uid is None else uid
    require(uid==os.getuid() and uid>0,'cgroup_collection_requires_runtime_owner')
    manager=Path('/sys/fs/cgroup/user.slice/user-'+str(uid)+'.slice/user@'+str(uid)+'.service')
    heavy=manager/'mldsafail.slice/mldsafail-heavy.slice'
    require(not any(parent.is_symlink() for parent in (heavy,*heavy.parents)),
            'cgroup_collection_parent_symlink')
    require(manager.is_dir(),'cgroup_collection_manager_missing')
    def observed_or_proposed(path):
        if path.exists():return cgroup_observation(path)
        require(path in (heavy,heavy.parent),'cgroup_collection_shared_ancestor_missing')
        # These are requirements on exclusive dedicated resources, not measured
        # births or assertions about a future kernel state.
        return dict(state='proposed',path=str(path),creation='exclusive_owned_creation',
                    preserve='current_and_rollback',controllers=['cpu','memory','pids'],
                    writable=True,retained_service_ancestor=False)
    ancestors=[]
    for parent in heavy.parents:
        row=observed_or_proposed(parent)
        # A pathname is not proof that existing descendants are disposable.
        # Conservatively protect every observed ancestor until retained-service
        # placements are independently joined to this observation.
        row['retained_service_ancestor']=row['state']=='observed'
        ancestors.append(row)
        if str(parent)=='/sys/fs/cgroup':break
    require(ancestors[-1]['path']=='/sys/fs/cgroup','cgroup_collection_incomplete_ancestry')
    delegation=observed_or_proposed(heavy);delegation['ancestors']=ancestors
    return dict(schema='mldsafail.workload-cgroup-observation.v3',origin='host_observation',
        captured_at=time.time(),hostname=socket.gethostname(),uid=uid,
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        user_manager=identity(manager),delegation=delegation,execution_authority=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();parent=args.output.absolute().parent
    require(not any(path.is_symlink() for path in (parent,*parent.parents)) and
            parent.stat().st_uid==os.getuid() and parent.stat().st_mode&0o077==0,
            'cgroup_collection_private_directory_required')
    exclusive(args.output,canonical(collect()))


if __name__=='__main__':main()
