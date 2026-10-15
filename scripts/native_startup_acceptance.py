"""Private native startup proof, before image admission.

Run only through native_operator_unit with a source-bound private driver config
and independent review. Each case owns fresh real systemd/cgroup/socket resources.
Fault injection changes publication only; authority checks use the native kernel.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import socket
import signal
import sys
import time
import uuid

# A real failed service leaves a refused socket, without importing the evaluator.
if __name__ == '__main__' and len(sys.argv) == 3 and sys.argv[1] == '--leave-socket':
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as endpoint:
        endpoint.bind(sys.argv[2])
    raise SystemExit(1)
if __name__ == '__main__' and len(sys.argv) == 3 and sys.argv[1] == '--wait-marker':
    deadline = time.monotonic() + 60
    while not Path(sys.argv[2]).exists():
        if time.monotonic() > deadline:
            raise SystemExit(1)
        time.sleep(.05)
    raise SystemExit(0)

from deploy import owned_client, owned_daemon
from deploy.recovery_daemon import provision_lock
from research.cpu_measurement import native_driver


CASES = ('refused', 'live', 'replacement', 'worker', 'fragment', 'admitted',
         'pending_job', 'intent_failure', 'after_unlink_failure', 'interrupted_cleanup')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def execute(config, repository, output):
    repository = repository.resolve()
    digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    review = owned_daemon.read_private_json(config['review_packet'])
    require(review.get('startup_source_sha256') == digest,
            'Independent startup harness review required')
    native_driver.validate(config, repository)
    output = owned_daemon._canonical(output)
    owned_daemon._private_directory(output.parent)
    output.mkdir(mode=0o700)
    report = dict(schema='mldsafail.native-startup-acceptance.v1', passed=False,
                  source_commit=config['source_commit'], source_sha256=digest,
                  native_executed=True, cases=[], cleanup_complete=False)
    owned_daemon.publish(output / 'report.json', report)
    # Longest internal suffix and encoded-byte rejection must precede mkdir.
    internal_only = 'x' * (104 - len(os.fsencode(output)) - 1 - len('/docker.sock'))
    require(len(internal_only) > 0, 'Short native acceptance output root required')
    for name in ('x' * 100, internal_only, 'é' * 45):
        target = output / name
        try:
            owned_daemon.provision(target, unit='mldsafail-owned-daemon-preflight.service',
                                   protected_roots=config['protected_roots'])
        except RuntimeError as error:
            require('endpoint exceeds' in str(error), 'Endpoint fault not reached')
        else:
            raise RuntimeError('Overlong endpoint admitted')
        require(not target.exists(), 'Preflight created resources')
    report['endpoint_rejection_verified'] = True
    for index, case in enumerate(CASES):
        root = output / ('c' + str(index))
        root.mkdir(mode=0o700)
        identifier = uuid.uuid4().hex
        unit = 'mldsafail-owned-daemon-' + identifier + '.service'
        state = dict(schema='mldsafail.cpu-native-driver-state.v1', id=identifier,
                     state='provisioning', config=config, units=[], commands=[], clients=[],
                     daemon_unit=unit, socket=str(root / 'daemon/docker.sock'),
                     manifest_path=str(root / 'manifest.json'))
        journal = native_driver.Journal(root / 'driver.json', state)
        journal.save()
        provision = owned_daemon.provision(root / 'daemon', unit=unit,
                                          protected_roots=config['protected_roots'])
        state['provisioning'] = provision
        journal.save()
        with provision_lock(provision):
            row = dict(case=case, passed=False, cleanup_complete=False)
            report['cases'].append(row)
            endpoint = None
            worker_client = None
            original_fragment = None
            gate = None
            publish = owned_daemon.publish
            try:
                worker = 'mldsafail-owned-workers-' + provision['id'] + '.slice'
                units = Path.home() / '.config/systemd/user'
                state['worker_slice'] = worker
                state['units'].append(native_driver.install(units / worker,
                                      '[Slice]\nCPUAccounting=yes\nMemoryAccounting=yes\n'))
                journal.save()
                journal.command(['systemctl', '--user', 'daemon-reload'], kind='unit_reload')
                state['worker_start_intent'] = True
                journal.save()
                journal.command(['systemctl', '--user', 'start', worker], kind='worker_start')
                control = journal.command(['systemctl', '--user', 'show', worker,
                                           '--property=ControlGroup', '--value']).stdout.decode().strip()
                parent = Path('/sys/fs/cgroup') / control.lstrip('/')
                require(parent.name == worker, 'Fresh worker slice has unexpected kernel path')
                owned_daemon._disjoint([parent, Path(config['operator_parent'])],
                                       [Path(path) for path in config['protected_cgroups']])
                secured = dict(id='startup-' + identifier)
                owned_client.secure_created_domain(secured, parent)
                state['worker_parent'] = str(parent)
                state['provisioning'] = owned_daemon.bind_worker(
                    provision, worker_parent=parent, worker_cgroup_parent=worker,
                    operator_parent=config['operator_parent'],
                    protected_domains=config['protected_cgroups'])
                journal.save()
                # Real service failure, real refused Unix socket; no worker image.
                fragment = ('[Service]\nType=oneshot\nRestart=no\nKillMode=control-group\nDelegate=yes\n'
                            'ExecStart=' + sys.executable + ' ' + str(Path(__file__).resolve())
                            + ' --leave-socket ' + state['socket'] + '\n')
                if case == 'pending_job':
                    gate = 'mldsafail-startup-gate-' + identifier + '.service'
                    marker = root / 'gate-marker'
                    marker.touch(mode=0o600)
                    gate_fragment = ('[Service]\nType=oneshot\nExecStart=' + sys.executable + ' '
                                     + str(Path(__file__).resolve()) + ' --wait-marker ' + str(marker) + '\n')
                    state['units'].append(native_driver.install(units / gate, gate_fragment))
                    fragment = '[Unit]\nRequires=' + gate + '\nAfter=' + gate + '\n' + fragment
                original_fragment = fragment
                state['units'].append(native_driver.install(units / unit, fragment))
                journal.save()
                journal.command(['systemctl', '--user', 'daemon-reload'], kind='unit_reload')
                state['start_intent'] = True
                journal.save()
                # --no-block acknowledges enqueueing; inspect actual completion.
                journal.command(['systemctl', '--user', 'start', '--no-block', unit], kind='daemon_start')
                deadline = time.monotonic() + 15
                while (not Path(state['socket']).exists()
                       or owned_daemon._unit(unit)['ActiveState'] not in {'failed', 'inactive'}):
                    require(time.monotonic() < deadline, 'Failed service did not terminate')
                    time.sleep(.05)
                require(Path(state['socket']).exists(), 'Failed service socket fault not reached')
                owned_daemon._failed_startup_authority(state)  # Establish the common native preconditions before fault injection.
                identity = owned_daemon._socket_identity(Path(state['socket']))
                row['socket_identity'] = identity
                if case == 'live':
                    Path(state['socket']).unlink()
                    endpoint = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    endpoint.bind(state['socket'])
                    endpoint.listen(4)
                    identity = owned_daemon._socket_identity(Path(state['socket']))
                elif case == 'worker':
                    worker_client = root / 'worker-cancelled.txt'
                    # A real transient service is admitted to the exact worker slice.
                    helper = 'mldsafail-startup-populated-' + identifier + '.service'
                    row['worker_helper'] = helper
                    journal.command(['systemd-run', '--user', '--unit=' + helper,
                                     '--slice=' + worker, '/usr/bin/sleep', '60'], kind='worker_fixture')
                    deadline = time.monotonic() + 10
                    while not owned_client.populated(parent):
                        require(time.monotonic() < deadline, 'Worker fault not reached')
                        time.sleep(.05)
                elif case == 'fragment':
                    (units / unit).write_text(fragment + '# changed fixture\n')
                elif case == 'admitted':
                    state['image_load_intent'] = True
                elif case == 'pending_job':
                    marker.unlink()
                    journal.command(['systemctl', '--user', 'start', '--no-block', unit], kind='daemon_start')
                    deadline = time.monotonic() + 10
                    while True:
                        raw_jobs = journal.command(owned_daemon.JOB_QUERY).stdout
                        jobs = owned_daemon._parse_jobs(raw_jobs)
                        if any(job.get('unit') == unit for job in jobs):
                            owned_daemon.publish(root / 'pending-jobs.json', dict(jobs=jobs))
                            break
                        require(time.monotonic() < deadline, 'Pending daemon job fault not reached')
                        time.sleep(.05)
                    current = owned_daemon._unit(unit)
                    require(current['ActiveState'] in {'inactive', 'failed'} and int(current['MainPID']) == 0,
                            'Pending-job fixture failed before target fence')
                if case in {'replacement', 'intent_failure', 'after_unlink_failure'}:
                    def inject(path, value):
                        nonlocal endpoint, identity
                        if 'socket-retirement-intent' in Path(path).name:
                            if case == 'intent_failure':
                                raise OSError('Injected intent publication failure')
                            publish(path, value)
                            if case == 'replacement':
                                # Keep old inode open to prevent immediate reuse.
                                old = os.open(state['socket'], os.O_PATH) if hasattr(os, 'O_PATH') else None
                                try:
                                    Path(state['socket']).unlink()
                                    endpoint = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                                    endpoint.bind(state['socket'])
                                    identity = owned_daemon._socket_identity(Path(state['socket']))
                                finally:
                                    if old is not None:
                                        os.close(old)
                            return
                        if case == 'after_unlink_failure' and 'failed-startup-' in Path(path).name:
                            row['post_unlink_publication_injection_reached'] = True
                            raise OSError('Injected post-unlink receipt publication failure')
                        return publish(path, value)
                    owned_daemon.publish = inject
                publish(root / 'fault-state.json', state)
                if case == 'fragment':
                    publish(root / 'changed-fragment.json', dict(text=(units / unit).read_text()))
                if case == 'interrupted_cleanup':
                    reader, writer = os.pipe()
                    child = os.fork()
                    if child == 0:
                        os.close(reader)
                        def pause_after_intent(path, value):
                            publish(path, value)
                            if 'socket-retirement-intent' in Path(path).name:
                                os.write(writer, b'1')
                                time.sleep(30)
                        owned_daemon.publish = pause_after_intent
                        try:
                            owned_daemon.failed_startup_barrier(state, evidence_directory=root, attempt_id=identifier)
                        finally:
                            os._exit(2)
                    os.close(writer)
                    birth = owned_client.identity(child)
                    try:
                        import select
                        ready, _, _ = select.select([reader], [], [], 10)
                        require(ready and os.read(reader, 1) == b'1', 'Interruption fault not reached')
                        require(owned_client.identity(child) == birth, 'Cleanup child birth changed')
                        os.kill(child, signal.SIGKILL)
                    finally:
                        os.close(reader)
                        # Child is this process's unreaped direct child: PID cannot be reused.
                        try:
                            os.kill(child, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        _, status = os.waitpid(child, 0)
                    require(os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL,
                            'Cleanup interruption was not observed')
                    row['interrupted_child'] = birth
                    row['expected_fault_reached'] = True
                    require(owned_daemon._socket_identity(Path(state['socket'])) == identity,
                            'Interrupted cleanup changed socket')
                try:
                    if case == 'interrupted_cleanup':
                        # Retry independently below, retaining the interrupted intent.
                        proof = dict(startup_shutdown_proven=False, interrupted=True)
                    else:
                        proof = owned_daemon.failed_startup_barrier(state, evidence_directory=root,
                                                                   attempt_id=identifier)
                    row['proof'] = proof
                    expected_errors = {
                        'live': 'still accepts connections',
                        'replacement': 'Socket birth changed',
                        'worker': 'worker parent is not empty',
                        'fragment': 'fragment identity changed',
                        'admitted': 'Never-admitted startup proof',
                        'pending_job': 'jobs remain pending',
                        'intent_failure': 'Injected intent publication failure',
                    }
                    if case in expected_errors:
                        require(any(expected_errors[case] in error.get('error', '')
                                    for error in proof.get('errors', [])),
                                'Expected startup fault gate was not reached: ' + case)
                    require(proof['startup_shutdown_proven'] == (case == 'refused'),
                            'Unexpected startup proof disposition')
                except OSError:
                    require(case == 'after_unlink_failure', 'Unexpected publication failure')
                    require(row.get('post_unlink_publication_injection_reached'),
                            'Post-unlink publication injection was not reached')
                    require(not Path(state['socket']).exists(), 'Post-unlink failure did not reach unlink')
                    row['publication_failure_reached'] = True
                finally:
                    owned_daemon.publish = publish
                if case not in {'refused', 'after_unlink_failure'}:
                    require(owned_daemon._socket_identity(Path(state['socket'])) == identity,
                            'Fenced socket changed')
                    row['fenced_socket_identity'] = identity
                row['expected_fault_reached'] = True
                row['passed'] = True
            finally:
                owned_daemon.publish = publish
                cleanup_errors = []
                def cleanup_step(label, action):
                    try:
                        action()
                    except BaseException as error:
                        cleanup_errors.append(dict(step=label, error=repr(error)))
                if endpoint is not None:
                    cleanup_step('fixture_endpoint_close', endpoint.close)
                if gate is not None:
                    # Cancel exact retained fixture jobs before releasing the dependency.
                    cleanup_step('pending_daemon_stop', lambda: journal.command(
                        ['systemctl', '--user', 'stop', unit], kind='service_stop'))
                    cleanup_step('pending_gate_stop', lambda: journal.command(
                        ['systemctl', '--user', 'stop', gate], kind='fixture_stop'))
                if worker_client is not None:
                    cleanup_step('worker_helper_stop', lambda: journal.command(
                        ['systemctl', '--user', 'stop', row['worker_helper']], kind='worker_fixture_stop'))
                if original_fragment is not None and case == 'fragment':
                    cleanup_step('fixture_fragment_restore', lambda: (units / unit).write_text(original_fragment))
                if case == 'admitted':
                    # Synthetic admission fence only; no Docker request was made.
                    state.pop('image_load_intent', None)
                cleanup_step('fixture_journal_save', journal.save)
                cleanup = None
                def retire_case():
                    nonlocal cleanup
                    cleanup = native_driver.cleanup(journal, terminal=True)
                cleanup_step('independent_case_cleanup', retire_case)
                row['cleanup_errors'] = cleanup_errors
                row['cleanup_complete'] = bool(cleanup and cleanup['cleanup_complete']) and not cleanup_errors
                owned_daemon.publish(output / 'report.json', report)
                require(row['cleanup_complete'], 'Case cleanup fenced; stop suite')
    report['cleanup_complete'] = all(row['cleanup_complete'] for row in report['cases'])
    report['passed'] = len(report['cases']) == len(CASES) and all(row['passed'] for row in report['cases']) and report['cleanup_complete']
    owned_daemon.publish(output / 'report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    execute(owned_daemon.read_private_json(args.config), Path(__file__).resolve().parents[1], args.output)
