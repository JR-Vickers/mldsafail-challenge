"""Explicit native interrupted-generation cleanup; never creates a score.

Every cleanup step is retried independently. Original interruption evidence stays
immutable; incomplete reconciliation keeps ownership fenced. Use only the exact
private directory/accounting parent previously owned by this supervisor.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
import signal
import select
from research.cpu_measurement.ownership import publish, canonical_directory
from research.cpu_measurement.harness import fields, prove_membership, worker_cgroup, prove_exclusive, process_start_ticks


def reconcile(directory, parent):
    directory, parent = Path(directory), Path(parent)
    if any(path.is_symlink() for target in (directory.absolute(), parent.absolute()) for path in (target, *target.parents)):
        raise RuntimeError('Reconciliation paths must not contain symlinks')
    parent_descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    descriptor = os.open(directory / 'lock', os.O_RDWR | os.O_NOFOLLOW)
    try:
        fcntl.flock(parent_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        journal = json.loads((directory / 'journal.json').read_text())
        if journal['state'] == 'complete':
            return {'cleanup_complete': True, 'already_complete': True}
        identity = os.fstat(parent_descriptor)
        if (identity.st_dev, identity.st_ino) != (journal['parent_device'], journal['parent_inode']):
            raise RuntimeError('Accounting parent identity changed; cannot reconcile')
        original = directory / (journal['generation'] + '-interrupted.json')
        if not original.exists():
            publish(original, journal)
        intentions = {entry['name']: entry for entry in journal['mutations']
                      if entry['operation'] == 'container_create_intent'}
        names = set(intentions)
        authorized_domains = []
        errors = []
        for name in names:
            if not name.startswith('cpu-proposal-') or len(name) != len('cpu-proposal-') + 32:
                raise RuntimeError('Malformed owned container identity')
            # Inspect absent containers as already removed; never blindly treat
            # daemon unavailability or permissions as proof of absence.
            try:
                listing = subprocess.check_output(['docker', 'ps', '-a', '--format', '{{.Names}}'], timeout=30).decode().splitlines()
                if name in listing:
                    inspected = json.loads(subprocess.check_output(['docker', 'inspect', name], timeout=30))[0]
                    expected = intentions[name]
                    if inspected['Config'].get('Labels', {}).get('org.mldsafail.cpu-generation') != journal['generation'] or inspected['Image'] != expected['image'] or inspected['HostConfig']['CgroupParent'] != expected['cgroup_parent']:
                        raise RuntimeError('Owned container generation/image/accounting identity mismatch')
                    pid = inspected['State'].get('Pid', 0)
                    if pid:
                        prove_membership(pid, parent)
                        authorized_domains.append(worker_cgroup(pid))
                    subprocess.run(['docker', 'rm', '-f', name], check=True, capture_output=True, timeout=30)
            except Exception as error:
                errors.append(dict(step='container_remove', error=repr(error)))
        for entry in journal['mutations']:
            if entry['operation'] != 'host_client_spawned':
                continue
            handle = None
            try:
                handle = os.pidfd_open(entry['pid'])
                if process_start_ticks(entry['pid']) != entry['start_ticks']:
                    raise RuntimeError('Host client PID identity mismatch')
                signal.pidfd_send_signal(handle, signal.SIGKILL)
                if not select.select([handle], [], [], 10)[0]:
                    raise RuntimeError("Host client survived termination deadline")
            except ProcessLookupError:
                pass
            except FileNotFoundError:
                pass  # Process exited after acquiring its pidfd.
            except Exception as error:
                errors.append(dict(step='host_client_cleanup', error=repr(error)))
            finally:
                if handle is not None:
                    os.close(handle)
        try:
            if fields(parent / 'cgroup.events')['populated']:
                if len(authorized_domains) != 1:
                    raise RuntimeError('Unexplained domain members; destructive cleanup prohibited')
                prove_exclusive(parent, authorized_domains[0])
                (parent / 'cgroup.kill').write_text('1')
        except Exception as error:
            errors.append(dict(step='domain_kill', error=repr(error)))
        try:
            deadline = time.monotonic() + 10
            while fields(parent / 'cgroup.events')['populated']:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Accounting domain still populated')
                time.sleep(.05)
            counter = fields(parent / 'cpu.stat')['usage_usec']
            before = [entry['counter_before_usec'] for entry in journal['mutations'] if 'counter_before_usec' in entry]
            if before and counter < max(before):
                raise RuntimeError('Accounting counter regressed')
        except Exception as error:
            errors.append(dict(step='domain_proof', error=repr(error)))
        attempt = dict(schema='mldsafail.cpu-cleanup.v1', generation=journal['generation'],
                       cleanup_complete=not errors, errors=errors, original_evidence=original.name)
        import uuid
        name = journal['generation'] + '-cleanup-' + uuid.uuid4().hex + '.json'
        publish(directory / name, attempt)
        if not errors:
            # Completion is a cleanup receipt, never measurement evidence. A
            # measurement audit rejects this generation; subsequent ownership
            # may start only after this fsynced independent domain-empty proof.
            journal.update(state='complete', reconciliation_evidence=name, measurement_aborted=True)
        else:
            journal.update(state='cleanup_incomplete', latest_cleanup_evidence=name)
        publish(directory / 'journal.json', journal)
        return attempt
    finally:
        os.close(descriptor)
        os.close(parent_descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ownership-directory', type=Path, required=True)
    parser.add_argument('--parent', type=Path, required=True)
    args = parser.parse_args()
    if args.ownership_directory.absolute() != canonical_directory(args.parent).absolute():
        raise ValueError('Canonical parent-scoped ownership directory required')
    result = reconcile(args.ownership_directory, args.parent)
    print(json.dumps(result))
    raise SystemExit(0 if result['cleanup_complete'] else 1)


if __name__ == '__main__':
    main()
