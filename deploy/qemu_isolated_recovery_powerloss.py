"""Hard-power-loss acceptance on a NEW overlay; no protected base writes/VPS."""
import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import time
import uuid
from deploy import owned_vm
from deploy.qemu_recovery_powerloss import ssh_argv
from deploy.recovery_journal import atomic_json,safe_path


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def isolated_argv(base,output,previous,port):
    fixed=['qemu-system-aarch64','-machine','virt,highmem=off','-accel','hvf','-cpu','host','-smp','2','-m','2048','-nographic','-monitor','none',
        '-drive','if=pflash,format=raw,readonly=on,file=/opt/homebrew/share/qemu/edk2-aarch64-code.fd',
        '-drive','if=pflash,format=raw,file='+str(base/'vars.fd'),
        '-drive','if=virtio,format=qcow2,file='+str(base/'disk.qcow2'),
        '-drive','if=virtio,format=raw,readonly=on,file='+str(base/'seed.iso'),
        '-netdev','', '-device','virtio-net-pci,netdev=net0']
    if not isinstance(previous,list) or len(previous)!=len(fixed):raise ValueError('Exact protected VM argument allowlist required')
    network=previous[previous.index('-netdev')+1]
    if not re.fullmatch(r'user,id=net0,hostfwd=tcp:127\.0\.0\.1:[0-9]+-:22',network):raise ValueError('Protected VM must expose only loopback SSH')
    fixed[fixed.index('-netdev')+1]=network
    if previous!=fixed:raise ValueError('Extra writable drive/host output forbidden')
    fixed[fixed.index('-netdev')+1]='user,id=net0,hostfwd=tcp:127.0.0.1:'+str(port)+'-:22'
    return [value.replace(str(base/'vars.fd'),str(output/'vars.fd')).replace(str(base/'disk.qcow2'),str(output/'disk.qcow2')) for value in fixed]


def require_base_quiescent(base):
    result=subprocess.run(['lsof','-t','--',str(base/'disk.qcow2'),str(base/'vars.fd')],capture_output=True,timeout=15)
    if result.returncode not in (0,1) or result.stdout.strip() or result.stderr.strip():raise RuntimeError('Protected base VM files are open or quiescence unproved')


