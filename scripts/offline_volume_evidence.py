"""Preserve disposable PostgreSQL files without claiming recovery acceptance.

Called only by a separately reviewed mapped-namespace cache inspection. Never
opens devices/links, follows links, launches database code, or changes the source.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import tarfile

from deploy import owned_daemon


def inventory(root):
    root = owned_daemon._canonical(root)
    device = root.stat().st_dev
    rows = {}
    for path in [root, *sorted(root.rglob('*'))]:
        info = path.lstat()
        if info.st_dev != device or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise ValueError('Offline database evidence requires only same-filesystem directories and regular files')
        name = '.' if path == root else path.relative_to(root).as_posix()
        row = dict(mode=info.st_mode, uid=info.st_uid, gid=info.st_gid, size=info.st_size if path.is_file() else 0)
        if path.is_file():
            with path.open('rb') as stream:
                row['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        rows[name] = row
    return rows


def archive(root, output):
    root, output = map(owned_daemon._canonical, (root, output))
    if output == root or root in output.parents:
        raise ValueError('Evidence archive must remain outside the retired store')
    rows = inventory(root)
    # x mode preserves any earlier complete or partial attempt.
    with tarfile.open(output, 'x:gz', dereference=False) as target:
        os.chmod(output, 0o600)
        for name in rows:
            target.add(root if name == '.' else root / name, arcname=name, recursive=False)
    if inventory(root) != rows:
        raise RuntimeError('Offline database files changed during retention')
    with output.open('rb') as stream:
        archive_sha256 = hashlib.file_digest(stream, 'sha256').hexdigest()
    receipt = dict(schema='mldsafail.offline-volume-evidence.v1', source=str(root),
        archive=str(output), archive_sha256=archive_sha256,
        files=rows, recovery_acceptance=False)
    verify(root, receipt)
    owned_daemon.publish(output.with_suffix(output.suffix + '.json'), receipt)
    return receipt


def verify(root, receipt):
    if receipt.get('schema') != 'mldsafail.offline-volume-evidence.v1' or receipt.get('recovery_acceptance') is not False:
        raise ValueError('Exact scoped offline database receipt required')
    root = owned_daemon._canonical(root)
    archive = owned_daemon._canonical(receipt['archive'])
    if receipt['source'] != str(root) or archive == root or root in archive.parents:
        raise ValueError('Offline database evidence source/archive binding changed')
    owned_daemon._private_directory(archive.parent)
    info = archive.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Private regular offline archive required')
    with archive.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != receipt['archive_sha256']:
            raise ValueError('Offline database archive checksum changed')
    actual = {}
    with tarfile.open(archive, 'r:gz') as source:
        for member in source:
            if member.name in actual or not (member.isdir() or member.isfile()):
                raise ValueError('Unexpected offline archive entry')
            row = dict(mode=(stat.S_IFDIR if member.isdir() else stat.S_IFREG) | member.mode,
                       uid=member.uid, gid=member.gid, size=member.size)
            if member.isfile():
                row['sha256'] = hashlib.file_digest(source.extractfile(member), 'sha256').hexdigest()
            actual[member.name] = row
    if actual != receipt['files'] or inventory(root) != receipt['files']:
        raise ValueError('Complete offline database inventory differs')
    return True
