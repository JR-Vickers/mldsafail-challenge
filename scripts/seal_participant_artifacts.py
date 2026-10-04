"""Seal only checksum-bound regular participant artifacts; exclude install trees.

Inventory is JSON mapping owned relative filenames to SHA-256. Files are opened
relative to held directory descriptors with O_NOFOLLOW; symlink targets never
receive chmod. All files validate before any permissions change.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat


def seal(root, inventory):
    root = Path(root).absolute()
    if root.resolve() != root or not inventory:
        raise ValueError('Non-symlink owned root and artifact inventory required')
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    files = []
    try:
        for relative, expected in inventory.items():
            path = Path(relative)
            if (path.is_absolute() or any(part in {'.', '..', 'installed', '.venv'} for part in path.parts)
                    or not path.parts or not re.fullmatch(r'[a-f0-9]{64}', expected)):
                raise ValueError('Unsafe participant artifact inventory')
            parent_fd = os.dup(root_fd)
            try:
                for component in path.parts[:-1]:
                    child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
                    os.close(parent_fd)
                    parent_fd = child
                descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
                files.append(descriptor)
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise ValueError('Participant artifacts must be single-link regular files')
                checksum = hashlib.sha256()
                while chunk := os.read(descriptor, 1024 * 1024):
                    checksum.update(chunk)
                if checksum.hexdigest() != expected:
                    raise ValueError('Participant artifact checksum mismatch')
            finally:
                os.close(parent_fd)
        for descriptor in files:
            os.fchmod(descriptor, 0o400)
    finally:
        for descriptor in files:
            os.close(descriptor)
        os.close(root_fd)
    return {'sealed_artifacts': len(files)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(seal(args.root, json.loads(args.inventory.read_text()))))
    except Exception:
        print(json.dumps({'participant_sealing_failed': True}))
        raise SystemExit(1)
