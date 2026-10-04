"""Fresh per-activation owned daemon lifecycle; never installs or starts timers.

The generic provisioning driver must be independently reviewed and present in
the retained source. Each activation uses its actual delegated user unit and a
new private state root. Earlier incomplete activations require terminal cleanup
under the new controller before any new daemon is provisioned.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid
from deploy import owned_daemon


class ActivationContended(BlockingIOError):
    """Only the activation ownership flock emits the rejection marker."""


@contextmanager
def activation_lock(root):
    root = owned_daemon._canonical(root)
    owned_daemon._private_directory(root)
    descriptor = os.open(root/'activation.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise RuntimeError('Private regular activation ownership required')
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ActivationContended('Activation ownership is already held') from error
        yield root
    finally:
        os.close(descriptor)


def current_configuration(template, root, unit):
    if not re.fullmatch(r'mldsafail-[a-z0-9-]+\.service', unit):
        raise ValueError('Explicit named operator user unit required')
    lines = Path('/proc/self/cgroup').read_text().splitlines()
    memberships = [line[3:] for line in lines if line.startswith('0::')]
    if len(memberships) != 1:
        raise RuntimeError('One native unified cgroup membership required')
    parent = Path('/sys/fs/cgroup')/memberships[0].lstrip('/')
    # Driver independently compares this parent against the declared actual
    # systemd user unit, delegation, permissions and native source authority.
    config = dict(template, schema='mldsafail.owned-native-driver.v1',
                  state_root=str(root/('activation-'+uuid.uuid4().hex)),
                  operator_unit=unit, operator_parent=str(parent),
                  acceptance_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    return config


def fixture(journal, config, data):
    """Tiny fixed execution proves lifecycle plumbing, never benchmark quality."""
    name = 'mldsafail-activation-'+data['id']
    command = ['docker', 'create', '--name', name, '--label', 'mldsafail.activation='+data['id'],
               '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--pids-limit', '32',
               '--memory', '128m', '--cgroup-parent', data['worker_slice'],
               '--entrypoint', 'python', config['image'], '-I', '-c',
               'print("mldsafail-owned-activation-fixture-v1")']
    identifier = journal.command(command, kind='container_create').stdout.decode().strip()
    if not re.fullmatch('[a-f0-9]{64}', identifier):
        raise RuntimeError('Exact created container identity required')
    output = journal.command(['docker', 'start', '--attach', identifier], kind='container_start', timeout=20).stdout
    inspected = json.loads(journal.command(['docker', 'inspect', identifier]).stdout)
    if (len(inspected) != 1 or inspected[0]['Id'] != identifier or
        inspected[0]['Image'] != config['image'] or inspected[0]['Name'] != '/'+name or
        inspected[0]['Config']['Labels'].get('mldsafail.activation') != data['id'] or
        inspected[0]['State']['Running'] is not False or inspected[0]['State']['ExitCode'] != 0 or
        output != b'mldsafail-owned-activation-fixture-v1\n'):
        raise RuntimeError('Owned fixed fixture identity or output mismatch')
    receipt = journal.path.parent/'fixture.json'
    owned_daemon.publish(receipt, dict(passed=True, source_sha256=config['acceptance_source_sha256'],
        container_id=identifier, image=config['image'], worker_parent=data['worker_parent'],
        operator_parent=config['operator_parent'], output_sha256=hashlib.sha256(output).hexdigest()))
    return dict(schema='mldsafail.owned-native-acceptance.v1', passed=True, native_executed=True,
                evidence_refs=[str(receipt)], source_sha256=config['acceptance_source_sha256'])


def prior_complete(state, prior):
    if (state.get('schema') != 'mldsafail.cpu-native-driver-state.v1' or
        state.get('daemon_kind') != 'owned' or state.get('config', {}).get('state_root') != str(prior)):
        raise RuntimeError('Unknown prior activation driver authority')
    cleanup = state.get('cleanup', {})
    if cleanup.get('cleanup_complete') is not True:
        return False
    if (state.get('state') != 'complete' or cleanup.get('schema') != 'mldsafail.cpu-native-driver-cleanup.v1' or
        cleanup.get('id') != state.get('id') or cleanup.get('errors') != []):
        return False
    if state.get('start_intent'):
        if state.get('manifest_path') != str(prior/'daemon-manifest.json'):
            raise RuntimeError('Prior activation manifest root binding changed')
        manifest = owned_daemon.load_manifest(state['manifest_path'])
        barrier = cleanup.get('daemon_barrier', {})
        if (barrier.get('schema') != 'mldsafail.owned-daemon-barrier.v1' or
            barrier.get('shutdown_proven') is not True or barrier.get('errors') != [] or
            barrier.get('attempt_id') != state.get('id') or
            barrier.get('daemon_epoch') != manifest['epoch'] or
            barrier.get('daemon_manifest_sha256') != owned_daemon.fingerprint(manifest)):
            return False
    return True


def execute(configuration, unit, *, cleanup_only=False):
    from research.cpu_measurement import native_driver
    if set(configuration) != {'schema', 'driver_template', 'activation_root', 'job', 'job_config', 'staging_socket'} or configuration['schema'] != 'mldsafail.operator-activation.v1':
        raise ValueError('Exact private activation configuration required')
    if configuration['job'] not in {'fixture', 'daily-recovery', 'recovery-check'}:
        raise ValueError('Fixed reviewed operator job required')
    if configuration['job'] == 'fixture':
        if configuration['job_config'] is not None or configuration['staging_socket'] is not None:
            raise ValueError('Isolated fixture has no staging configuration')
    elif configuration['staging_socket'] != '/run/user/'+str(os.getuid())+'/docker.sock':
        raise ValueError('Established same-user staging socket required')
    repository = Path(__file__).resolve().parents[1]
    template = owned_daemon.read_private_json(configuration['driver_template'])
    with activation_lock(configuration['activation_root']) as root:
        config = current_configuration(template, root, unit)
        # Only exact direct child driver journals are owned; unknown directories
        # are a fence rather than a reason to skip prior interruption recovery.
        reconciliation_errors = []
        first_error = None
        for prior in sorted(root.glob('activation-*')):
            try:
                if prior.is_symlink() or not prior.is_dir() or not re.fullmatch('activation-[a-f0-9]{32}', prior.name):
                    raise RuntimeError('Unknown prior activation ownership')
                state = owned_daemon.read_private_json(prior/'driver.json', cap=4*1024*1024)
                if not prior_complete(state, prior):
                    result = native_driver.cleanup_state(prior/'driver.json', controller_config=config, repository=repository)
                    if result.get('cleanup_complete') is not True:
                        raise RuntimeError('Earlier activation remains fenced')
            except BaseException as error:
                if first_error is None:
                    first_error = error
                reconciliation_errors.append(dict(state_path=str(prior/'driver.json'), error_class=type(error).__name__))
        if first_error is not None:
            try:
                owned_daemon.publish(root/('reconciliation-'+uuid.uuid4().hex+'.json'),
                    dict(cleanup_complete=False, errors=reconciliation_errors))
            except BaseException as publication:
                first_error.add_note('Reconciliation evidence publication failed: '+type(publication).__name__)
            raise first_error
        if cleanup_only:
            return dict(cleanup_complete=True, activated=False)
        def acceptance(journal, config, data):
            if configuration['job'] == 'fixture':
                return fixture(journal, config, data)
            from deploy.recovery_daemon import shared_scope
            private = owned_daemon.read_private_json(configuration['job_config'])
            environment = dict(DOCKER_HOST='unix://'+configuration['staging_socket'],
                               DOCKER_CONTEXT=None, MLDSAFAIL_OPERATOR_DAEMON_MANIFEST=None,
                               MLDSAFAIL_CPU_DAEMON_MANIFEST=None)
            with shared_scope(environment):
                if configuration['job'] == 'daily-recovery':
                    from deploy import daily_recovery
                    private = dict(private, backup=dict(private['backup'], owned_daemon_manifest=data['manifest_path']))
                    result = daily_recovery.run(private)
                    if result.get('daily_recovery_verified') is not True:
                        raise RuntimeError('Complete daily recovery acceptance required')
                else:
                    from deploy.recovery import execute as check
                    from deploy.recovery_journal import standalone_operation
                    private = dict(private, owned_daemon_manifest=data['manifest_path'])
                    result = standalone_operation(private, Path(private['backup_state']).parent, 'restic',
                        lambda operation: check(private, 'check', journal=operation))
                    if result.get('completed') is not True:
                        raise RuntimeError('Complete recovery repository check required')
            receipt = journal.path.parent/'operator-job.json'
            owned_daemon.publish(receipt, dict(passed=True, job=configuration['job'], result=result,
                                 source_sha256=config['acceptance_source_sha256']))
            return dict(schema='mldsafail.owned-native-acceptance.v1', passed=True, native_executed=True,
                        evidence_refs=[str(receipt)], source_sha256=config['acceptance_source_sha256'])
        result = native_driver.execute(config, repository, acceptance=acceptance, daemon_kind='owned')
        owned_daemon.publish(Path(config['state_root'])/'activation.json', dict(
            schema='mldsafail.operator-activation-receipt.v1', passed=True,
            source_sha256=config['acceptance_source_sha256'], job=configuration['job'],
            source_commit=config['source_commit'], operator_unit=unit,
            operator_domain=result['provisioning']['operator_domain'],
            daemon_epoch=result['registered_manifest']['epoch'],
            worker_domain=result['registered_manifest']['worker_domain'],
            driver_state=str(Path(config['state_root'])/'driver.json'),
            cleanup_complete=result['cleanup']['cleanup_complete'],
            native_cpu_gates_passed=False))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--unit', required=True)
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    try:
        execute(owned_daemon.read_private_json(args.config), args.unit, cleanup_only=args.cleanup)
        print(json.dumps({'operator_activation_completed': True}))
    except ActivationContended:
        print(json.dumps({'ownership_rejected': 'activation_lock_contended'}))
        raise SystemExit(73)
    except BaseException as error:
        print(json.dumps({'operator_activation_completed': False, 'error_class': type(error).__name__}))
        raise


if __name__ == '__main__':
    main()
