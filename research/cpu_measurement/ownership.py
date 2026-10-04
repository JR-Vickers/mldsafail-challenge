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
        self.parent_fd = None
        self.record = None

    def __enter__(self):
        for target in (self.parent.absolute(), self.directory.absolute()):
            if any(component.is_symlink() for component in (target, *target.parents)):
                raise RuntimeError('Ownership paths must not contain symlinks')
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.is_symlink() or self.directory.stat().st_mode & 0o077:
            raise RuntimeError('Ownership directory must be private')
        self.parent_fd = os.open(self.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.lock = os.open(self.directory / 'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.parent_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            journal = self.directory / 'journal.json'
            old = json.loads(journal.read_text()) if journal.exists() else None
            if old and old.get('state') != 'complete':
                raise RuntimeError('Interrupted ownership requires explicit cleanup reconciliation')
            identity = os.fstat(self.parent_fd)
            self.record = dict(schema=SCHEMA, generation=uuid.uuid4().hex,
                               state='owned', parent_device=identity.st_dev,
                               parent_inode=identity.st_ino, mutations=[])
            self.update('owned')
            return self
        except BaseException:
            os.close(self.lock)
            self.lock = None
            if self.parent_fd is not None:
                os.close(self.parent_fd)
                self.parent_fd = None
            raise

    def check_identity(self):
        identity = self.parent.stat(follow_symlinks=False)
        descriptor_identity = os.fstat(self.parent_fd)
        if (identity.st_dev, identity.st_ino) != (descriptor_identity.st_dev, descriptor_identity.st_ino):
            raise RuntimeError("Accounting parent path replaced")
        if (identity.st_dev, identity.st_ino) != (self.record['parent_device'], self.record['parent_inode']):
            raise RuntimeError('Accounting parent identity changed')

    def update(self, state, **values):
        self.check_identity()
        self.record.update(values, state=state)
        publish(self.directory / 'journal.json', self.record)

    def mutation(self, operation, **values):
        self.record['mutations'].append(dict(operation=operation, **values))
        self.update('running')

    def finish(self, evidence):
        if self.record['state'] == 'complete':
            raise RuntimeError('Ownership generation already completed')
        if evidence.get('cleanup_complete') is not True:
            raise RuntimeError('Incomplete cleanup cannot release ownership')
        evidence.update(schema=SCHEMA, generation=self.record['generation'],
                        parent_device=self.record['parent_device'], parent_inode=self.record['parent_inode'], ownership_mutations=self.record['mutations'])
        path = self.directory / (self.record['generation'] + '.json')
        publish(path, evidence)
        publish(self.directory / (self.record['generation'] + '-ownership.json'),
                dict(self.record, state='complete', evidence_file=path.name,
                     evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        self.update('complete', evidence_file=path.name,
                    evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        return evidence

    def __exit__(self, kind, value, traceback):
        try:
            if kind is not None:
                # Preserve interruption even if the parent path was replaced or
                # disappeared; recording failure must not require live identity.
                self.record.update(state='interrupted', error_type=kind.__name__, error=str(value))
                try:
                    publish(self.directory / 'journal.json', self.record)
                    publish(self.directory / (self.record['generation'] + '-interrupted.json'), self.record)
                except BaseException as journal_error:
                    value.add_note('Interruption journal publication failed: ' + repr(journal_error))
                return False
        finally:
            if self.lock is not None:
                os.close(self.lock)
            if self.parent_fd is not None:
                os.close(self.parent_fd)
                self.parent_fd = None


def sync_tree(root):
    """Sync bounded trusted source artifacts before any completion receipt."""
    root = Path(root)
    entries = list(root.rglob('*'))
    if any(path.is_symlink() for path in entries):
        raise RuntimeError('Source artifact symlinks forbidden')
    for path in entries:
        if path.is_file():
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    for directory in [*sorted((path for path in entries if path.is_dir()), reverse=True), root]:
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def canonical_directory(parent):
    """One immutable user-state mapping for each canonical host accounting parent."""
    key = hashlib.sha256(str(Path(parent).resolve()).encode()).hexdigest()
    return Path.home() / '.local' / 'state' / 'mldsafail' / 'cpu-ownership' / key
