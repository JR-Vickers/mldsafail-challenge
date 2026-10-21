"""Owned, disposable x86_64 systemd/cgroup-v2 rehearsal VM on local QEMU.

Provisioning may download packages. Offline installation is a distinct network
namespace operation inside this guest. This script never accesses the VPS.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import uuid


def run(root, *, budget=1800):
    root = Path(root).absolute()
    assert root.is_dir() and not root.is_symlink()
    source = json.loads((root/'download.json').read_text())
    assert hashlib.sha256((root/'base.img').read_bytes()).hexdigest() == source['sha256']
    assert not (root/'ownership.json').exists()
    for key in ('key', 'host-key'):
        subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(root/key)],check=True)
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0)); port=reservation.getsockname()[1]
    host_public=(root/'host-key.pub').read_text().strip()
    (root/'known_hosts').write_text('[127.0.0.1]:'+str(port)+' '+host_public+'\n')
    seed=root/'seed'; seed.mkdir(mode=0o700)
    instance='workload-v3-'+uuid.uuid4().hex
    (seed/'meta-data').write_text('instance-id: '+instance+'\nlocal-hostname: workload-rehearsal\n')
    user = dict(users=[dict(name='ubuntu', sudo='ALL=(ALL) NOPASSWD:ALL', groups=['sudo'], shell='/bin/bash',
                            ssh_authorized_keys=[(root/'key.pub').read_text().strip()])],
                ssh_pwauth=False, ssh_keys=dict(ed25519_private=(root/'host-key').read_text(),ed25519_public=host_public),
                package_update=True, packages=['python3-venv','python3-pip','postgresql','uidmap','dbus-user-session','docker.io'],
                runcmd=[['systemctl','disable','--now','docker.service','docker.socket'],
                        ['loginctl','enable-linger','ubuntu'], ['touch','/home/ubuntu/provisioned']])
    (seed/'user-data').write_text('#cloud-config\n'+json.dumps(user))
    subprocess.run(['hdiutil','makehybrid','-iso','-joliet','-default-volume-name','cidata','-o',str(root/'seed.iso'),str(seed)],
                   check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(root/'base.img'),str(root/'disk.qcow2'),'12G'],check=True)
    argv=['qemu-system-x86_64','-machine','q35','-accel','tcg,thread=multi','-cpu','max','-smp','2','-m','3072',
          '-nographic','-monitor','none','-drive','if=virtio,format=qcow2,file='+str(root/'disk.qcow2'),
          '-drive','if=virtio,format=raw,readonly=on,file='+str(root/'seed.iso'),
          '-netdev','user,id=net0,hostfwd=tcp:127.0.0.1:'+str(port)+'-:22','-device','virtio-net-pci,netdev=net0']
    ownership=dict(instance=instance,qemu_argv=argv,port=port,base_sha256=source['sha256'],origin='local_linux')
    (root/'ownership.json').write_text(json.dumps(ownership,sort_keys=True))
    ssh=['ssh','-i',str(root/'key'),'-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes',
         '-o','UserKnownHostsFile='+str(root/'known_hosts'),'-o','ConnectTimeout=2','-p',str(port),'ubuntu@127.0.0.1']
    (root/'ssh.json').write_text(json.dumps(ssh))
    process=None
    try:
        with (root/'console.log').open('xb') as log:
            process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
            ownership['pid']=process.pid
            (root/'ownership.json').write_text(json.dumps(ownership,sort_keys=True))
            deadline=time.monotonic()+budget
            while time.monotonic()<deadline:
                assert process.poll() is None, 'Owned VM exited; inspect console.log'
                result=subprocess.run([*ssh,'test -f ~/provisioned && uname -m && ps -p 1 -o comm= && stat -fc %T /sys/fs/cgroup && python3 --version'],
                                      capture_output=True,timeout=10)
                if result.returncode==0:
                    (root/'ready.json').write_text(json.dumps(dict(stdout=result.stdout.decode(),time=time.time(),origin='local_linux')))
                    print('Disposable x86_64 Linux VM ready',flush=True)
                    break
                time.sleep(2)
            else: raise TimeoutError('VM readiness budget exceeded')
            while time.monotonic()<deadline and not (root/'stop').exists():
                assert process.poll() is None, 'Owned VM exited'
                time.sleep(1)
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
            (root/'stopped.json').write_text(json.dumps(dict(pid=process.pid,returncode=process.returncode,reaped=True)))


def resume(root, *, budget=1800):
    """Reuse only this stopped owned disk; retain the original lifecycle record."""
    root=Path(root).absolute()
    assert root.is_dir() and not root.is_symlink()
    stopped=json.loads((root/'stopped.json').read_text());assert stopped['reaped'] is True
    owner=json.loads((root/'ownership.json').read_text())
    assert hashlib.sha256((root/'base.img').read_bytes()).hexdigest()==owner['base_sha256']
    process_list=subprocess.check_output(['ps','-axo','command='],text=True)
    assert not any('qemu-system-' in line and 'file='+str(root/'disk.qcow2') in line for line in process_list.splitlines())
    generation=root/('resume-'+uuid.uuid4().hex);generation.mkdir(mode=0o700)
    argv=owner['qemu_argv']
    assert argv[0]=='qemu-system-x86_64' and '-accel' in argv
    with (generation/'console.log').open('xb') as log:
        process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
        (generation/'ownership.json').write_text(json.dumps(dict(pid=process.pid,qemu_argv=argv,
            parent_ownership_sha256=hashlib.sha256((root/'ownership.json').read_bytes()).hexdigest(),
            origin='local_linux',budget_seconds=budget)))
        print(str(generation),flush=True)
        try:
            deadline=time.monotonic()+budget
            while time.monotonic()<deadline and not (generation/'stop').exists():
                assert process.poll() is None,'Owned resumed VM exited'
                time.sleep(1)
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            (generation/'stopped.json').write_text(json.dumps(dict(pid=process.pid,returncode=process.returncode,reaped=True)))


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('root',type=Path)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if args.resume:
        descriptor=os.open(args.root/'resume.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
            resume(args.root)
        finally:os.close(descriptor)
    else:run(args.root)


if __name__=='__main__': main()
