"""Provision only a disposable ARM64 VM and hard-kill its owned QEMU process."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import uuid
from deploy.recovery_journal import atomic_json, safe_path

BASE_URL = 'https://cloud-images.ubuntu.com/noble/20260926/'
BASE_NAME = 'noble-server-cloudimg-arm64.img'


def command(argv, timeout=120):
    return subprocess.check_output(argv, stderr=subprocess.STDOUT, text=True, timeout=timeout)


def ssh_argv(root, port):
    return ['ssh', '-i', str(root / 'key'), '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=accept-new',
            '-o', 'UserKnownHostsFile=' + str(root / 'known_hosts'), '-o', 'ConnectTimeout=3',
            '-p', str(port), 'ubuntu@127.0.0.1']


def run(root, source):
    root = safe_path(root)
    root.mkdir(mode=0o700, exist_ok=True)
    if root.stat().st_mode & 0o077:
        raise ValueError('Private task-owned directory required')
    base = root / 'base.qcow2'
    if not base.exists():
        command(['curl', '-fL', '--retry', '3', '-o', str(base), BASE_URL + BASE_NAME], 1200)
    sums = command(['curl', '-fsSL', BASE_URL + 'SHA256SUMS'])
    expected = next(line.split()[0] for line in sums.splitlines() if line.split()[-1].lstrip('*') == BASE_NAME)
    actual = hashlib.sha256(base.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError('Official Ubuntu checksum mismatch')
    if (root / 'disk.qcow2').exists():
        raise ValueError('Refuse to overwrite existing VM disk')
    command(['ssh-keygen', '-t', 'ed25519', '-N', '', '-f', str(root / 'key')])
    seed = root / 'seed'
    seed.mkdir(mode=0o700)
    instance = 'recovery-powerloss-' + uuid.uuid4().hex
    (seed / 'meta-data').write_text('instance-id: ' + instance + '\nlocal-hostname: recovery-powerloss\n')
    public_key = (root / 'key.pub').read_text().strip()
    (seed / 'user-data').write_text('''#cloud-config
users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: [sudo]
    shell: /bin/bash
    ssh_authorized_keys:
      - KEY
ssh_pwauth: false
package_update: true
packages: [uidmap, dbus-user-session, slirp4netns, fuse-overlayfs, ca-certificates, curl, python3]
write_files:
  - path: /etc/sysctl.d/99-disposable-rootless.conf
    content: |
      kernel.apparmor_restrict_unprivileged_userns=0
runcmd:
  - [sysctl, --system]
  - [sh, -c, "curl -fsSL https://get.docker.com | sh"]
  - [systemctl, disable, --now, docker.service, docker.socket]
  - [loginctl, enable-linger, ubuntu]
  - [sh, -c, "sudo -u ubuntu XDG_RUNTIME_DIR=/run/user/1000 dockerd-rootless-setuptool.sh install"]
  - [sh, -c, "touch /home/ubuntu/provisioned"]
'''.replace('KEY', public_key))
    command(['hdiutil', 'makehybrid', '-iso', '-joliet', '-default-volume-name', 'cidata',
             '-o', str(root / 'seed.iso'), str(seed)])
    command(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(base), str(root / 'disk.qcow2'), '16G'])
    firmware = Path('/opt/homebrew/share/qemu')
    shutil.copyfile(firmware / 'edk2-arm-vars.fd', root / 'vars.fd')
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    argv = ['qemu-system-aarch64', '-machine', 'virt,highmem=off', '-accel', 'hvf', '-cpu', 'host',
            '-smp', '2', '-m', '2048', '-nographic', '-monitor', 'none',
            '-drive', 'if=pflash,format=raw,readonly=on,file=' + str(firmware / 'edk2-aarch64-code.fd'),
            '-drive', 'if=pflash,format=raw,file=' + str(root / 'vars.fd'),
            '-drive', 'if=virtio,format=qcow2,file=' + str(root / 'disk.qcow2'),
            '-drive', 'if=virtio,format=raw,readonly=on,file=' + str(root / 'seed.iso'),
            '-netdev', 'user,id=net0,hostfwd=tcp:127.0.0.1:' + str(port) + '-:22',
            '-device', 'virtio-net-pci,netdev=net0']
    atomic_json(root / 'ownership.json', {'instance': instance, 'port': port, 'base_sha256': actual,
                                        'source_commit': command(['git', '-C', str(source), 'rev-parse', 'HEAD']).strip(),
                                        'source_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                        'qemu_argv': argv})
    processes = []
    def boot(number):
        log = (root / ('boot-' + str(number) + '.log')).open('w')
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        processes.append((process, log))
        deadline = time.monotonic() + 1200
        while True:
            if process.poll() is not None:
                raise RuntimeError('Owned QEMU process exited; inspect boot log')
            try:
                command(ssh_argv(root, port) + ['test -f ~/provisioned'], 10)
                return process
            except subprocess.SubprocessError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('VM provisioning readiness deadline exceeded')
                time.sleep(5)
    try:
        process = boot(1)
        files = ['deploy/recovery_journal.py', 'deploy/native_recovery_acceptance.py', 'deploy/qemu_recovery_guest.py']
        archive = root / 'source.tar'
        command(['tar', '-cf', str(archive), '-C', str(source), *files])
        ownership = json.loads((root / 'ownership.json').read_text())
        ownership['guest_source_sha256'] = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in files}
        ownership['guest_archive_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        atomic_json(root / 'ownership.json', ownership)
        with archive.open('rb') as stream:
            subprocess.run(ssh_argv(root, port) + ['mkdir -p ~/source && tar -xf - -C ~/source'],
                           stdin=stream, check=True, timeout=60)
        baseline = command(ssh_argv(root, port) + ['cd ~/source && python3 -m deploy.qemu_recovery_guest prepare'], 300)
        (root / 'baseline.json').write_text(baseline)
        # SIGKILL to this exact owned emulator simulates abrupt guest power loss;
        # no guest shutdown, live-host process, or shared host is targeted.
        process.kill()
        process.wait(timeout=30)
        process = boot(2)
        result = command(ssh_argv(root, port) + ['cd ~/source && python3 -m deploy.qemu_recovery_guest reconcile'], 300)
        (root / 'result.json').write_text(result)
        atomic_json(root / 'host-result.json', {'hard_power_loss_injected': True, 'rebooted': True,
                                              'guest_result': json.loads(result), 'owned_vm_stopped': False})
    finally:
        for process, log in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=30)
            log.close()
        final = root / 'host-result.json'
        if final.exists():
            outcome = json.loads(final.read_text())
            outcome['owned_vm_stopped'] = True
            atomic_json(final, outcome)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    os.umask(0o077)
    run(args.output, args.source)
