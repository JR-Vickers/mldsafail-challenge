"""Run operator client faults on an isolated overlay of the retained local VM.

The original power-loss disk/firmware remain unchanged. No VPS operations.
"""
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
from deploy.qemu_recovery_powerloss import ssh_argv
from deploy import owned_vm
from deploy.recovery_journal import atomic_json, safe_path


def _execute_locked(base, output, source, gate="operator", artifacts=None):
    base, output, source = map(safe_path, (base, output, source))
    if output.exists(): raise ValueError('Fresh owned VM output required')
    output.mkdir(mode=0o700)
    os.umask(0o077)
    def command(argv, timeout=120):
        return subprocess.check_output(argv, stderr=subprocess.STDOUT, timeout=timeout)
    if command(['git', '-C', str(source), 'status', '--porcelain']):
        raise ValueError('Clean retained source required')
    commit = command(['git', '-C', str(source), 'rev-parse', 'HEAD']).decode().strip()
    original_disk = hashlib.sha256((base / 'disk.qcow2').read_bytes()).hexdigest()
    original_vars = hashlib.sha256((base / 'vars.fd').read_bytes()).hexdigest()
    command(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(base / 'disk.qcow2'), str(output / 'disk.qcow2')])
    for name in ('key', 'key.pub', 'vars.fd'):
        shutil.copyfile(base / name, output / name)
        (output / name).chmod(0o600)
    command(['git', '-C', str(source), 'bundle', 'create', str(output / 'source.bundle'), 'HEAD'])
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0)); port = reservation.getsockname()[1]
    previous = json.loads((base / 'ownership.json').read_text())['qemu_argv']
    argv = [value.replace(str(base / 'vars.fd'), str(output / 'vars.fd'))
            .replace(str(base / 'disk.qcow2'), str(output / 'disk.qcow2')) for value in previous]
    index = argv.index('-netdev') + 1
    argv[index] = 'user,id=net0,hostfwd=tcp:127.0.0.1:' + str(port) + '-:22'
    unit = 'mldsafail-owned-client-' + uuid.uuid4().hex + '.service'
    if gate not in {'operator', 'synthetic-s3'}:
        raise ValueError('Unsupported disposable native gate')
    if gate == 'synthetic-s3' and artifacts is None:
        raise ValueError('Pinned synthetic native artifacts required')
    outcome = {'source_commit': commit, 'qemu_argv': argv, 'port': port,
               'original_disk_sha256': original_disk, 'original_vars_sha256': original_vars,
               'bundle_sha256': hashlib.sha256((output / 'source.bundle').read_bytes()).hexdigest(),
               'unit': unit, 'gate': gate, 'passed': False, 'owned_vm_stopped': False}
    atomic_json(output / 'ownership.json', outcome)
    log = (output / 'boot.log').open('wb')
    process = None
    original = None
    ssh = ssh_argv(output, port)
    def publish_vm(entry):
        outcome['vm_client'] = entry
        atomic_json(output / 'ownership.json', outcome)
    try:
        process, entry = owned_vm.spawn(argv, publish_vm, log)
        deadline = time.monotonic() + 240
        while True:
            try:
                command(ssh + ['systemctl is-active --quiet multi-user.target'], 10); break
            except subprocess.SubprocessError:
                if process.poll() is not None or time.monotonic() >= deadline: raise RuntimeError('VM boot health gate failed')
                time.sleep(1)
        command(ssh + ['sudo apt-get -qq update && sudo apt-get -qq install -y git'], 300)
        with (output / 'source.bundle').open('rb') as stream:
            subprocess.run(ssh + ['cat > /home/ubuntu/operator-source.bundle'], stdin=stream, stdout=subprocess.DEVNULL, check=True, timeout=120)
        command(ssh + ['git clone -q /home/ubuntu/operator-source.bundle /home/ubuntu/operator-source && git -C /home/ubuntu/operator-source checkout -q ' + commit + ' && mkdir -m700 /home/ubuntu/operator-evidence'], 120)
        outcome['guest_identity'] = command(ssh + ['uname -a; python3 --version; git -C /home/ubuntu/operator-source rev-parse HEAD; cat /proc/sys/kernel/random/boot_id']).decode()
        atomic_json(output / 'ownership.json', outcome)
        if gate == 'synthetic-s3':
            import tarfile
            artifacts = safe_path(artifacts)
            bundle = output / 'artifacts.tar'
            with tarfile.open(bundle, 'w') as archive:
                for name in ('artifacts.json', 'restic', 'minio'):
                    path = safe_path(artifacts / name)
                    if path.is_symlink() or not path.is_file():
                        raise ValueError('Pinned regular artifact required')
                    archive.add(path, arcname=name, recursive=False)
            outcome['artifacts_bundle_sha256'] = hashlib.sha256(bundle.read_bytes()).hexdigest()
            atomic_json(output / 'ownership.json', outcome)
            command(ssh + ['mkdir -m700 /home/ubuntu/native-artifacts'])
            with bundle.open('rb') as stream:
                subprocess.run(ssh + ['tar -xf - -C /home/ubuntu/native-artifacts'], stdin=stream,
                               stdout=subprocess.DEVNULL, check=True, timeout=180)
        parent = '/sys/fs/cgroup/system.slice/' + unit
        run = ['sudo', 'systemd-run', '--wait', '--collect', '--unit=' + unit,
               '--property=Delegate=yes', '--property=User=ubuntu', '--property=Group=ubuntu',
               '--property=WorkingDirectory=/home/ubuntu/operator-source',
               '--setenv=MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT=' + parent,
               '/usr/bin/python3', '-m',
               'deploy.native_owned_client_acceptance' if gate == 'operator' else 'deploy.native_synthetic_s3',
               '--output', '/home/ubuntu/operator-evidence/fresh-run']
        if gate == 'synthetic-s3':
            run += ['--artifacts', '/home/ubuntu/native-artifacts']
        try:
            outcome['native_output'] = command(ssh + [' '.join(run)], 900).decode()
        except subprocess.CalledProcessError as error:
            try: (output / 'failed-command.log').write_bytes(error.output)
            except BaseException as publication_error:
                error.add_note('Failure log publication failed: ' + type(publication_error).__name__)
            raise
        finally:
            # Evidence collection is independent; failures cannot skip VM stop.
            collection_errors = []
            try:
                command(ssh + ['sudo journalctl -u ' + unit + ' --no-pager > /home/ubuntu/operator-evidence/unit.log'], 30)
            except BaseException as error:
                collection_errors.append({'step': 'guest_journal', 'error_type': type(error).__name__})
            try:
                with (output / 'guest-evidence.tar').open('wb') as stream:
                    subprocess.run(ssh + ['tar -cf - -C /home/ubuntu operator-evidence'], stdout=stream, check=True, timeout=60)
            except BaseException as error:
                collection_errors.append({'step': 'guest_archive', 'error_type': type(error).__name__})
            outcome['collection_errors'] = collection_errors
        if collection_errors:
            raise RuntimeError('Native evidence collection incomplete')
        outcome['passed'] = True
    except BaseException as error:
        original = error
        outcome['error_type'] = type(error).__name__
    finally:
        errors = []
        def attempt(step, action):
            try: action()
            except BaseException as error: errors.append({'step': step, 'error_type': type(error).__name__})
        if process is not None:
            attempt('owned_vm_signal', lambda: process.kill() if process.poll() is None else None)
            attempt('owned_vm_wait', lambda: process.wait(timeout=30))
            outcome['owned_vm_stopped'] = process.poll() is not None
        elif outcome.get('vm_client'):
            def stop_receipt():
                owned_vm.stop(outcome['vm_client'])
                outcome['owned_vm_stopped'] = True
            attempt('owned_vm_receipt_cleanup', stop_receipt)
        attempt('boot_log_close', log.close)
        def originals():
            outcome['original_disk_unchanged'] = hashlib.sha256((base / 'disk.qcow2').read_bytes()).hexdigest() == original_disk
            outcome['original_vars_unchanged'] = hashlib.sha256((base / 'vars.fd').read_bytes()).hexdigest() == original_vars
            if not outcome['original_disk_unchanged'] or not outcome['original_vars_unchanged']:
                raise RuntimeError('Retained original VM evidence changed')
        attempt('original_evidence_check', originals)
        outcome['cleanup_errors'] = errors
        outcome['passed'] = outcome['passed'] and not errors
        attempt('final_report', lambda: atomic_json(output / 'ownership.json', outcome))
        if original is not None:
            if errors: original.add_note('Independent owned VM cleanup errors: ' + repr(errors))
            raise original
        if errors: raise RuntimeError('Owned VM cleanup incomplete: ' + repr(errors))
    return outcome


def execute(base, output, source, gate="operator", artifacts=None, cleanup_only=False):
    import fcntl
    import stat
    from deploy.recovery import private_file
    output = safe_path(output)
    lock = output.parent / ('.' + output.name + '.lock')
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Private owned VM run lock required')
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if cleanup_only:
            if output.stat().st_uid != os.getuid() or output.stat().st_mode & 0o077:
                raise ValueError('Private owned VM evidence directory required')
            record = json.loads(private_file(output / 'ownership.json').read_text())
            if not record.get('owned_vm_stopped'):
                if not record.get('vm_client'):
                    raise RuntimeError('VM cleanup requires exact durable native process identity')
                owned_vm.stop(record['vm_client'])
            result = {'owned_vm_stopped': True}
            atomic_json(output / ('cleanup-' + uuid.uuid4().hex + '.json'), result)
            return result
        return _execute_locked(base, output, source, gate, artifacts)
    finally:
        os.close(descriptor)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--gate', choices=['operator', 'synthetic-s3'], default='operator')
    parser.add_argument('--artifacts', type=Path)
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    if not args.cleanup and args.base is None: parser.error('--base required for native execution')
    print(json.dumps(execute(args.base, args.output, args.source, args.gate, args.artifacts, args.cleanup)))