def run(base,output,source,review_packet,cleanup_only=False):
    base,output,source=map(safe_path,(base,output,source))
    descriptor=os.open(output.parent/('.'+output.name+'.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077 or info.st_nlink!=1:
            raise ValueError('Private regular owned VM lock required')
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if cleanup_only:
            from deploy.recovery import private_file
            record=json.loads(private_file(output/'ownership.json').read_text())
            errors=[]
            for entry in record.get('vm_attempts',[]):
                try:
                    if not entry.get('exit_proven'):owned_vm.stop(entry)
                except BaseException as error:errors.append(type(error).__name__)
            atomic_json(output/(uuid.uuid4().hex+'-cleanup.json'),{'owned_vm_stopped':not errors,'errors':errors})
            if errors:raise RuntimeError('Owned VM cleanup incomplete')
            return {'owned_vm_stopped':True}
        return execute(base,output,source,review_packet)
    finally:os.close(descriptor)


def execute(base,output,source,review_packet):
    os.umask(0o077)
    output.mkdir(mode=0o700,exist_ok=False)
    def command(argv,timeout=120):return subprocess.check_output(argv,stderr=subprocess.STDOUT,timeout=timeout)
    if command(['git','-C',str(source),'status','--porcelain']):raise ValueError('Retained clean source required')
    commit=command(['git','-C',str(source),'rev-parse','HEAD']).decode().strip()
    from deploy import owned_daemon
    from research.cpu_measurement.native_driver import source_digest
    packet=owned_daemon.read_private_json(review_packet)
    callback_sha=sha(source/'deploy/native_recovery_powerloss.py')
    if (packet.get('schema')!='mldsafail.cpu-native-review.v1' or packet.get('supervisor_source_sha256')!=source_digest(source) or
        packet.get('acceptance_source_sha256')!=callback_sha or
        any(packet.get(name) is not True for name in ('supervisor_review_passed','auditor_review_passed','native_protocol_review_passed')) or
        not packet.get('evidence_refs')):raise ValueError('Actual source-bound independent reviews required')
    require_base_quiescent(base)
    previous=json.loads((base/'ownership.json').read_text())['qemu_argv']
    isolated_argv(base,output,previous,1)  # Reject inherited mutable host resources before image operations.
    originals={'disk':sha(base/'disk.qcow2'),'vars':sha(base/'vars.fd')}
    command(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(base/'disk.qcow2'),str(output/'disk.qcow2')])
    for name in ('key','key.pub','vars.fd'):
        shutil.copyfile(base/name,output/name);(output/name).chmod(0o600)
    command(['git','-C',str(source),'bundle','create',str(output/'source.bundle'),'HEAD'])
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
    argv=isolated_argv(base,output,previous,port)
    record=dict(schema='mldsafail.isolated-powerloss-vm.v1',source_commit=commit,callback_sha256=callback_sha,
        bundle_sha256=sha(output/'source.bundle'),qemu_argv=argv,port=port,originals=originals,
        vm_attempts=[],passed=False,owned_vm_stopped=False,synthetic_only=True)
    atomic_json(output/'ownership.json',record)
    process=None;log=None;original=None
    ssh=ssh_argv(output,port)
    def guest(text,timeout=120):return command(ssh+[text],timeout)
    def upload(path,value):
        subprocess.run(ssh+['umask 077; cat > '+path],input=value,stdout=subprocess.DEVNULL,check=True,timeout=120)
    def boot():
        nonlocal process,log
        log=(output/('boot-'+str(len(record['vm_attempts']))+'.log')).open('wb')
        def publish(entry):record['vm_attempts'].append(entry);atomic_json(output/'ownership.json',record)
        process,entry=owned_vm.spawn(argv,publish,log)
        deadline=time.monotonic()+240
        while True:
            try:guest('systemctl is-active --quiet multi-user.target',10);break
            except subprocess.SubprocessError:
                if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('VM boot health gate failed')
                time.sleep(1)
    def invoke(phase):
        unit='mldsafail-owned-powerloss-'+phase+'-'+uuid.uuid4().hex+'.service'
        settings=record['artifacts']
        settings.update(schema='mldsafail.owned-native-driver.v1',source_commit=commit,
            supervisor_source_sha256=packet['supervisor_source_sha256'],acceptance_source_sha256=callback_sha,
            operator_unit=unit,operator_parent='/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/'+unit,
            state_root='/home/ubuntu/powerloss-evidence/'+phase+'-driver',review_packet='/home/ubuntu/powerloss-review.json')
        config='/home/ubuntu/powerloss-evidence/'+phase+'-config.json'
        upload(config,json.dumps(settings).encode())
        record[phase+'_operator_unit']=unit;atomic_json(output/'ownership.json',record)
        guest('systemd-run --user --unit='+unit+' --property=Delegate=yes --property=UMask=0077 --property=Restart=no '+
              '--property=WorkingDirectory=/home/ubuntu/powerloss-source '+
              '--setenv=PYTHONPATH=/home/ubuntu/powerloss-source:/home/ubuntu/powerloss-source/src '+
              '/usr/bin/python3 -m deploy.native_recovery_powerloss --phase '+phase+' --config '+config)
        return unit
    try:
        boot()
        guest('sudo apt-get -qq update && sudo apt-get -qq install -y git',300)
        with (output/'source.bundle').open('rb') as stream:
            subprocess.run(ssh+['cat > /home/ubuntu/powerloss-source.bundle'],stdin=stream,stdout=subprocess.DEVNULL,check=True,timeout=120)
        guest('git clone -q /home/ubuntu/powerloss-source.bundle /home/ubuntu/powerloss-source && git -C /home/ubuntu/powerloss-source checkout -q '+commit+' && mkdir -m700 /home/ubuntu/powerloss-evidence /home/ubuntu/powerloss-artifacts')
        upload('/home/ubuntu/powerloss-review.json',json.dumps(packet).encode())
        # Bootstrap is solely this disposable VM's existing synthetic daemon.
        # Its resources cannot survive exact owned VM termination; no staging inputs.
        bootstrap='''import hashlib,json,os,subprocess
from pathlib import Path
os.environ['DOCKER_HOST']='unix:///run/user/1000/docker.sock'
def cmd(a):return subprocess.check_output(a)
info=json.loads(cmd(['docker','info','--format','{{json .}}']))
if cmd(['docker','ps','-aq']).strip():raise RuntimeError('Bootstrap daemon must have no containers')
cmd(['docker','pull','postgres:16-alpine'])
image=json.loads(cmd(['docker','image','inspect','postgres:16-alpine']))[0]['Id']
archive=Path('/home/ubuntu/powerloss-artifacts/postgres.tar')
with archive.open('wb') as stream:subprocess.run(['docker','save',image],stdout=stream,check=True)
archive.chmod(0o600)
with archive.open('rb') as stream:archive_sha=hashlib.file_digest(stream,'sha256').hexdigest()
rootless=cmd(['which','dockerd-rootless.sh']).decode().strip()
dockerd=cmd(['which','dockerd']).decode().strip()
control=cmd(['systemctl','--user','show','docker.service','--property=ControlGroup','--value']).decode().strip()
print(json.dumps(dict(image=image,image_archive=str(archive),image_archive_sha256=archive_sha,dockerd_sha256=hashlib.sha256(Path(dockerd).read_bytes()).hexdigest(),rootless_script=rootless,rootless_script_sha256=hashlib.sha256(Path(rootless).read_bytes()).hexdigest(),server_version=info['ServerVersion'],server_git_commit=json.loads(cmd(['docker','version','--format','{{json .Server}}']))['GitCommit'],api_version=json.loads(cmd(['docker','version','--format','{{json .Server}}']))['ApiVersion'],protected_roots=[info['DockerRootDir']],protected_cgroups=['/sys/fs/cgroup'+control])))
'''
        upload('/home/ubuntu/powerloss-bootstrap.py',bootstrap.encode())
        record['artifacts']=json.loads(guest('python3 /home/ubuntu/powerloss-bootstrap.py',600))
        record['guest_identity']=guest('id; uname -a; python3 --version; cat /proc/sys/kernel/random/boot_id').decode()
        atomic_json(output/'ownership.json',record)
        invoke('prepare')
        deadline=time.monotonic()+180
        while True:
            try:
                boundary=json.loads(guest('cat /home/ubuntu/powerloss-evidence/powerloss-boundary.json',10));break
            except subprocess.SubprocessError:
                if time.monotonic()>deadline:raise TimeoutError('New recovery powerloss boundary absent')
                time.sleep(1)
        record['boundary']=boundary;atomic_json(output/'ownership.json',record)
        # Abrupt exact-owned QEMU kill: no guest shutdown and no shared machine.
        process.kill();process.wait(timeout=30)
        record['vm_attempts'][-1]['exit_proven']={'returncode':process.returncode}
        log.close();process=None;log=None
        record['hard_power_loss_injected']=True;atomic_json(output/'ownership.json',record)
        boot()
        new_boot=guest('cat /proc/sys/kernel/random/boot_id').decode().strip()
        if new_boot==boundary['boot_id']:raise RuntimeError('Actual guest reboot not proven')
        record['postboot_id']=new_boot;atomic_json(output/'ownership.json',record)
        unit=invoke('restore')
        deadline=time.monotonic()+240
        while True:
            state=guest('systemctl --user show '+unit+' --property=ActiveState --property=Result').decode()
            if 'ActiveState=inactive' in state and 'Result=success' in state:break
            if 'ActiveState=failed' in state or time.monotonic()>deadline:raise RuntimeError('Postboot fresh recovery unit failed: '+state)
            time.sleep(1)
        result=json.loads(guest('cat /home/ubuntu/powerloss-evidence/restore-driver/driver.json'))
        if result.get('native_acceptance_passed') is not True or result.get('cleanup',{}).get('cleanup_complete') is not True:
            raise RuntimeError('Postboot source-bound restoration or cleanup incomplete')
        record['native_result']=result;record['passed']=True
    except BaseException as error:
        original=error;record['error_type']=type(error).__name__
        if isinstance(error,subprocess.CalledProcessError):
            try:(output/'failed-command.log').write_bytes((error.output or b'')[-1024*1024:])
            except BaseException as publication:error.add_note('Private failed output publication failed: '+type(publication).__name__)
    finally:
        errors=[]
        def attempt(step,action):
            try:action()
            except BaseException as error:errors.append({'step':step,'error_type':type(error).__name__})
        if process is not None and process.poll() is None:
            attempt('guest_unit_journal',lambda:guest('journalctl --user --no-pager > /home/ubuntu/powerloss-evidence/unit.log',30))
            def collect():
                with (output/'guest-evidence.tar').open('wb') as stream:
                    subprocess.run(ssh+['tar -cf - -C /home/ubuntu powerloss-evidence powerloss-artifacts'],stdout=stream,check=True,timeout=180)
            attempt('private_evidence_collection',collect)
        for entry in record['vm_attempts']:
            if not entry.get('exit_proven'):attempt('owned_vm_stop',lambda entry=entry:owned_vm.stop(entry))
        if process is not None:attempt('owned_vm_wait',lambda:process.wait(timeout=30))
        if log is not None:attempt('boot_log_close',log.close)
        record['owned_vm_stopped']=not any(item['step'] in {'owned_vm_stop','owned_vm_wait'} for item in errors)
        def verify_originals():
            record['original_disk_unchanged']=sha(base/'disk.qcow2')==originals['disk']
            record['original_vars_unchanged']=sha(base/'vars.fd')==originals['vars']
            if not record['original_disk_unchanged'] or not record['original_vars_unchanged']:raise RuntimeError('Protected originals changed')
        attempt('protected_originals',verify_originals)
        record['cleanup_errors']=errors;record['passed']=record['passed'] and not errors and record['owned_vm_stopped']
        attempt('final_receipt',lambda:atomic_json(output/'ownership.json',record))
        if errors:
            record['passed']=False
            attempt('failed_final_receipt',lambda:atomic_json(output/'ownership.json',record))
        if original is not None:
            if errors:original.add_note('Independent VM cleanup errors: '+repr(errors))
            raise original
        if errors:raise RuntimeError('VM finalization incomplete')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--review-packet',type=Path)
    parser.add_argument('--cleanup',action='store_true')
    args=parser.parse_args()
    print(json.dumps(run(args.base,args.output,args.source,args.review_packet,args.cleanup)))
