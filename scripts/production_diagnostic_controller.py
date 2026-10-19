"""Explicit diagnostic configuration, supervised execution, cleanup-only and report.

Run inside the existing delegated native operator wrapper. The supervisor owns
an engine child, retains host serialization throughout, and uses retained driver
ownership for terminal cleanup. No epoch or full-rehearsal entrypoint is called.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import time
import threading

from deploy import owned_client, owned_daemon
from research.cpu_measurement import native_driver
from scripts import production_diagnostic as diagnostic
from scripts import production_diagnostic_state as budget_state
from scripts.production_diagnostic_deadline import remaining


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def configuration(path):
    packet = owned_daemon.read_private_json(path, cap=4*1024*1024)
    packet['packet_path'] = str(path)
    config = owned_daemon.read_private_json(packet['driver_config'])
    from scripts.native_production_diagnostic import preflight
    preflight(packet, config, Path(__file__).resolve().parents[1])
    native_driver.validate(config, Path(__file__).resolve().parents[1])
    return packet, config


def engine(path):
    packet = owned_daemon.read_private_json(path, cap=4*1024*1024)
    start = owned_daemon.read_private_json(Path(packet['budget_root'])/(packet['protocol']['generation']+'-start.json'))
    if start['boot_id'] != boot_id():
        raise ValueError('Generation boot identity changed')
    # Only the already registered gated child may enter this internal operation.
    # Replaying --engine in a new process cannot reuse an interrupted slot.
    config = owned_daemon.read_private_json(packet['driver_config'])
    if diagnostic.file_digest(packet['driver_config']) != packet['driver_configuration_sha256']:
        raise ValueError('Actual driver configuration changed before engine entry')
    root = Path(config['state_root']).parent
    authority = owned_daemon.read_private_json(root/'supervisor-clients.json')
    actual = owned_client.identity(os.getpid())
    entries = [entry for entry in authority['clients'] if entry.get('pid') == os.getpid()
        and entry.get('start_ticks') == actual['start_ticks'] and entry.get('boot_id') == actual['boot_id']]
    if len(entries) != 1 or entries[0].get('expected_cmdline_sha256') != actual['cmdline_sha256']:
        raise ValueError('Engine requires retained same-birth supervisor authority')
    if owned_client.verify_domain(entries[0]) != current_domain():
        raise ValueError('Engine is outside its retained execution domain')
    native_driver.install(root/'engine-entered.json', json.dumps(dict(start_sha256=diagnostic.digest(start))))
    started = start['monotonic_started']
    from scripts.production_diagnostic_deadline import interrupt_at
    with interrupt_at(started+packet['protocol']['phases'][0]['outer_seconds']):
        packet, config = configuration(path)
    from scripts.native_production_diagnostic import callback
    # The callback clears this setup alarm only after imports, database startup,
    # fixture restoration and monitor installation have completed within it.
    with interrupt_at(started+packet['protocol']['phases'][0]['outer_seconds']):
        native_driver.execute(config, Path(__file__).resolve().parents[1], acceptance=callback,
            daemon_kind='owned', diagnostic_deadlines=(started+2100, started+3000),
            diagnostic_setup_deadline=started+packet['protocol']['phases'][0]['outer_seconds'])



def current_domain():
    return Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')


def quiesce_engine(config, root, entry, deadline):
    """Freeze all owned dispatchers before snapshot; barrier before cancellation.

    A failed freeze or ownership proof leaves recorded domains frozen and fenced.
    No fallback may kill them or claim terminal cleanup completed.
    """
    from scripts.production_diagnostic_deadline import interrupt_at
    root = Path(root)
    with interrupt_at(deadline):
        entries = [entry]
        state_path = Path(config['state_root'])/'driver.json'
        # Freeze the top-level controller first. Every subordinate process has a
        # durable gated registry before it can run or create further clients.
        frozen = set()
        current = current_domain()
        def freeze(item):
            if 'cgroup' not in item:
                if item.get('pid') is not None or 'cgroup_intent' not in item:
                    raise ValueError('Malformed interrupted client authority')
                return  # Still gated: no process could be released before acknowledgement.
            path = owned_client.verify_domain(item)
            if path is None or path in frozen or current.is_relative_to(path):
                return
            (path/'cgroup.freeze').write_text('1')
            while dict(line.split() for line in (path/'cgroup.events').read_text().splitlines()).get('frozen') != '1':
                remaining(deadline,1)
                time.sleep(.01)
            frozen.add(path)
        freeze(entry)
        # Freezing each recorded dispatcher makes its next registry snapshot
        # stable. Repeat until no newly discovered domain can dispatch work.
        while True:
            old = len(frozen)
            if state_path.exists():
                data = owned_daemon.read_private_json(state_path, cap=4*1024*1024)
                entries.extend(data.get('clients',[]))
            for registry in Path(config['state_root']).rglob('clients.json') if Path(config['state_root']).exists() else []:
                value = json.loads(registry.read_text())
                entries.extend(value.get('clients',[]) if isinstance(value,dict) else value)
            for item in entries:
                freeze(item)
            if len(frozen)==old:
                break
        if state_path.exists():
            data = owned_daemon.read_private_json(state_path, cap=4*1024*1024)
            if data.get('start_intent'):
                if Path(data['manifest_path']).exists():
                    manifest = owned_daemon.load_manifest(data['manifest_path'])
                    barrier = owned_daemon.shutdown_barrier(manifest, evidence_directory=root, attempt_id='diagnostic-supervisor')
                    if barrier.get('shutdown_proven') is not True:
                        raise RuntimeError('Supervisor daemon barrier failed')
                else:
                    barrier = owned_daemon.failed_startup_barrier(data, evidence_directory=root, attempt_id='diagnostic-supervisor')
                    if barrier.get('startup_shutdown_proven') is not True:
                        raise RuntimeError('Supervisor startup barrier failed')
        for item in entries:
            # The caller's current controller remains active to finish cleanup.
            if 'cgroup' not in item:
                owned_client.stop(item)
                continue
            path = owned_client.verify_domain(item)
            if path is not None and not current.is_relative_to(path):
                owned_client.stop(item)


def execute(path, *, preflight_only=False):
    packet = owned_daemon.read_private_json(path, cap=4*1024*1024)
    config = owned_daemon.read_private_json(packet['driver_config'])
    # This is the existing host-wide evaluation/maintenance/build serialization
    # lock, supplied explicitly by the independently reviewed private packet.
    lock = owned_daemon._canonical(packet['host_operation_lock'])
    fd = os.open(lock, os.O_RDWR | os.O_NOFOLLOW)
    try:
        import stat
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise ValueError('Existing private host operation lock required')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with budget_state.locked(packet['budget_root']) as budget:
            slot = 'preflight' if preflight_only else packet['protocol']['generation']
            allowance = budget.start(slot, boot_id=boot_id())
            from scripts.production_diagnostic_preflight import inspect
            from scripts.production_diagnostic_deadline import interrupt_at
            with interrupt_at(allowance.started+allowance.seconds-allowance.cleanup):
                configuration(path)
                inspect(packet, Path(config['state_root']).parent, allowance.started+allowance.seconds-allowance.cleanup)
            if preflight_only:
                return dict(preflight_complete=True, independent_verification_pending=True)
            # Start is durable before the engine can provision or import images.
            root = Path(config['state_root']).parent
            clients = []
            def save():
                owned_daemon.publish(root/'supervisor-clients.json', dict(clients=clients))
            save()
            error = None
            os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST'] = str(Path(config['state_root'])/'daemon-manifest.json')
            os.environ['DOCKER_HOST'] = 'unix://'+str(Path(config['state_root'])/'daemon/docker.sock')
            try:
                # The independent parent terminates the engine by second 2,100,
                # leaving the entire reserved 900 seconds for terminal cleanup.
                owned_client.run([sys.executable,'-B','-m','scripts.production_diagnostic_controller','--engine',str(path)],
                    clients, save, root, timeout=remaining(allowance.started+2100, 2100),
                    absolute_deadline=allowance.started+2100,
                    before_cancel=lambda entry: quiesce_engine(config,root,entry,allowance.started+3000),
                    stdout=open(root/'engine.stdout','xb'), stderr=open(root/'engine.stderr','xb'))
            except BaseException as caught:
                error = caught
            finally:
                state = Path(config['state_root'])/'driver.json'
                if state.exists():
                    from scripts.native_production_diagnostic import terminal_cleanup
                    from scripts.production_diagnostic_deadline import interrupt_at
                    with interrupt_at(allowance.started+3000):
                        cleanup = terminal_cleanup(state, config, Path(__file__).resolve().parents[1])
                else:
                    cleanup = dict(cleanup_complete=not Path(config['state_root']).exists())
                owned_daemon.publish(root/'supervisor-cleanup.json', cleanup)
                if not cleanup['cleanup_complete']:
                    raise RuntimeError('Terminal cleanup remains fenced') from error
            if error is not None:
                raise error
            # Independent actual postflight must produce the start-bound receipt;
            # execution never self-certifies it or advances the next generation.
            return dict(measurements_complete=True, independent_postflight_pending=True)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--configuration', type=Path)
    group.add_argument('--execute', type=Path)
    group.add_argument('--preflight', type=Path)
    group.add_argument('--engine', type=Path, help=argparse.SUPPRESS)
    group.add_argument('--cleanup-state', type=Path)
    group.add_argument('--report', type=Path)
    parser.add_argument('--controller-config', type=Path)
    args = parser.parse_args()
    if args.configuration:
        configuration(args.configuration)
    elif args.execute:
        execute(args.execute)
    elif args.preflight:
        execute(args.preflight, preflight_only=True)
    elif args.engine:
        engine(args.engine)
    elif args.cleanup_state:
        if args.controller_config is None:
            parser.error('Retained cleanup requires explicit reviewed controller config')
        from scripts.native_production_diagnostic import terminal_cleanup
        receipt = terminal_cleanup(args.cleanup_state,
            owned_daemon.read_private_json(args.controller_config), Path(__file__).resolve().parents[1])
        raise SystemExit(0 if receipt['cleanup_complete'] else 1)
    else:
        # Reports are private and read-only. Never load a callback or provision.
        print(json.dumps(owned_daemon.read_private_json(args.report, cap=4*1024*1024), sort_keys=True))


if __name__ == '__main__':
    main()
