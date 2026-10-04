"""Private durable accounting ownership. Interrupted generations fence new work.

The flock only serializes journal mutation; an unfinished durable generation is
never implicitly reclaimed, including after SIGKILL or a host restart.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import uuid

SCHEMA = 'mldsafail.cpu-evidence.v1'


def publish(path: Path, value: dict):
    """Publish a complete record atomically and sync both file and directory."""
    path = Path(path)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        with temporary.open('x') as stream:
            os.chmod(temporary, 0o600)
            json.dump(value, stream, allow_nan=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


class Ownership:
    def __init__(self, directory, parent):
        self.directory = Path(directory)
        self.parent = Path(parent)
        self.lock = None
        self.record = None

    def __enter__(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.is_symlink() or self.directory.stat().st_mode & 0o077:
            raise RuntimeError('Ownership directory must be private')
        self.lock = os.open(self.directory / 'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            journal = self.directory / 'journal.json'
            old = json.loads(journal.read_text()) if journal.exists() else None
            if old and old.get('state') != 'complete':
                raise RuntimeError('Interrupted ownership requires explicit cleanup reconciliation')
            identity = self.parent.stat()
            self.record = dict(schema=SCHEMA, generation=uuid.uuid4().hex,
                               state='owned', parent_device=identity.st_dev,
                               parent_inode=identity.st_ino, mutations=[])
            self.update('owned')
            return self
        except BaseException:
            os.close(self.lock)
            self.lock = None
            raise

    def update(self, state, **values):
        identity = self.parent.stat()
        if (identity.st_dev, identity.st_ino) != (self.record['parent_device'], self.record['parent_inode']):
            raise RuntimeError('Accounting parent identity changed')
        self.record.update(values, state=state)
        publish(self.directory / 'journal.json', self.record)

    def mutation(self, operation, **values):
        self.record['mutations'].append(dict(operation=operation, **values))
        self.update('running')

    def finish(self, evidence):
        if evidence.get('cleanup_complete') is not True:
            raise RuntimeError('Incomplete cleanup cannot release ownership')
        evidence.update(schema=SCHEMA, generation=self.record['generation'],
                        parent_device=self.record['parent_device'], parent_inode=self.record['parent_inode'])
        path = self.directory / (self.record['generation'] + '.json')
        publish(path, evidence)
        self.update('complete', evidence_file=path.name,
                    evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        return evidence

    def __exit__(self, kind, value, traceback):
        try:
            if kind is not None:
                self.update('interrupted', error_type=kind.__name__, error=str(value))
        finally:
            if self.lock is not None:
                os.close(self.lock)
