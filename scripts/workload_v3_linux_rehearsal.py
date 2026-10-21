"""Disposable real-Linux controls, separate from installed-native VPS evidence.

Run only in the owned rehearsal VM. No solver, scientific epoch or credentials.
The two phases permit a host-orchestrated reboot between collection and cleanup.
"""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from deploy.workload_installation import exclusive, identity, Journal
from deploy.workload_prerequisites import root_exclusive_write
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.native_workload import process_birth, values


ACTIVE_JOURNAL=None

def command(argv, *, okay=(0,), seconds=20):
    if ACTIVE_JOURNAL: ACTIVE_JOURNAL.append('command_intent',argv=argv)
    result=subprocess.run(argv,capture_output=True,text=True,timeout=seconds)
    if ACTIVE_JOURNAL: ACTIVE_JOURNAL.append('command_outcome',returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
    assert result.returncode in okay,(argv,result.returncode,result.stdout,result.stderr)
    return result.stdout


def first(root):
    root.mkdir(mode=0o700,exist_ok=False)
    global ACTIVE_JOURNAL
    ACTIVE_JOURNAL=Journal(root,digest(Path(__file__).read_bytes()))
    token=uuid.uuid4().hex[:10]; unit='workload-v3-'+token+'.service'
    directory=Path.home()/'.config/systemd/user';directory.mkdir(parents=True,exist_ok=True)
    path=directory/unit;permission=root/'permission.allow';marker=root/'unexpected-computation'
    ACTIVE_JOURNAL.append('fixture_intent',token=token,root=identity(root),origin='local_linux')
    contents=('[Unit]\nConditionPathExists='+str(permission)+'\n[Service]\nType=oneshot\nExecStart=/usr/bin/touch '+str(marker)+
              '\n[Install]\nWantedBy=default.target\n')
    exclusive(path,contents.encode());unit_identity=identity(path)
    ACTIVE_JOURNAL.append('unit_created',observed=unit_identity)
    command(['systemctl','--user','daemon-reload']);command(['systemctl','--user','enable',unit]);command(['systemctl','--user','start',unit])
    assert not marker.exists() and not permission.exists()
    fixture='workload-v3-fixture-'+token+'.service'
    command(['systemd-run','--user','--unit',fixture,'--property=Delegate=yes','--property=MemoryMax=67108864',
        '--property=MemorySwapMax=0','--property=TasksMax=32','--property=CPUQuota=100%','/usr/bin/sleep','180'])
    cg=command(['systemctl','--user','show',fixture,'--property=ControlGroup','--value']).strip()
    parent=Path('/sys/fs/cgroup'+cg);control=parent/'control';control.mkdir()
    main=int(command(['systemctl','--user','show',fixture,'--property=MainPID','--value']).strip())
    ACTIVE_JOURNAL.append('delegated_fixture',observed=identity(parent),main=process_birth(main))
    main_birth=process_birth(main);(control/'cgroup.procs').write_text(str(main))
    (parent/'cgroup.subtree_control').write_text('+cpu +memory +pids')
    scope=parent/'fixture';scope.mkdir()
    for name,value in {'memory.max':32*1024**2,'memory.swap.max':0,'pids.max':32,'cpu.max':'100000 100000'}.items():
        (scope/name).write_text(str(value))
    children=[];raw={}
    try:
        def enter(): (scope/'cgroup.procs').write_text(str(os.getpid()))
        for _ in range(3):
            child=subprocess.Popen(['/usr/bin/sleep','20'],preexec_fn=enter)
            children.append(child)
            ACTIVE_JOURNAL.append('process_created',birth=process_birth(child.pid))
        births=[dict(process_birth(p.pid),cgroup=Path('/proc/'+str(p.pid)+'/cgroup').read_text().strip()) for p in children]
        assert len({p['pid'] for p in births})==3 and all(p['cgroup']=='0::'+str(scope).removeprefix('/sys/fs/cgroup') for p in births)
        raw['placement']=dict(processes=births,scope=identity(scope),outside_heavy=0)
        for child in children: child.terminate();child.wait(timeout=3)
        children=[];assert values(scope/'cgroup.events')['populated']==0
        before=values(scope/'memory.events')
        child=subprocess.Popen([sys.executable,'-c','x=bytearray(64*1024*1024)'],preexec_fn=enter)
        children.append(child);child.wait(timeout=10)
        after=values(scope/'memory.events')
        assert child.returncode==-signal.SIGKILL and after['oom_kill']>before['oom_kill']
        raw['parent_oom']=dict(before=before,after=after,allocation_bytes=64*1024**2,memory_max=32*1024**2,pids_max=32)
        assert (parent/'memory.max').read_text().strip()=='67108864'
        assert (parent/'memory.swap.max').read_text().strip()=='0' and (parent/'pids.max').read_text().strip()=='32'
        (scope/'memory.max').write_text(str(16*1024**2))
        assert (scope/'memory.max').read_text().strip()==str(16*1024**2)
        raw['limit_change']=dict(before=32*1024**2,after=16*1024**2,scope=identity(scope),origin='local_linux_kernel_only')
    finally:
        for child in children:
            if child.poll() is None: child.kill()
            child.wait(timeout=3)
        assert values(scope/'cgroup.events')['populated']==0
        scope.rmdir()
        assert process_birth(main)==main_birth
        command(['systemctl','--user','stop',fixture]);command(['systemctl','--user','reset-failed',fixture],okay=(0,1))
    backing=root/'output.img';mount=root/'output';mount.mkdir(mode=0o700)
    fd=os.open(backing,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.posix_fallocate(fd,0,32*1024**2);os.fsync(fd);os.close(fd)
    backing_birth=identity(backing,content=False)
    ACTIVE_JOURNAL.append('backing_created',observed=backing_birth)
    command(['sudo','-n','mkfs.ext4','-F',str(backing)],seconds=30)
    mount_name=str(mount).strip('/').replace('-',r'\x2d').replace('/','-')+'.mount'
    mount_path=Path('/etc/systemd/system')/mount_name
    mount_contents=('[Mount]\nWhat='+str(backing)+'\nWhere='+str(mount)+'\nType=ext4\nOptions=loop,noexec,nosuid,nodev\n[Install]\nWantedBy=local-fs.target\n')
    command(root_exclusive_write(mount_path,mount_contents.encode()));command(['sudo','-n','systemctl','daemon-reload'])
    command(['sudo','-n','systemctl','enable','--now',mount_name]);command(['sudo','-n','chown',str(os.getuid()),str(mount)])
    mount_birth=identity(mount)
    ACTIVE_JOURNAL.append('mount_created',observed=mount_birth,unit=mount_name,unit_sha256=digest(mount_contents.encode()))
    from deploy.workload_installed import mount as inspect_mount
    mounted=inspect_mount(mount);assert set(mounted['mount_options'])>={'noexec','nosuid','nodev'}
    data=mount/'quota-fixture';written=0
    try:
        with data.open('xb',buffering=0) as stream:
            for _ in range(64): written+=stream.write(b'x'*(1024*1024))
    except OSError as error: assert error.errno==errno.ENOSPC
    else: raise AssertionError('Filesystem did not enforce bound')
    assert data.stat().st_size<=32*1024**2;data.unlink()
    raw['output']=dict(mount=mounted,bytes_before_enospc=written,backing=identity(backing,content=False))
    # A kernel log bound independent of filesystem fullness.
    log=mount/'bounded.log'
    code='import errno,resource,sys;resource.setrlimit(resource.RLIMIT_FSIZE,(2048,2048));'+'\ntry:\n with open(sys.argv[1],"xb",buffering=0) as f:f.write(b"x"*4096);f.write(b"x")\nexcept OSError as e:assert e.errno==errno.EFBIG\nelse:raise AssertionError()'
    command([sys.executable,'-c',code,str(log)]);assert log.stat().st_size<=2048;log.unlink()
    receipt=dict(schema='mldsafail.disposable-linux-controls.v3',origin='local_linux',phase='awaiting_reboot',
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),uid=os.getuid(),
        unit=unit,unit_identity=unit_identity,marker=str(marker),permission=str(permission),
        mount_unit=mount_name,mount_contents_sha256=digest(mount_contents.encode()),backing=identity(backing,content=False),mount=mount_birth,
        raw=raw,scientific_evaluations=0,installed_native_acceptance=False)
    exclusive(root/'before-reboot.json',canonical(receipt))
    print(json.dumps(dict(passed=True,phase='awaiting_reboot',origin='local_linux')))


def after(root):
    before=json.loads((root/'before-reboot.json').read_bytes())
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot!=before['boot_id']
    assert not Path(before['marker']).exists() and not Path(before['permission']).exists()
    command(['systemctl','--user','start',before['unit']]);assert not Path(before['marker']).exists()
    from deploy.workload_installed import mount
    mounted=mount(before['mount']['path']);assert set(mounted['mount_options'])>={'noexec','nosuid','nodev'}
    unit_path=Path(before['unit_identity']['path']);assert identity(unit_path)==before['unit_identity']
    command(['systemctl','--user','disable',before['unit']]);unit_path.unlink();command(['systemctl','--user','daemon-reload'])
    mount_name=before['mount_unit'];path=Path('/etc/systemd/system')/mount_name
    assert digest(command(['sudo','-n','cat','--',str(path)]).encode())==before['mount_contents_sha256']
    command(['sudo','-n','systemctl','disable','--now',mount_name])
    command(['sudo','-n','rm','--',str(path)]);command(['sudo','-n','systemctl','daemon-reload'])
    backing=Path(before['backing']['path']);actual=identity(backing,content=False)
    assert all(actual[k]==before['backing'][k] for k in ('device','inode','uid','mode'))
    backing.unlink();Path(before['mount']['path']).rmdir()
    receipt=dict(origin='local_linux',passed=True,boot_before=before['boot_id'],boot_after=boot,
        reboot_inhibition=True,persistent_output_mount=True,cleanup_verified=True,
        removed=[str(unit_path),str(path),str(backing),before['mount']['path']],installed_native_acceptance=False)
    exclusive(root/'after-reboot.json',canonical(receipt));print(json.dumps(receipt))


def cleanup_failed(root):
    rows=[json.loads(line) for line in (root/'installation.jsonl').read_text().splitlines()]
    units=[row['observed'] for row in rows if row['event']=='unit_created']
    mounts=[row for row in rows if row['event']=='mount_created']
    removed=[]
    for row in units:
        path=Path(row['path'])
        if not path.exists(): continue
        assert identity(path)==row
        command(['systemctl','--user','disable',path.name]);path.unlink();removed.append(str(path))
    if mounts:
        row=mounts[-1];mount=Path(row['observed']['path'])
        assert identity(mount)==row['observed']
        log=mount/'bounded.log'
        if log.exists():
            assert log.is_file() and not log.is_symlink() and log.stat().st_size<=2048 and set(log.read_bytes())<={120}
            log.unlink()
        assert {p.name for p in mount.iterdir()}<={'lost+found'}
        path=Path('/etc/systemd/system')/row['unit'];assert digest(command(['sudo','-n','cat','--',str(path)]).encode())==row['unit_sha256']
        command(['sudo','-n','systemctl','disable','--now',row['unit']]);command(['sudo','-n','rm','--',str(path)])
        removed.append(str(path));mount.rmdir()
        backing=root/'output.img'
        expected=next(row['observed'] for row in rows if row['event']=='backing_created')
        assert all(identity(backing,content=False)[key]==expected[key] for key in ('device','inode','uid','mode'))
        backing.unlink();removed.append(str(backing))
    command(['systemctl','--user','daemon-reload']);command(['sudo','-n','systemctl','daemon-reload'])
    exclusive(root/'failed-cleanup.json',canonical(dict(passed=False,cleanup_verified=True,removed=removed,origin='local_linux')))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=('before','after','cleanup-failed'));parser.add_argument('root',type=Path)
    args=parser.parse_args();assert sys.platform=='linux' and os.uname().machine=='x86_64'
    {'before':first,'after':after,'cleanup-failed':cleanup_failed}[args.phase](args.root)


if __name__=='__main__':main()
