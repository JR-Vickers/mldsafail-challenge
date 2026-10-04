"""Disposable native recovery fault suite; no staging inputs, mounts, or ports."""
import argparse
import fcntl
import hashlib
import platform
import re
import stat
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from deploy.recovery_journal import Journal, atomic_json, restore_service, safe_path


_OPERATION = None


def command(argv):
    if _OPERATION is None:
        raise ValueError('Durable fixture ownership required')
    selected = os.environ.get('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST')
    if not selected:
        raise ValueError('Dedicated disposable daemon manifest required')
    return _OPERATION.command(argv, daemon_manifest_path=selected, text=True,
                              capture_output=True, check=True, timeout=90).stdout.strip()


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


def quiesce_owned_child(root):
    """A retained exact pidfd must report exit before any daemon restart."""
    import select
    identity = json.loads((root/'owner-process.json').read_text())
    try:
        current = process_identity(identity['pid'])
    except FileNotFoundError:
        return
    if current != identity or current['uid'] != os.getuid():
        raise RuntimeError('Fixture owner identity changed; daemon restart prohibited')
    descriptor = os.pidfd_open(identity['pid'])
    try:
        if process_identity(identity['pid']) != identity:
            raise RuntimeError('Fixture owner changed before pidfd cancellation')
        signal.pidfd_send_signal(descriptor, signal.SIGKILL)
        poller = select.poll()
        poller.register(descriptor, select.POLLIN)
        if not poller.poll(30000):
            raise RuntimeError('Fixture owner exit not proven; daemon restart prohibited')
    finally:
        os.close(descriptor)


