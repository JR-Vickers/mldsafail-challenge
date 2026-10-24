"""Owned, disposable x86_64 systemd/cgroup-v2 rehearsal VM on local QEMU.

Provisioning may download packages. Offline installation is a distinct network
namespace operation inside this guest. This script never accesses the VPS.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import time
import uuid


def allocate(root, image, download, *, case):
    """Allocate a fresh per-case guest from the verified clean Ubuntu base.

    Never clone an answered trial disk or share its writable namespaces. Each
    invocation of run() owns one independent overlay and cloud-init instance.
    Packages/rootless tooling are provisioned before offline installation.
    """
    from deploy.workload_installation import exclusive, identity, private, sync_directory
    from deploy.workload_release import canonical, copy_regular, file_record
    from scripts.workload_installation_fixture import absolute, CASES, lifecycle_lock
    root=absolute(root);image=absolute(image);download=absolute(download)
    vm_argv(root,1)
    assert case in CASES
    _,source=private(download)
    assert source['url'].startswith('https://cloud-images.ubuntu.com/') and source['url'].endswith('amd64.img')
    record=file_record(image.parent,image.name)
    assert image.stat().st_uid==os.getuid() and record['sha256']==source['sha256']
    processes=subprocess.check_output(['ps','-axo','command='],text=True)
    assert not any('qemu-system-' in line and 'file='+str(image) in line for line in processes.splitlines())
    mounts=subprocess.check_output(['mount'],text=True)
    assert not any(str(image) in line for line in mounts.splitlines())
    root.mkdir(mode=0o700);sync_directory(root.parent)
    with lifecycle_lock(root):
        exclusive(root/'allocation-intent.json',canonical(dict(fixture_only=True,case=case,
            source=identity(image,content=False),source_sha256=source['sha256'],resources=['base.img','disk.qcow2','seed.iso',
            'seed','key','key.pub','host-key','host-key.pub','known_hosts','ssh.json','ownership.json','console.log','ready.json','stopped.json'])))
        try:
            copy_regular(image.parent,image.name,root/'base.img',dict(record,mode=0o600),source_record=record)
            exclusive(root/'download.json',canonical(source))
            exclusive(root/'allocation-complete.json',canonical(dict(fixture_only=True,case=case,
                base=identity(root/'base.img',content=False),sha256=record['sha256'],shared_hardlinks=False,
                namespaces_shared_with_previous_trial=False)))
        except BaseException as error:
            exclusive(root/'allocation-failed.json',canonical(dict(error=type(error).__name__,message=str(error),
                ownership='preserve',automatic_retry=False)))
            raise
    return root


def vm_argv(root,port):
    from mldsafail.evaluator.native_workload import require
    require(type(port) is int and 0<port<65536,'fixture_vm_port_invalid')
    require(root.is_absolute() and '..' not in root.parts and re.fullmatch(r'/[A-Za-z0-9_./@-]+',str(root)),
            'fixture_vm_path_invalid')
    return ['qemu-system-x86_64','-machine','q35','-accel','tcg,thread=multi','-cpu','max','-smp','2','-m','3072',
            '-nographic','-monitor','none','-drive','if=virtio,format=qcow2,file='+str(root/'disk.qcow2'),
            '-drive','if=virtio,format=raw,readonly=on,file='+str(root/'seed.iso'),
            '-netdev','user,id=net0,hostfwd=tcp:127.0.0.1:'+str(port)+'-:22','-device','virtio-net-pci,netdev=net0']


def inactive(root):
    from mldsafail.evaluator.native_workload import require
    disk=str(root/'disk.qcow2')
    processes=subprocess.check_output(['ps','-axo','command='],text=True)
    require(not any('qemu-system-' in line and 'file='+disk in line for line in processes.splitlines()),'fixture_vm_disk_active')
    mounts=subprocess.check_output(['mount'],text=True)
    require(not any(str(root) in line for line in mounts.splitlines()),'fixture_vm_mount_active')
    for name in ('base.img','disk.qcow2','seed.iso'):
        observed=subprocess.run(['lsof','-Fpn','--',str(root/name)],capture_output=True,timeout=5)
        require(observed.returncode==1 and not observed.stdout,'fixture_vm_open_image_preserve')


def stopped_record(destination,root,process):
    from deploy.workload_installation import exclusive,identity
    from deploy.workload_release import canonical,digest,file_record
    errors=[]
    try:inactive(root)
    except Exception as error:errors.append(dict(type=type(error).__name__,message=str(error)))
    try:os.killpg(process.pid,0);group_empty=False
    except ProcessLookupError:group_empty=True
    except OSError as error:
        group_empty=False;errors.append(dict(type=type(error).__name__,message=str(error)))
    artifacts={}
    for name in ('base.img','disk.qcow2','seed.iso'):
        try:artifacts[name]=dict(identity(root/name,content=False),sha256=file_record(root,name)['sha256'])
        except Exception as error:errors.append(dict(path=name,type=type(error).__name__,message=str(error)))
    exclusive(destination/'stopped.json',canonical(dict(pid=process.pid,returncode=process.returncode,reaped=True,
        process_group_empty=group_empty,inactivity_verified=not errors,cleanup_errors=errors,artifacts=artifacts,
        owner_sha256=digest((destination/'ownership.json').read_bytes()),recorded_at=time.time())))


def run(root, *, budget=1800):
    from scripts.workload_installation_fixture import absolute, lifecycle_lock
    root=absolute(root)
    vm_argv(root,1)
    with lifecycle_lock(root):
        return _run(root,budget=budget)


def _run(root, *, budget):
    from deploy.workload_installation import exclusive, identity
    from deploy.workload_release import canonical, file_record
    from deploy.workload_log import LogPipe
    from mldsafail.evaluator.native_workload import require
    require(300<budget<=1800,'fixture_vm_budget_invalid')
    started=time.monotonic();deadline=started+budget-300
    exclusive(root/'vm-run-intent.json',canonical(dict(fixture_only=True,root=identity(root),budget_seconds=budget,
                                                     cleanup_reserve_seconds=300)))
    process=None
    try:
        source=json.loads((root/'download.json').read_text())
        base=file_record(root,'base.img')
        require(base['sha256']==source['sha256'],'fixture_vm_base_changed')
        allocated=root/'allocation-complete.json'
        if allocated.exists():
            allocation=json.loads(allocated.read_bytes())
            require(allocation['base']==identity(root/'base.img',content=False) and
                    allocation['sha256']==base['sha256'],'fixture_vm_allocated_base_replaced')
        for name in ('ownership.json','key','key.pub','host-key','host-key.pub','seed','seed.iso','disk.qcow2','console.log'):
            require(identity(root/name,content=False)['state']=='absent','fixture_vm_resource_exists:'+name)
        def command(argv):
            remaining=deadline-time.monotonic()
            require(remaining>2,'fixture_vm_preparation_budget_expired')
            token=uuid.uuid4().hex
            exclusive(root/('prepare-'+token+'-intent.json'),canonical(dict(argv=argv,timeout_seconds=min(30,remaining-1))))
            child=None;failure=None
            try:
                with (root/('prepare-'+token+'.log')).open('xb') as stream,LogPipe(stream,1024**2) as pipe:
                    os.chmod(stream.name,0o600)
                    child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=pipe.write_fd,stderr=subprocess.STDOUT,start_new_session=True)
                    pipe.wait(child,min(30,remaining-1))
                    require(child.returncode==0,'fixture_vm_preparation_command_failed')
            except BaseException as error:
                failure=dict(type=type(error).__name__,message=str(error))
                raise
            finally:
                if child is not None and child.poll() is None:
                    os.killpg(child.pid,15)
                    try:child.wait(timeout=.5)
                    except subprocess.TimeoutExpired:os.killpg(child.pid,9);child.wait(timeout=.5)
                exclusive(root/('prepare-'+token+'-result.json'),canonical(dict(returncode=child.returncode if child else None,failure=failure)))
        for key in ('key','host-key'):
            command(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(root/key)])
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
        host_public=(root/'host-key.pub').read_text().strip()
        exclusive(root/'known_hosts',('[127.0.0.1]:'+str(port)+' '+host_public+'\n').encode())
        seed=root/'seed';seed.mkdir(mode=0o700)
        instance='workload-v3-'+uuid.uuid4().hex
        exclusive(seed/'meta-data',('instance-id: '+instance+'\nlocal-hostname: workload-rehearsal\n').encode())
        user=dict(users=[dict(name='ubuntu',sudo='ALL=(ALL) NOPASSWD:ALL',groups=['sudo'],shell='/bin/bash',
                             ssh_authorized_keys=[(root/'key.pub').read_text().strip()])],
                  ssh_pwauth=False,ssh_keys=dict(ed25519_private=(root/'host-key').read_text(),ed25519_public=host_public),
                  write_files=[dict(path='/etc/systemd/system/user@.service.d/50-workload-fixture-delegate.conf',
                                    permissions='0644',content='[Service]\nDelegate=cpu cpuset io memory pids\n')],
                  package_update=True,packages=['git','python3-venv','python3-pip','uidmap','dbus-user-session','docker.io','rootlesskit','slirp4netns'],
                  runcmd=[['systemctl','disable','--now','docker.service','docker.socket'],
                          ['systemctl','daemon-reload'],
                          ['loginctl','enable-linger','ubuntu'],['touch','/home/ubuntu/provisioned']])
        exclusive(seed/'user-data',('#cloud-config\n'+json.dumps(user)).encode())
        command(['hdiutil','makehybrid','-iso','-joliet','-default-volume-name','cidata','-o',str(root/'seed.iso'),str(seed)])
        command(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(root/'base.img'),str(root/'disk.qcow2'),'16G'])
        argv=vm_argv(root,port)
        ownership=dict(instance=instance,qemu_argv=argv,port=port,base_sha256=source['sha256'],origin='local_linux')
        exclusive(root/'ownership-intent.json',canonical(ownership))
        ssh=['ssh','-i',str(root/'key'),'-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes',
             '-o','UserKnownHostsFile='+str(root/'known_hosts'),'-o','ConnectTimeout=2','-p',str(port),'ubuntu@127.0.0.1']
        exclusive(root/'ssh.json',canonical(ssh))
        require(time.monotonic()<deadline,'fixture_vm_preparation_budget_expired')
        with (root/'console.log').open('xb') as log,LogPipe(log,4*1024**2) as console:
            os.chmod(log.name,0o600)
            process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=console.write_fd,stderr=subprocess.STDOUT,start_new_session=True)
            console.spawned()
            exclusive(root/'ownership.json',canonical(dict(ownership,pid=process.pid)))
            while time.monotonic()<deadline:
                require(not console.overflow.is_set(),'fixture_vm_console_limit')
                require(process.poll() is None,'fixture_owned_vm_exited')
                try:
                    result=subprocess.run([*ssh,'test -f ~/provisioned && uname -m && ps -p 1 -o comm= && stat -fc %T /sys/fs/cgroup && python3 --version'],
                                          capture_output=True,timeout=min(10,max(.001,deadline-time.monotonic())))
                except subprocess.TimeoutExpired:
                    exclusive(root/('readiness-poll-'+uuid.uuid4().hex+'.json'),canonical(dict(
                        kind='read_only_readiness_poll',error='TimeoutExpired',phase_retry=False)))
                    continue
                if result.returncode==0:
                    exclusive(root/'ready.json',canonical(dict(stdout=result.stdout[:65536].decode(),time=time.time(),origin='local_linux')))
                    print('Disposable x86_64 Linux VM ready',flush=True)
                    break
                time.sleep(min(2,max(0,deadline-time.monotonic())))
            else:raise TimeoutError('VM readiness budget exceeded')
            while time.monotonic()<deadline and not (root/'stop').exists():
                require(not console.overflow.is_set(),'fixture_vm_console_limit')
                require(process.poll() is None,'fixture_owned_vm_exited')
                time.sleep(min(1,deadline-time.monotonic()))
    except BaseException as error:
        exclusive(root/'vm-run-failed.json',canonical(dict(error=type(error).__name__,message=str(error),automatic_retry=False)))
        raise
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            stopped_record(root,root,process)


def resume(root, *, budget=1800, adoption=None):
    from scripts.workload_installation_fixture import absolute,lifecycle_lock
    root=absolute(root)
    vm_argv(root,1)
    with lifecycle_lock(root):return _resume(root,budget=budget,adoption=adoption)


def _resume(root, *, budget=1800, adoption=None):
    from deploy.workload_installation import exclusive,identity,private
    from deploy.workload_release import canonical,digest,file_record
    from deploy.workload_log import LogPipe
    from mldsafail.evaluator.native_workload import require
    require(300<budget<=1800,'fixture_vm_budget_invalid')
    deadline=time.monotonic()+budget-300
    owner_raw,owner=private(root/'ownership.json')
    require(owner.get('origin')=='local_linux' and owner['qemu_argv']==vm_argv(root,owner['port']), 'fixture_vm_owned_argv_changed')
    inactive(root)
    candidates=[root/'stopped.json',*[p/'stopped.json' for p in root.glob('resume-*') if p.is_dir()]]
    require(all(not p.parent.is_symlink() and p.is_file() for p in candidates),'fixture_vm_incomplete_lifecycle_audit_required')
    records=[(p,*private(p)) for p in candidates]
    require(all(record['reaped'] is True for p,raw,record in records),'fixture_vm_unreaped_generation')
    latest_path,latest_raw,latest=max(records,key=lambda row:row[2].get('recorded_at',row[0].stat().st_mtime))
    current={name:dict(identity(root/name,content=False),sha256=file_record(root,name)['sha256'])
             for name in ('base.img','disk.qcow2','seed.iso')}
    require(current['base.img']['sha256']==owner['base_sha256'],'fixture_vm_base_changed')
    if 'artifacts' not in latest:
        require(adoption is not None,'fixture_vm_legacy_resume_audit_required')
        _,audit=private(adoption)
        require(audit.get('schema')=='mldsafail.fixture-vm-adoption.v1' and audit.get('fixture_only') is True and
                audit.get('ownership_sha256')==digest(owner_raw) and audit.get('artifacts')==current and
                audit.get('stopped_records')=={str(p.relative_to(root)):digest(raw) for p,raw,r in records} and
                0<=time.time()-audit.get('captured_at',0)<=300,'fixture_vm_adoption_changed_or_expired')
    else:
        selected_owner_raw,selected_owner=private(latest_path.parent/'ownership.json')
        require(latest.get('process_group_empty') is True and latest.get('inactivity_verified') is True and latest['artifacts']==current and
                latest['owner_sha256']==digest(selected_owner_raw),
                'fixture_vm_stopped_artifact_replaced')
        if latest_path.parent!=root:
            require(selected_owner.get('parent_ownership_sha256')==digest(owner_raw),
                    'fixture_vm_parent_ownership_replaced')
    generation=root/('resume-'+uuid.uuid4().hex);generation.mkdir(mode=0o700)
    exclusive(generation/'intent.json',canonical(dict(fixture_only=True,parent_ownership_sha256=digest(owner_raw),
        previous_stop_sha256=digest(latest_raw),artifacts=current,budget_seconds=budget,cleanup_reserve_seconds=300)))
    process=None
    try:
        with (generation/'console.log').open('xb') as log,LogPipe(log,4*1024**2) as console:
            os.chmod(log.name,0o600)
            require(time.monotonic()<deadline,'fixture_vm_audit_budget_expired')
            process=subprocess.Popen(owner['qemu_argv'],stdin=subprocess.DEVNULL,stdout=console.write_fd,stderr=subprocess.STDOUT,start_new_session=True)
            console.spawned()
            exclusive(generation/'ownership.json',canonical(dict(pid=process.pid,qemu_argv=owner['qemu_argv'],
                parent_ownership_sha256=digest(owner_raw),origin='local_linux',budget_seconds=budget)))
            print(str(generation),flush=True)
            while time.monotonic()<deadline and not (generation/'stop').exists():
                require(not console.overflow.is_set(),'fixture_vm_console_limit')
                require(process.poll() is None,'fixture_owned_vm_exited')
                time.sleep(min(1,deadline-time.monotonic()))
    except BaseException as error:
        exclusive(generation/'failed.json',canonical(dict(error=type(error).__name__,message=str(error),automatic_retry=False)))
        raise
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            stopped_record(generation,root,process)


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('root',type=Path)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--adoption',type=Path)
    parser.add_argument('--allocate-from',type=Path)
    parser.add_argument('--download',type=Path)
    parser.add_argument('--case',choices=('complete','partial-snapshots','partial-configurations','unacknowledged-images','interrupted-rollback'))
    args=parser.parse_args()
    from scripts.workload_installation_fixture import absolute, lifecycle_lock
    args.root=absolute(args.root)
    if args.allocate_from:
        assert args.download and args.case and not args.resume
        allocate(args.root,args.allocate_from,args.download,case=args.case)
        print(json.dumps(dict(fixture_only=True,root=str(args.root),allocated=True,guest_started=False)))
        return
    if args.resume:
        descriptor=os.open(args.root/'resume.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
            resume(args.root,adoption=args.adoption)
        finally:os.close(descriptor)
    else:
        run(args.root)


if __name__=='__main__': main()
