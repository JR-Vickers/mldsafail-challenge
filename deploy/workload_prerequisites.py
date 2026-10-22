"""Scoped prerequisite proposals. No shared-daemon or ancestor reconfiguration."""
from pathlib import Path
import shlex

from deploy.workload_installation import exclusive, identity
from deploy.workload_units import absolute
from mldsafail.evaluator.native_workload import require


def mount_unit(output):
    name=output['path'].strip('/').replace('-',r'\x2d').replace('/','-')+'.mount'
    contents=('[Unit]\nDescription=MLDSAFAIL preserved bounded output\nBefore=local-fs.target\n'
              '[Mount]\nWhat='+output['backing_file']+'\nWhere='+output['path']+
              '\nType=ext4\nOptions=loop,noexec,nosuid,nodev\n[Install]\nWantedBy=local-fs.target\n')
    return name,contents


def root_exclusive_write(path,data):
    script=('import os,sys; p=sys.argv[1]; '
            'fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600); '
            'os.write(fd,bytes.fromhex(sys.argv[2]));os.fsync(fd);os.close(fd)')
    return ['/usr/bin/sudo','-n','/usr/bin/python3','-c',script,str(path),data.hex()]


def proposal(source):
    output=source['resources']['output']; delegation=source['resources']['delegation']
    commands=[]; reversal=[]; resources=[]
    if output['state']=='proposed':
        path=absolute(output['path']); backing=absolute(output['backing_file'])
        require(output['filesystem']=='ext4' and output['exclusive_backing_file'] is True and
                0<output['bytes']<=1024**3 and source['admission']['backing_free']-output['bytes']>=5*1024**3,
                'prerequisite_backing_floor')
        # Exact exclusive creation is implemented by this adapter, never truncate
        # or format an existing backing file.
        create=('import os,sys;fd=os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);'
                'os.posix_fallocate(fd,0,int(sys.argv[2]));os.fsync(fd);os.close(fd)')
        commands=[[source['recipe']['interpreter']['path'],'-c',create,backing,str(output['bytes'])],
                  ['/usr/bin/sudo','-n','/usr/sbin/mkfs.ext4','-F',backing],
                  ['/usr/bin/sudo','-n','/usr/bin/mount','-t','ext4','-o','loop,noexec,nosuid,nodev',backing,path],
                  ['/usr/bin/sudo','-n','/usr/bin/chown',str(source['host']['uid']),path]]
        name,contents=mount_unit(output)
        commands.insert(1,[source['recipe']['interpreter']['path'],'-c','import os,sys;os.mkdir(sys.argv[1],0o700)',path])
        commands.insert(3,root_exclusive_write('/etc/systemd/system/'+name,contents.encode()))
        commands[4]=['/usr/bin/sudo','-n','/usr/bin/systemctl','daemon-reload']
        commands.insert(5,['/usr/bin/sudo','-n','/usr/bin/systemctl','enable','--now',name])
        reversal=[['/usr/bin/findmnt','--target',path,'--output','ID,SOURCE,TARGET,FSTYPE,OPTIONS'],
                  ['/usr/bin/sudo','-n','/usr/bin/umount',path],['/usr/bin/stat','--',backing]]
        resources=[dict(path=backing,state='proposed',bytes=output['bytes'],preserve='rollback_and_ownership_records'),
                   dict(path=path,state='proposed',preserve='never_unmount_while_owned_outputs_required')]
    if delegation['state']=='proposed':
        commands.append(['/usr/bin/systemctl','--user','start','mldsafail-heavy.slice'])
    commands.append([source['recipe']['interpreter']['path'],'-m','deploy.workload_prerequisites',
                     '--enable-owned-delegation',delegation['path'],'--uid',str(source['host']['uid'])])
    return dict(schema='mldsafail.workload-prerequisite-proposal.v3',execution_authority=False,
        resources=resources,commands=[shlex.join(row) for row in commands],reversal=[shlex.join(row) for row in reversal],
        forbidden=['shared_docker_daemon_mutation','retained_service_ancestor_mutation'],
        admission=dict(memory_floor=1024**3,backing_floor=5*1024**3),
        rollback='preserve_output_mount_and_inhibition')


def apply(source,command,journal):
    output=source['resources']['output']
    if output['state']=='proposed':
        import os
        backing=Path(output['backing_file']); mount=Path(output['path'])
        require(not any(parent.is_symlink() for path in (backing,mount) for parent in (path,*path.parents)),
                'prerequisite_parent_symlink')
        release=Path(source['resources']['release']['path'])
        require(backing.parent.stat().st_dev==release.parent.stat().st_dev,
                'prerequisite_separate_backing_filesystem_requires_evidence')
        require(identity(backing)['state']==identity(mount)['state']=='absent','prerequisite_destination_not_absent')
        fd=os.open(backing,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:
            os.posix_fallocate(stream.fileno(),0,output['bytes']); stream.flush(); os.fsync(stream.fileno())
        journal.append('resource_created',resource='output_backing',observed=identity(backing,content=False))
        mount.mkdir(mode=0o700)
        journal.append('resource_created',resource='output_mountpoint',observed=identity(mount))
        command(['/usr/bin/sudo','-n','/usr/sbin/mkfs.ext4','-F',str(backing)])
        name,contents=mount_unit(output)
        command(root_exclusive_write('/etc/systemd/system/'+name,contents.encode()))
        command(['/usr/bin/sudo','-n','/usr/bin/systemctl','daemon-reload'])
        command(['/usr/bin/sudo','-n','/usr/bin/systemctl','enable','--now',name])
        command(['/usr/bin/sudo','-n','/usr/bin/chown',str(source['host']['uid']),str(mount)])
    if source['resources']['delegation']['state']=='proposed':
        command(['/usr/bin/systemctl','--user','start','mldsafail-heavy.slice'])
    root=source['resources']['delegation']['path']
    journal.append('delegation_controller_intent',observed=identity(root))
    observed=enable_delegation(root,source['host']['uid'])
    journal.append('delegation_controllers_enabled',observed=observed)


def enable_delegation(path,uid):
    """Enable child controllers only on this owner's dedicated heavy slice."""
    import os
    root=Path(path)
    expected='/sys/fs/cgroup/user.slice/user-'+str(uid)+'.slice/user@'+str(uid)+'.service/mldsafail.slice/mldsafail-heavy.slice'
    require(str(root)==expected and os.getuid()==uid and not any(parent.is_symlink() for parent in (root,*root.parents)) and
            root.stat().st_uid==uid,'prerequisite_delegation_owner_changed')
    wanted={'cpu','memory','pids'}
    require(set((root/'cgroup.controllers').read_text().split())>=wanted,'prerequisite_controllers_unavailable')
    if not set((root/'cgroup.subtree_control').read_text().split())>=wanted:
        require(not (root/'cgroup.procs').read_text().strip(),'prerequisite_heavy_internal_processes')
        (root/'cgroup.subtree_control').write_text('+cpu +memory +pids')
    require(set((root/'cgroup.subtree_control').read_text().split())>=wanted,'prerequisite_controller_enable_failed')
    return identity(root)


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-owned-delegation',required=True)
    parser.add_argument('--uid',required=True,type=int)
    args=parser.parse_args();enable_delegation(args.enable_owned_delegation,args.uid)


if __name__=='__main__':main()