def child(root, boundary, fail_cleanup):
    lock = (root / 'lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    operation = Journal(root / 'operation.json', {})
    if not operation.data['cleanup_complete']:
        operation.cleanup()
    identities = json.loads((root / 'identities.json').read_text())
    global _OPERATION
    _OPERATION = operation
    selected = os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST']
    operation.services([], {'web': True, 'coordinator': True}, identities, daemon_manifest_path=selected)
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
            def fail_one(identifier, running, **kwargs):
                if identifier == identities['web']:
                    raise RuntimeError('synthetic cleanup failure')
                return original(identifier, running, **kwargs)
            module.restore_service = fail_one
        operation.cleanup()


def wait_boundary(process, root):
    deadline = time.monotonic() + 30
    while not (root / 'boundary.json').exists():
        if process.poll() is not None or time.monotonic() >= deadline:
            raise RuntimeError('Native fault driver did not reach boundary')
        time.sleep(0.1)


def wait_child(pid, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        waited, status = os.waitpid(pid, os.WNOHANG)
        if waited:
            return status
        time.sleep(.05)
    raise TimeoutError('Owned fixture child did not exit')


def cleanup_fixture(root, ownership, results):
    """Independent creator, journal, project, inventory, and receipt cleanup."""
    global _OPERATION
    errors = []
    def attempt(label, action):
        try:
            return action()
        except BaseException as error:
            errors.append({'step': label, 'error_type': type(error).__name__})
    if (root/'owner-process.json').exists():
        attempt('fixture_owner_stop', lambda: quiesce_owned_child(root))
    if errors:
        # An unfenced fault owner could submit a request after daemon restart.
        # Preserve its journals and refuse further mutations until exact repair.
        atomic_json(root/(uuid.uuid4().hex+'-owner-fence.json'), {'cleanup_complete':False,'errors':errors})
        raise RuntimeError('Fixture owner quiescence not proven')
    child_journal = Journal(root/'operation.json', {})
    attempt('interrupted_service_restoration', child_journal.cleanup)
    _OPERATION = Journal(root/'driver-operation.json', {})
    attempt('driver_epoch_reconciliation', _OPERATION.cleanup)
    argv = ['docker', 'compose', '-p', ownership['project'], '-f', str(root/'compose.yaml')]
    attempt('project_removal', lambda: command(argv+['down', '-v', '--remove-orphans']))
    attempt('post_removal_epoch_reconciliation', _OPERATION.cleanup)
    resource_filter = 'label=com.docker.compose.project='+ownership['project']
    for kind, argv in (
        ('containers', ['docker','ps','-aq','--filter',resource_filter]),
        ('volumes', ['docker','volume','ls','-q','--filter',resource_filter]),
        ('networks', ['docker','network','ls','-q','--filter',resource_filter])):
        def inventory(argv=argv):
            if command(argv):
                raise RuntimeError('Owned fixture resource remains')
        attempt('final_'+kind, inventory)
    report = dict(schema='mldsafail.native-recovery-faults.v2', source=ownership['source'],
        source_script_sha256=ownership['source_script_sha256'], daemon_fingerprint=ownership['daemon_fingerprint'],
        image=ownership['image'], python=sys.version, kernel=platform.release(), cases=results,
        cleanup_complete=not errors, cleanup_errors=errors,
        native_service_suite_passed=len(results)==4 and not errors,
        actual_power_loss_passed=False, actual_connection_loss_passed=False)
    attempt('cleanup_receipt', lambda: atomic_json(root/(uuid.uuid4().hex+'-cleanup.json'), report))
    report.update(cleanup_complete=not errors, native_service_suite_passed=len(results)==4 and not errors)
    atomic_json(root/'results.json', report)
    if errors:
        raise RuntimeError('Disposable fixture cleanup incomplete')
    return report


def run(args):
    from deploy.recovery_daemon import operation_lock, scope
    from deploy import owned_daemon
    root = safe_path(args.output)
    cleanup_only = getattr(args, 'cleanup', False)
    if not cleanup_only and not re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}', args.image or ''):
        raise ValueError('Preloaded immutable Alpine-compatible fixture image required')
    if sys.platform != 'linux':
        raise ValueError('Native Linux required')
    selected = os.environ.get('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST')
    if cleanup_only:
        ownership = owned_daemon.read_private_json(root/'ownership.json')
        selected = ownership['daemon_manifest_path']
    if not selected:
        raise ValueError('Explicit dedicated disposable daemon manifest required')
    parent = root.parent
    info = parent.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Private owned fixture parent required')
    descriptor = os.open(parent/('.'+root.name+'.lock'), os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise ValueError('Private owned fixture lock required')
        fcntl.flock(descriptor, fcntl.LOCK_EX|fcntl.LOCK_NB)
        with operation_lock(selected), scope(selected, verify=not cleanup_only):
            if cleanup_only:
                if not re.fullmatch(r'recovery-test-[a-f0-9]{32}', ownership['project']):
                    raise ValueError('Disposable project ownership mismatch')
                results_path = root/'results.json'
                results = owned_daemon.read_private_json(results_path).get('cases',[]) if results_path.exists() else []
                return cleanup_fixture(root, ownership, results)
            return execute_fixture(args, root, selected)
    finally:
        os.close(descriptor)


def execute_fixture(args, root, selected):
    global _OPERATION
    from deploy import owned_daemon
    source_root = Path(__file__).resolve().parents[1]
    source = subprocess.check_output(['git','-C',str(source_root),'rev-parse','HEAD'], text=True).strip()
    if subprocess.check_output(['git','-C',str(source_root),'status','--porcelain'], text=True):
        raise ValueError('Retained clean source required')
    root.mkdir(mode=0o700)
    project = 'recovery-test-'+uuid.uuid4().hex
    compose = root/'compose.yaml'
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
    manifest = owned_daemon.load_manifest(selected)
    ownership = {'project':project, 'image':args.image, 'source':source,
        'source_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'daemon_manifest_path':str(selected), 'daemon_fingerprint':owned_daemon.fingerprint(manifest)}
    atomic_json(root/'ownership.json', ownership)
    _OPERATION = Journal(root/'driver-operation.json', {})
    argv = ['docker','compose','-p',project,'-f',str(compose)]
    results = []
    children = []
    original = None
    try:
        image_info = json.loads(command(['docker','image','inspect',args.image]))[0]
        if image_info.get('Config',{}).get('Volumes'):
            raise ValueError('Fixture image must not create anonymous volumes')
        command(argv+['up','-d','web','coordinator'])
        identities = {role:command(argv+['ps','-aq',role]) for role in ('web','coordinator')}
        if any(not re.fullmatch(r'[a-f0-9]{64}', value) for value in identities.values()):
            raise ValueError('Exact pinned fixture service IDs required')
        atomic_json(root/'identities.json', identities)
        for identifier in identities.values():
            restore_service(identifier, True, runner=lambda argv, **kwargs: _OPERATION.command(
                argv, daemon_manifest_path=selected, **kwargs))
        migrate = command(argv+['ps','-aq','migrate'])
        baseline = json.loads(command(['docker','inspect',migrate]))[0]['State']
        for fault in ('SIGTERM','SIGKILL','connection_loss','cleanup_failure'):
            (root/'boundary.json').unlink(missing_ok=True)
            read_gate, write_gate = os.pipe()
            pid = os.fork()
            if pid == 0:
                os.close(write_gate)
                try:
                    if os.read(read_gate,1) != b'1': os._exit(2)
                    os.close(read_gate)
                    with (root/(fault+'.log')).open('w') as log:
                        os.dup2(log.fileno(),1); os.dup2(log.fileno(),2)
                        child(root,fault,fault=='cleanup_failure')
                    os._exit(0)
                except BaseException:
                    import traceback
                    traceback.print_exc()
                    os._exit(1)
            os.close(read_gate)
            children.append(pid)
            try:
                atomic_json(root/'owner-process.json', process_identity(pid))
                os.write(write_gate,b'1')  # No Docker mutation before durable fork ownership.
            finally:
                os.close(write_gate)
            deadline = time.monotonic()+30
            while not (root/'boundary.json').exists():
                if time.monotonic()>=deadline: raise TimeoutError('Fixture boundary absent')
                time.sleep(.1)
            rival = subprocess.run([sys.executable,'-m','deploy.native_recovery_acceptance','--child',
                '--output',str(root),'--boundary','race'],capture_output=True,timeout=15)
            if (rival.returncode != 73 or json.loads(rival.stdout) !=
                    {'ownership_rejected':'run_lock_contended'}):
                raise RuntimeError('Concurrent recovery rejection did not prove lock contention')
            os.kill(pid, signal.SIGTERM if fault in ('SIGTERM','cleanup_failure') else signal.SIGKILL)
            wait_child(pid,90)
            children.remove(pid)
            atomic_json(root/(fault+'-owner-process.json'), json.loads((root/'owner-process.json').read_text()))
            (root/'owner-process.json').unlink()
            from deploy.recovery_journal import sync_directory
            sync_directory(root)
            operation = Journal(root/'operation.json',{})
            if fault=='cleanup_failure':
                if 'service:web' not in operation.data.get('cleanup_errors',[]):
                    raise RuntimeError('Independent cleanup failure absent')
                if not json.loads(command(['docker','inspect',identities['coordinator']]))[0]['State']['Running']:
                    raise RuntimeError('Independent coordinator restoration skipped')
            atomic_json(root/(fault+'-interrupted.json'),operation.data)
            operation.cleanup(); operation.cleanup()
            atomic_json(root/(fault+'-reconciled.json'),operation.data)
            if identities!={role:command(argv+['ps','-aq',role]) for role in identities}:
                raise RuntimeError('Service identity changed')
            if json.loads(command(['docker','inspect',migrate]))[0]['State']!=baseline:
                raise RuntimeError('Migration container activated during restoration')
            if command(['docker','exec',identities['web'],'cat','/state/migrations'])!='invocation':
                raise RuntimeError('Migration invocation count changed')
            results.append({'fault':fault,'passed':True})
            atomic_json(root/'results.json',{'cases':results,'cleanup_complete':False})
    except BaseException as error:
        original = error
    finally:
        child_errors = []
        for pid in children:
            try:
                # These are still-unreaped direct fork children; their PIDs cannot be reused.
                os.kill(pid,signal.SIGKILL)
            except ProcessLookupError: pass
            except BaseException as error: child_errors.append(type(error).__name__)
            try: wait_child(pid,30)
            except BaseException as error: child_errors.append(type(error).__name__)
        try:
            report = cleanup_fixture(root,ownership,results)
            if child_errors: raise RuntimeError('Owned fork children not proven reaped: '+repr(child_errors))
        except BaseException as error:
            if original is None: original=error
            else: original.add_note('Independent fixture cleanup failed: '+type(error).__name__)
    if original is not None: raise original
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image')
    parser.add_argument('--cleanup', action='store_true')
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--boundary', default='maintenance')
    parser.add_argument('--fail-cleanup', action='store_true')
    options = parser.parse_args()
    os.umask(0o077)
    if options.child:
        try:
            child(options.output, options.boundary, options.fail_cleanup)
        except BlockingIOError:
            print(json.dumps({'ownership_rejected':'run_lock_contended'}))
            raise SystemExit(73)
    else:
        if not options.image and not options.cleanup:
            parser.error('--image is required')
        print(json.dumps(run(options)))
