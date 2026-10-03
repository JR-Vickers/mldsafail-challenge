"""Copy exact release artifacts into a private, immutable commit directory.

Inventory JSON: source_commit (full hash), artifacts mapping destination basenames
 to {path, sha256}, with at least manifest, images, wheel, checksums and rollback
 roles identified by the roles mapping. No build, relabel, deployment or deletion.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from deploy.recovery_journal import atomic_json, safe_path


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def validate_inventory(inventory):
    commit = inventory['source_commit']
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Full source commit required')
    artifacts = inventory['artifacts']
    if set(inventory['roles']) != {'manifest', 'images', 'wheel', 'checksums', 'rollback'}:
        raise ValueError('All release roles required')
    if not set(inventory['roles'].values()) <= set(artifacts):
        raise ValueError('Missing release material')
    for name, item in artifacts.items():
        if Path(name).name != name or name in {'.', '..', 'retention.json'}:
            raise ValueError('Unsafe artifact name')
        safe_path(item['path'])
        if not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ValueError('Invalid checksum')
    return commit


def verify(root, commit, inventory=None):
    root = safe_path(root)
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Full source commit required')
    destination = safe_path(root / commit)
    if root.stat().st_mode & 0o077 or destination.stat().st_mode & 0o777 != 0o500:
        raise ValueError('Retained release permissions mismatch')
    stored = json.loads(safe_path(destination / 'retention.json').read_text())
    if validate_inventory(stored) != commit:
        raise ValueError('Retained commit mismatch')
    if inventory is not None and stored != inventory:
        raise ValueError('Conflicting retained release')
    artifacts = stored['artifacts']
    if {p.name for p in destination.iterdir()} != set(artifacts) | {'retention.json'}:
        raise ValueError('Retained artifact list mismatch')
    for name in [*artifacts, 'retention.json']:
        target = safe_path(destination / name)
        if not target.is_file() or target.stat().st_mode & 0o777 != 0o400:
            raise ValueError('Retained artifact permissions mismatch')
        if name in artifacts and digest(target) != artifacts[name]['sha256']:
            raise ValueError('Retained checksum mismatch')
    manifest = json.loads((destination / stored['roles']['manifest']).read_text())
    if manifest.get('source_commit') != commit:
        raise ValueError('Manifest source commit mismatch')
    return destination


def retain(inventory, root):
    root = safe_path(root)
    commit = validate_inventory(inventory)
    destination = safe_path(root / commit)
    if destination.exists():
        return verify(root, commit, inventory)
    artifacts = inventory['artifacts']
    for item in artifacts.values():
        source = safe_path(item['path'])
        if not source.is_file() or digest(source) != item['sha256']:
            raise ValueError('Missing artifact or checksum mismatch')
    manifest = json.loads(Path(artifacts[inventory['roles']['manifest']]['path']).read_text())
    if manifest.get('source_commit') != commit:
        raise ValueError('Manifest source commit mismatch')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_mode & 0o077:
        raise ValueError('Release root must be private')
    temporary = Path(tempfile.mkdtemp(prefix='.retaining-', dir=root))
    try:
        for name, item in artifacts.items():
            target = temporary / name
            shutil.copyfile(item['path'], target)
            target.chmod(0o400)
            if digest(target) != item['sha256']:
                raise ValueError('Copied checksum mismatch')
            with target.open('rb') as stream:
                os.fsync(stream.fileno())
        atomic_json(temporary / 'retention.json', inventory)
        (temporary / 'retention.json').chmod(0o400)
        # Serialize publication without replacing an existing commit directory.
        import fcntl
        with safe_path(root / '.publication-lock').open('a') as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            if destination.exists():
                raise ValueError('Release published concurrently; retry verification')
            temporary.rename(destination)
            destination.chmod(0o500)
            descriptor = os.open(root, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return destination
    finally:
        if temporary.exists():
            temporary.chmod(0o700)
            shutil.rmtree(temporary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--commit')
    parser.add_argument('--root', type=Path, default=Path.home() / '.local/share/mldsafail/releases')
    args = parser.parse_args()
    os.umask(0o077)
    if args.verify:
        if not args.commit or args.inventory:
            parser.error('--verify requires --commit and excludes --inventory')
        print(verify(args.root, args.commit))
    else:
        if not args.inventory or args.commit:
            parser.error('retention requires --inventory and excludes --commit')
        print(retain(json.loads(args.inventory.read_text()), args.root))
