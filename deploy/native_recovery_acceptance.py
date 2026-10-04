"""Disposable native recovery fault suite; no staging inputs, mounts, or ports."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from deploy.recovery_journal import Journal, atomic_json, restore_service, safe_path


def command(argv):
    return subprocess.check_output(argv, text=True, stderr=subprocess.PIPE, timeout=90).strip()


def process_identity(pid, proc_root=Path('/proc')):
    root = proc_root / str(pid)
    stat = (root / 'stat').read_text()
    return {'pid': pid, 'start_ticks': int(stat[stat.rindex(')') + 2:].split()[19]),
            'cmdline': (root / 'cmdline').read_bytes().hex(), 'uid': root.stat().st_uid,
            'boot_id': (proc_root / 'sys/kernel/random/boot_id').read_text().strip()}


def stop_owned_child(root):
    """Cancel only the durably identified fixture process, never a reused PID."""
    identity = json.loads((root / 'owner-process.json').read_text())
    pid = identity['pid']
    try:
        current = process_identity(pid)
    except FileNotFoundError:
        return {'already_stopped': True}
    if current != identity or current['uid'] != os.getuid():
        raise RuntimeError('Fixture process ownership mismatch')
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('Native pidfd cancellation is required')
    try:
        descriptor = os.pidfd_open(pid)
    except ProcessLookupError:
        return {'already_stopped': True}
    try:
        if process_identity(pid) != identity:
            raise RuntimeError('Fixture process changed before cancellation')
        signal.pidfd_send_signal(descriptor, signal.SIGTERM)
    except (ProcessLookupError, FileNotFoundError):
        return {'already_stopped': True}
    finally:
        os.close(descriptor)
    return {'cancellation_sent': True}


def child(root, boundary, fail_cleanup):
    lock = (root / 'lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    operation = Journal(root / 'operation.json', {})
    if not operation.data['cleanup_complete']:
        operation.cleanup()
    identities = json.loads((root / 'identities.json').read_text())
    operation.services([], {'web': True, 'coordinator': True}, identities)
    for identifier in identities.values():
        command(['docker', 'container', 'stop', identifier])
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: (_ for _ in ()).throw(InterruptedError()))
    try:
        atomic_json(root / 'owner-process.json', process_identity(os.getpid()))
        atomic_json(root / 'boundary.json', {'boundary': boundary})
        time.sleep(300)
    finally:
        if fail_cleanup:
            import deploy.recovery_journal as module
            original = module.restore_service
            def fail_one(identifier, running):
                if identifier == identities['web']:
                    raise RuntimeError('synthetic cleanup failure')
                return original(identifier, running)
            module.restore_service = fail_one
        operation.cleanup()


def wait_boundary(process, root):
    deadline = time.monotonic() + 30
    while not (root / 'boundary.json').exists():
        if process.poll() is not None or time.monotonic() >= deadline:
            raise RuntimeError('Native fault driver did not reach boundary')
        time.sleep(0.1)


def run(args):
    root = safe_path(args.output)
    root.mkdir(mode=0o700)
    project = 'recovery-test-' + uuid.uuid4().hex
    import re
    if not re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}', args.image):
        raise ValueError('Preloaded immutable Alpine-compatible fixture image required')
    compose = root / 'compose.yaml'
    compose.write_text('''services:
  migrate:
    image: IMAGE
    pull_policy: never
    command: [sh, -c, "echo invocation >> /state/migrations"]
    volumes: ["state:/state"]
  web:
    image: IMAGE
    pull_policy: never
    command: [sleep, "3600"]
    volumes: ["state:/state:ro"]
    healthcheck: {test: [CMD, "true"], interval: 1s, timeout: 1s, retries: 10}
    depends_on: {migrate: {condition: service_completed_successfully}}
  coordinator:
    image: IMAGE
    pull_policy: never
    command: [sleep, "3600"]
    depends_on: {migrate: {condition: service_completed_successfully}}
volumes:
  state:
'''.replace('IMAGE', args.image))
    argv = ['docker', 'compose', '-p', project, '-f', str(compose)]
    atomic_json(root / 'ownership.json', {'project': project, 'image': args.image, 'source': command(['git', 'rev-parse', 'HEAD'])})
    results = []
    children = []
    cleanup = False
    try:
        command(argv + ['up', '-d', 'web', 'coordinator'])
        identities = {role: command(argv + ['ps', '-aq', role]) for role in ('web', 'coordinator')}
        atomic_json(root / 'identities.json', identities)
        for identifier in identities.values():
            restore_service(identifier, True)
        migrate = command(argv + ['ps', '-aq', 'migrate'])
        baseline = json.loads(command(['docker', 'inspect', migrate]))[0]['State']
        for fault in ('SIGTERM', 'SIGKILL', 'connection_loss', 'cleanup_failure'):
            (root / 'boundary.json').unlink(missing_ok=True)
            driver = [sys.executable, '-m', 'deploy.native_recovery_acceptance', '--child',
                      '--output', str(root), '--boundary', fault]
            if fault == 'cleanup_failure':
                driver += ['--fail-cleanup']
            log = (root / (fault + '.log')).open('w')
            process = subprocess.Popen(driver, stdout=log, stderr=log)
            children.append(process)
            wait_boundary(process, root)
            rival = subprocess.run(driver, capture_output=True, timeout=15)
            if rival.returncode == 0:
                raise RuntimeError('Concurrent recovery ownership was not rejected')
            # Connection-loss surrogate kills the owning process; actual transport
            # faults and host power loss need the separate disposable-VM protocol.
            process.send_signal(signal.SIGTERM if fault in ('SIGTERM', 'cleanup_failure') else signal.SIGKILL)
            process.wait(timeout=90)
            log.close()
            operation = Journal(root / 'operation.json', {})
            if fault == 'cleanup_failure':
                if operation.data.get('cleanup_errors') != ['service:web']:
                    raise RuntimeError('Independent cleanup failure was not recorded')
                state = json.loads(command(['docker', 'inspect', identities['coordinator']]))[0]['State']
                if not state['Running']:
                    raise RuntimeError('Independent coordinator cleanup was skipped')
            atomic_json(root / (fault + '-interrupted.json'), operation.data)
            operation.cleanup()
            operation.cleanup()
            atomic_json(root / (fault + '-reconciled.json'), operation.data)
            if not operation.data['cleanup_complete']:
                raise RuntimeError('Repeated cleanup failed')
            if identities != {role: command(argv + ['ps', '-aq', role]) for role in identities}:
                raise RuntimeError('Service identity changed')
            if json.loads(command(['docker', 'inspect', migrate]))[0]['State'] != baseline:
                raise RuntimeError('Migration container was activated during restoration')
            if command(['docker', 'exec', identities['web'], 'cat', '/state/migrations']) != 'invocation':
                raise RuntimeError('Migration invocation count changed')
            results.append({'fault': fault, 'passed': True})
            atomic_json(root / 'results.json', {'cases': results, 'cleanup_complete': False})
    finally:
        for process in children:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=30)
        # Unique project owns only the fixture resources created by this invocation.
        command(argv + ['down', '-v', '--remove-orphans'])
        resource_filter = 'label=com.docker.compose.project=' + project
        cleanup = not any(command(argv) for argv in (
            ['docker', 'ps', '-aq', '--filter', resource_filter],
            ['docker', 'volume', 'ls', '-q', '--filter', resource_filter],
            ['docker', 'network', 'ls', '-q', '--filter', resource_filter],
        ))
        atomic_json(root / 'results.json', {'cases': results, 'cleanup_complete': cleanup,
                                           'native_service_suite_passed': len(results) == 4 and cleanup,
                                           'actual_power_loss_passed': False,
                                           'actual_connection_loss_passed': False})
    if not cleanup:
        raise RuntimeError('Disposable fixture cleanup incomplete')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image')
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--boundary', default='maintenance')
    parser.add_argument('--fail-cleanup', action='store_true')
    options = parser.parse_args()
    os.umask(0o077)
    if options.child:
        child(options.output, options.boundary, options.fail_cleanup)
    else:
        if not options.image:
            parser.error('--image is required')
        run(options)
