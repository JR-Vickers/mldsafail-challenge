"""Scoped prerequisite proposals. No shared-daemon or ancestor reconfiguration."""
from pathlib import Path
import json
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
    script=('import os,sys,pathlib,json,hashlib,stat; p=pathlib.Path(sys.argv[1]); '
            'assert not any(q.is_symlink() for q in (p,*p.parents));data=bytes.fromhex(sys.argv[2]); '
            'fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600); '
            'stream=os.fdopen(fd,"wb");stream.write(data);stream.flush();os.fsync(stream.fileno()); '
            's=os.fstat(stream.fileno());assert s==p.lstat() and s.st_nlink==1 and s.st_size==len(data); '
            'record=dict(state="observed",path=str(p),device=s.st_dev,inode=s.st_ino,uid=s.st_uid,mode=stat.S_IMODE(s.st_mode),sha256=hashlib.sha256(data).hexdigest()); '
            'stream.close();parent=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(parent);os.close(parent); '
            'print(json.dumps(record))')
    return ['/usr/bin/sudo','-n','/usr/bin/python3','-c',script,str(path),data.hex()]


def mount_namespace(name,command):
    fields=('LoadState','ActiveState','FragmentPath','SourcePath','Transient')
    raw=command(['/usr/bin/sudo','-n','/usr/bin/systemctl','show',name,'--all','--property='+','.join(fields)]).decode()
    rows=[line.split('=',1) for line in raw.splitlines() if '=' in line]
    require(len(rows)==len(fields) and {key for key,value in rows}==set(fields),
            'prerequisite_mount_namespace_observation_incomplete')
    return dict(rows)


def absent_mount_namespace(name,command):
    require(mount_namespace(name,command)==dict(LoadState='not-found',ActiveState='inactive',
            FragmentPath='',SourcePath='',Transient='no'),'prerequisite_mount_namespace_not_absent')


def selected_mount_namespace(name,written,command):
    from deploy.workload_installation import read_owned_file
    from deploy.workload_release import digest
    require(identity(written['path'],content=False)=={key:value for key,value in written.items() if key!='sha256'} and
            digest(read_owned_file(written['path'],command)[0])==written['sha256'],
            'prerequisite_mount_unit_replaced')
    require(mount_namespace(name,command)==dict(LoadState='loaded',ActiveState='inactive',
            FragmentPath=written['path'],SourcePath='',Transient='no'),'prerequisite_mount_namespace_changed')


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


def apply(source,command,journal,*,fault=None):
    from deploy.workload_mutation import mutate
    def change(name,observe,action):
        return mutate(journal,name,observe,action,fault=fault)
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
        name,contents=mount_unit(output)
        unit=Path('/etc/systemd/system')/name
        link=Path('/etc/systemd/system/local-fs.target.wants')/name
        require(identity(unit,content=False)['state']==identity(link)['state']=='absent','prerequisite_mount_unit_destination_exists')
        absent_mount_namespace(name,command)
        def allocate():
            from deploy.workload_installation import sync_directory
            fd=os.open(backing,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as stream:
                os.posix_fallocate(stream.fileno(),0,output['bytes']); stream.flush(); os.fsync(stream.fileno())
            sync_directory(backing.parent)
        change('output_backing',lambda:identity(backing,content=False),allocate)
        created_backing=identity(backing,content=False)
        journal.append('resource_created',resource='output_backing',observed=created_backing)
        def create_mountpoint():
            from deploy.workload_installation import sync_directory
            mount.mkdir(mode=0o700);sync_directory(mount.parent)
        change('output_mountpoint',lambda:identity(mount),create_mountpoint)
        journal.append('resource_created',resource='output_mountpoint',observed=identity(mount))
        require(identity(backing,content=False)==created_backing,'prerequisite_backing_replaced')
        def backing_format():
            # Bind format observations to the original backing birth and header.
            from deploy.workload_release import digest
            require(identity(backing,content=False)==created_backing,'prerequisite_backing_replaced')
            with backing.open('rb') as stream:header=stream.read(4096)
            require(identity(backing,content=False)==created_backing,'prerequisite_backing_replaced')
            return dict(identity=created_backing,header_sha256=digest(header))
        change('output_format',backing_format,
               lambda:command(['/usr/bin/sudo','-n','/usr/sbin/mkfs.ext4','-F',str(backing)]))
        written=json.loads(change('output_mount_unit',lambda:identity(unit,content=False),
                                  lambda:command(root_exclusive_write(unit,contents.encode()))))
        from deploy.workload_release import digest
        require(written==dict(identity(unit,content=False),sha256=digest(contents.encode())) and
                written['uid']==0 and written['mode']==0o600,'prerequisite_mount_unit_ack_changed')
        journal.append('resource_created',resource='output_mount_unit',observed=written)
        change('output_daemon_reload',lambda:mount_namespace(name,command),
               lambda:command(['/usr/bin/sudo','-n','/usr/bin/systemctl','daemon-reload']))
        selected_mount_namespace(name,written,command)
        require(identity(backing,content=False)==created_backing,'prerequisite_backing_replaced')
        change('output_mount_activation',lambda:dict(unit=mount_namespace(name,command),link=identity(link),directory=identity(mount)),
               lambda:command(['/usr/bin/sudo','-n','/usr/bin/systemctl','enable','--now',name]))
        enabled=identity(link)
        require(enabled.get('target')==str(unit) and enabled.get('uid')==0,'prerequisite_mount_enable_changed')
        journal.append('resource_created',resource='output_mount_enable',observed=enabled)
        change('output_mount_owner',lambda:identity(mount),
               lambda:command(['/usr/bin/sudo','-n','/usr/bin/chown',str(source['host']['uid']),str(mount)]))
        from deploy.workload_installed import mount as inspect_mount,loop_backing
        mounted=inspect_mount(mount)
        require(identity(backing,content=False)==created_backing,'prerequisite_backing_replaced')
        require(mounted['filesystem']=='ext4' and set(mounted['mount_options'])>={'noexec','nosuid','nodev'},
                'prerequisite_mount_enforcement_changed')
        journal.append('resource_created',resource='output_active_mount',observed=mounted,
                       directory=identity(mount),backing=created_backing,
                       loop_backing=loop_backing(mounted,created_backing,command))
    if source['resources']['delegation']['state']=='proposed':
        change('delegation_start',lambda:identity(source['resources']['delegation']['path']),
               lambda:command(['/usr/bin/systemctl','--user','start','mldsafail-heavy.slice']))
    root=source['resources']['delegation']['path']
    journal.append('delegation_controller_intent',observed=identity(root))
    def controllers():
        return dict(identity=identity(root),subtree_control=(Path(root)/'cgroup.subtree_control').read_text().strip())
    observed=change('delegation_controllers',controllers,lambda:enable_delegation(root,source['host']['uid']))
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
