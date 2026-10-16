"""Run a trusted operator command inside its own delegated user service.

Invoke through systemd-run --user with Delegate=yes and KillMode=control-group.
The parent service identity and all child ownership receipts remain private.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deploy import owned_client
from deploy.recovery_journal import atomic_json, safe_path


def execute(unit, journal, argv, timeout):
    if sys.platform != 'linux' or os.getuid() == 0:
        raise RuntimeError('Native non-root user service required')
    if not unit.startswith('mldsafail-launch-') or not unit.endswith('.service') or '/' in unit:
        raise ValueError('Explicit owned launch service required')
    invocation = os.environ.get('INVOCATION_ID')
    if not invocation or len(invocation) != 32:
        raise RuntimeError('Systemd service invocation identity required')
    rows = Path('/proc/self/cgroup').read_text().splitlines()
    groups = [row.split('::', 1)[1] for row in rows if row.startswith('0::')]
    if len(groups) != 1 or Path(groups[0]).name != unit:
        raise RuntimeError('Controller must execute inside the named owned service')
    properties = dict(row.split('=', 1) for row in subprocess.check_output(
        ['systemctl', '--user', 'show', unit,
         '--property=InvocationID,Delegate,KillMode,ControlGroup,MainPID'],
        text=True, timeout=30).splitlines())
    if (properties.get('InvocationID') != invocation or properties.get('Delegate') != 'yes'
            or properties.get('KillMode') != 'control-group'
            or properties.get('ControlGroup') != groups[0]
            or properties.get('MainPID') != str(os.getpid())):
        raise RuntimeError('Actual service/controller identity differs from declared delegated invocation')
    parent = Path('/sys/fs/cgroup' + groups[0])
    identity = owned_client.domain_identity(parent)
    if identity['uid'] != os.getuid() or identity['mode'] & 0o022:
        raise RuntimeError('Exclusive delegated owner write access required')
    if (parent / 'cgroup.type').read_text().strip() != 'domain':
        raise RuntimeError('Native domain parent required')
    journal = safe_path(journal)
    if journal.exists() or not journal.parent.is_dir():
        raise RuntimeError('New private journal with existing protected parent required')
    info = journal.parent.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError('Private owner-held evidence directory required')
    if not argv or not 0 < timeout <= 7200:
        raise ValueError('Bounded operator command required')
    source = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True, timeout=30).strip()
    if subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True, timeout=30).strip():
        raise RuntimeError('Clean retained source required')
    state = {'source_commit': source, 'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'helper_sha256': hashlib.sha256((ROOT / 'deploy/owned_client.py').read_bytes()).hexdigest(),
             'command_sha256': hashlib.sha256(b'\0'.join(os.fsencode(arg) for arg in argv) + b'\0').hexdigest(),
             'unit': unit, 'invocation_id': invocation, 'service_properties': properties, 'controller': owned_client.identity(os.getpid()),
             'parent': identity, 'clients': [], 'complete': False, 'cleanup_complete': False}
    atomic_json(journal, state)
    env = dict(os.environ, MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT=str(parent))
    failure = None
    cleanup_errors = []
    try:
        with (journal.parent / 'command.stdout').open('xb') as out, (journal.parent / 'command.stderr').open('xb') as err:
            os.chmod(out.name, 0o600); os.chmod(err.name, 0o600)
            result = owned_client.run(argv, state['clients'], lambda: atomic_json(journal, state),
                                      journal.parent, timeout=timeout, env=env, stdout=out, stderr=err)
        state['returncode'] = result.returncode
    except BaseException as error:
        failure = error
        state['failure_class'] = type(error).__name__
        try:
            with (journal.parent / 'operator.failure.log').open('xb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(traceback.format_exc().encode()[:1024 * 1024])
                stream.flush()
                os.fsync(stream.fileno())
            state['failure_log'] = 'operator.failure.log'
        except BaseException as log_error:
            error.add_note('Private failure log publication failed: ' + type(log_error).__name__)
    finally:
        for entry in state['clients']:
            try:
                owned_client.stop(entry)
            except BaseException as error:
                cleanup_errors.append(type(error).__name__)
        state['cleanup_errors'] = cleanup_errors
        state['cleanup_complete'] = not cleanup_errors
        state['complete'] = failure is None and not cleanup_errors and state.get('returncode') == 0
        try:
            atomic_json(journal, state)
        except BaseException as error:
            if failure is None:
                failure = error
            else:
                failure.add_note('Final operator journal publication failed: ' + type(error).__name__)
    if failure is not None:
        raise failure
    if cleanup_errors:
        raise RuntimeError('Owned native command cleanup incomplete')
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit', required=True)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    try:
        result = execute(args.unit, args.journal, command, args.timeout)
        print(json.dumps({'native_operator_complete': result['complete'], 'cleanup_complete': result['cleanup_complete']}))
        return 0 if result['complete'] else 1
    except BaseException as error:
        print(json.dumps({'native_operator_failed': True, 'failure_class': type(error).__name__,
                          'private_evidence_retained': True}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
