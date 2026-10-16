"""Retire only terminal, archive-backed owned build caches; retain all evidence.

Run through the delegated operator wrapper. A bounded rootlesskit child uses the
original subordinate mappings to traverse mapped image layers, never a Docker API.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

from deploy import owned_client, owned_daemon
from deploy.recovery_daemon import provision_lock


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def root_identity(path):
    info = Path(path).lstat()
    if not stat.S_ISDIR(info.st_mode) or Path(path).is_symlink():
        raise ValueError('Real cache directory required')
    return dict(device=info.st_dev, inode=info.st_ino, uid=info.st_uid)


def reject_mounts(root, lines):
    for line in lines:
        fields = line.split()
        if len(fields) < 10 or '-' not in fields:
            raise ValueError('Malformed mount inspection')
        mount = Path(re.sub(r'\\([0-7]{3})', lambda value: chr(int(value[1], 8)), fields[4]))
        if mount == root or root in mount.parents:
            raise ValueError('Mounted cache cannot be retired')


def mount_inspection(root):
    inspected, inaccessible = 0, 0
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal():
            continue
        try:
            reject_mounts(root, (process / 'mountinfo').read_text().splitlines())
            inspected += 1
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            inaccessible += 1
    if not inspected:
        raise RuntimeError('No accessible mount namespaces inspected')
    return dict(process_mount_tables=inspected, inaccessible_process_mount_tables=inaccessible)


def inspect_tree(root, expected):
    """Classify every node without following links or opening special entries."""
    root = owned_daemon._canonical(root)
    if root_identity(root) != expected:
        raise ValueError('Exact cache directory identity required')
    count, special = 0, []
    def walk_error(error):
        raise error
    for directory, directories, files in os.walk(root, followlinks=False, onerror=walk_error):
        for name in [*directories, *files]:
            path = Path(directory) / name
            info = path.lstat()
            if info.st_dev != expected['device']:
                raise ValueError('Unexpected cache filesystem')
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)):
                special.append(dict(path=str(path.relative_to(root)), device=info.st_dev,
                                    inode=info.st_ino, mode=info.st_mode, rdev=info.st_rdev))
            count += 1
    if root_identity(root) != expected:
        raise ValueError('Cache directory changed during inspection')
    return dict(entries=count, special_entries=sorted(special, key=lambda value: value['path']))


def delete_tree(root, expected, *, special_entries=()):
    """Remove only an exactly inspected tree, unlinking approved nodes unopened."""
    root = owned_daemon._canonical(root)
    if not shutil.rmtree.avoids_symlink_attacks:
        raise ValueError('Descriptor-safe removal required')
    names = set()
    for item in special_entries:
        if not isinstance(item, dict) or set(item) != {'path', 'device', 'inode', 'mode', 'rdev'}:
            raise ValueError('Exact special-node declaration required')
        path = Path(item['path'])
        if (path.is_absolute() or '..' in path.parts or str(path) != item['path'] or str(path) == '.'
                or item['path'] in names or any(type(item[key]) is not int for key in ('device', 'inode', 'mode', 'rdev'))):
            raise ValueError('Unique relative special-node identities required')
        names.add(item['path'])
    inventory = inspect_tree(root, expected)
    if inventory['special_entries'] != sorted(special_entries, key=lambda value: value['path']):
        raise ValueError('Unexpected or changed special cache entry; separate review required')
    descriptor = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if root_identity(root) != expected:
            raise ValueError('Cache directory changed before retirement')
        if inspect_tree(root, expected)['special_entries'] != inventory['special_entries']:
            raise ValueError('Special cache entries changed immediately before removal')
        shutil.rmtree(root.name, dir_fd=descriptor)
    finally:
        os.close(descriptor)
    if root.exists() or root.is_symlink():
        raise RuntimeError('Cache retirement incomplete')
    return inventory['entries']


def terminal_proof(driver, operator):
    if (driver.get('native_acceptance_passed') is not True
            or driver.get('cleanup', {}).get('cleanup_complete') is not True
            or operator.get('cleanup_complete') is not True or operator.get('complete') is not True):
        raise ValueError('Positive completed build/operator cleanup required')
    domains, processes = set(), []
    def collect(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and value['path'].startswith('/sys/fs/cgroup/'):
                domains.add(value['path'])
            if type(value.get('pid')) is int and type(value.get('start_ticks')) is int:
                processes.append(value)
            for child in value.values(): collect(child)
        elif isinstance(value, list):
            for child in value: collect(child)
    collect(driver); collect(operator)
    if any(Path(path).exists() for path in domains):
        raise ValueError('Owned build domain survives')
    for entry in processes:
        try:
            current = owned_client.identity(entry['pid'])
        except (FileNotFoundError, ProcessLookupError):
            continue
        if current['boot_id'] == entry['boot_id'] and current['start_ticks'] == entry['start_ticks']:
            raise ValueError('Owned build process survives')
    socket = Path(driver['socket'])
    if socket.exists() or socket.is_symlink():
        raise ValueError('Owned daemon socket survives')
    for unit in (driver['daemon_unit'], driver['worker_slice'], operator['unit']):
        state = subprocess.check_output(['systemctl', '--user', 'show', unit,
                                         '--property=ActiveState', '--value'], text=True, timeout=15).strip()
        if state not in {'inactive', 'failed'}:
            raise ValueError('Owned build unit remains active')
    return dict(domains=len(domains), process_births=len(processes), socket_absent=True)


def child(intent_path):
    intent = owned_daemon.read_private_json(intent_path)
    mapping = f'0 {intent["owner_uid"]} 1\n1 100000 65536'
    for name in ('uid_map', 'gid_map'):
        actual = '\n'.join(' '.join(line.split()) for line in Path('/proc/self', name).read_text().splitlines())
        if actual != mapping:
            raise ValueError('Original exact rootless UID/GID mapping required')
    if os.getuid() != 0 or os.readlink('/proc/self/ns/user') == intent['parent_user_namespace']:
        raise ValueError('Separate mapped cache retirement namespace required')
    root = Path(intent['root'])
    mounts = mount_inspection(root)
    identity = dict(intent['root_identity'], uid=0)
    action = intent.get('action', 'retire')
    if action not in {'inspect', 'retire'}:
        raise ValueError('Exact cache operation required')
    inventory = inspect_tree(root, identity)
    count = (delete_tree(root, identity, special_entries=intent.get('special_entries', []))
             if action == 'retire' else 0)
    owned_daemon.publish(Path(intent_path).with_suffix('.complete.json'),
                         dict(complete=True, action=action, inventory=inventory, removed_entries=count, mount_inspection=mounts,
                              intent_sha256=digest(intent_path)))


def retire(protocol_path):
    protocol = owned_daemon.read_private_json(protocol_path)
    if protocol.get('schema') != 'mldsafail.build-cache-retirement.v1' or not protocol.get('builds'):
        raise ValueError('Explicit reviewed cache retirement protocol required')
    review = owned_daemon.read_private_json(protocol['review_packet'])
    if (review.get('schema') != 'mldsafail.build-cache-retirement-review.v1'
            or review.get('cache_retirement_review_passed') is not True
            or review.get('protocol_sha256') != digest(protocol_path)
            or review.get('source_commit') != protocol['source_commit']
            or review.get('helper_sha256') != protocol['helper_sha256']):
        raise ValueError('Exact independent cache retirement review required')
    repository = Path(__file__).resolve().parents[1]
    if subprocess.check_output(['git', '-C', str(repository), 'status', '--porcelain'], timeout=15):
        raise ValueError('Clean frozen retirement source required')
    if subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], text=True, timeout=15).strip() != protocol['source_commit']:
        raise ValueError('Retirement source differs from reviewed protocol')
    rootlesskit = owned_daemon._canonical(protocol['rootlesskit'])
    if digest(rootlesskit) != protocol['rootlesskit_sha256'] or digest(__file__) != protocol['helper_sha256']:
        raise ValueError('Reviewed retirement executable/source required')
    action = protocol.get('action', 'retire')
    if action not in {'inspect', 'retire'}:
        raise ValueError('Exact inspected/retired cache operation required')
    output = owned_daemon._canonical(protocol['output'])
    output.mkdir(mode=0o700)
    report = dict(complete=False, action=action, protocol_sha256=digest(protocol_path), builds=[], clients=[])
    publish = lambda: owned_daemon.publish(output / 'report.json', report)
    publish()
    try:
        for number, item in enumerate(protocol['builds']):
            driver_path, operator_path = Path(item['driver']), Path(item['operator'])
            if digest(driver_path) != item['driver_sha256'] or digest(operator_path) != item['operator_sha256']:
                raise ValueError('Retained build cleanup journals changed')
            driver = owned_daemon.read_private_json(driver_path, cap=4*1024*1024)
            operator = owned_daemon.read_private_json(operator_path)
            with provision_lock(driver['provisioning']):
                proof = terminal_proof(driver, operator)
                root = owned_daemon._canonical(driver['provisioning']['roots']['root_dir']['path'])
                expected = {key: driver['provisioning']['roots']['root_dir'][key] for key in ('device', 'inode', 'uid')}
                if root_identity(root) != expected or root.parent != Path(driver['provisioning']['base']['path']):
                    raise ValueError('Registered cache identity changed')
                report_path = Path(item['build_report'])
                config_path = Path(item['driver_config'])
                if digest(report_path) != item['build_report_sha256'] or digest(config_path) != item['driver_config_sha256']:
                    raise ValueError('Build receipt/configuration identity changed')
                built = owned_daemon.read_private_json(report_path, cap=4*1024*1024)
                config = owned_daemon.read_private_json(config_path)
                if config != driver['config']:
                    raise ValueError('Build configuration differs from execution journal')
                if built.get('passed') is not True:
                    raise ValueError('Passing archived build required before cache retirement')
                retained = [dict(path=config['image_archive'], sha256=config['image_archive_sha256'])]
                retained.extend(dict(path=value['archive'], sha256=value['archive_sha256']) for value in config.get('additional_images', []))
                if set(driver['loaded_images']) != {config['image'], *[value['image'] for value in config.get('additional_images', [])]}:
                    raise ValueError('Loaded image archive inventory differs')
                for pair in built['pairs'].values():
                    for image in pair['images'].values():
                        if Path(image['archive']).name != image['archive']:
                            raise ValueError('Archive basename required')
                        retained.append(dict(path=str(report_path.parent / image['archive']), sha256=image['archive_sha256']))
                retained.extend([dict(path=str(report_path), sha256=item['build_report_sha256']),
                                 dict(path=str(config_path), sha256=item['driver_config_sha256']),
                                 dict(path=str(driver_path), sha256=item['driver_sha256']),
                                 dict(path=str(operator_path), sha256=item['operator_sha256'])])
                inventories = []
                for artifact in retained:
                    path = owned_daemon._canonical(artifact['path'])
                    if (path == root or root in path.parents or not path.is_file()
                            or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077
                            or digest(path) != artifact['sha256']):
                        raise ValueError('Archive/evidence retention failed')
                    inventories.append(artifact)
                if not inventories:
                    raise ValueError('Retained artifacts required before retiring cache')
                mounts = mount_inspection(root)
                intent = dict(root=str(root), root_identity=expected, owner_uid=os.getuid(), action=action,
                    special_entries=item.get('special_entries', []),
                    parent_user_namespace=os.readlink('/proc/self/ns/user'), terminal_proof=proof,
                    mount_inspection=mounts, retained_artifacts=inventories, permanently_retired=action == 'retire',
                    source_commit=protocol['source_commit'])
                intent_path = output / ('cache-' + str(number) + '.json')
                owned_daemon.publish(intent_path, intent)
                report['builds'].append(dict(intent=str(intent_path), complete=False)); publish()
                argv = [str(rootlesskit), '--state-dir=' + str(output / ('namespace-' + str(number))),
                        str(Path(sys.executable)), '-m', 'scripts.retire_build_cache', '--child', str(intent_path)]
                owned_client.run(argv, report['clients'], publish, output, timeout=900, capture_output=True)
                completed = owned_daemon.read_private_json(intent_path.with_suffix('.complete.json'), cap=4*1024*1024)
                if completed.get('complete') is not True or completed.get('action') != action:
                    raise RuntimeError('Cache operation lacks completion proof')
                if action == 'retire':
                    if root.exists() or root.is_symlink():
                        raise RuntimeError('Cache retirement incomplete')
                    owned_daemon.publish(root.parent / 'CACHE_RETIRED.json', dict(intent_sha256=digest(intent_path),
                        completion_sha256=digest(intent_path.with_suffix('.complete.json')), restart_prohibited=True))
                elif root_identity(root) != expected:
                    raise RuntimeError('Read-only cache inspection changed its root')
                report['builds'][-1]['complete'] = True; publish()
        report['complete'] = True
    finally:
        publish()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--protocol', type=Path)
    group.add_argument('--child', type=Path)
    args = parser.parse_args()
    child(args.child) if args.child else retire(args.protocol)
