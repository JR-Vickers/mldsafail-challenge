"""Owner console collector: read only, bounded, no environments or command contents.

Run the reviewed file with python3 in the existing root console.
Save stdout privately. Use --raw-output for a separate private raw evidence file. Classification deliberately remains pending; hashed cron
and unit files require separate owner review before a complete receipt is issued.
"""
import hashlib
import json
import itertools
import stat
import os
from pathlib import Path
import socket
import subprocess
import time

SECTIONS = {
    'root_crontab': ['crontab', '-l', '-u', 'root'],
    'user_crontab': ['crontab', '-l', '-u', 'mldsafail'],
    'system_units': ['systemctl', 'list-unit-files', '--no-pager', '--no-legend'],
    'loaded_units': ['systemctl', 'list-units', '--all', '--plain', '--no-pager', '--no-legend'],
    'system_identities': ['systemctl', 'show', '*.service', '*.timer', '*.socket', '*.path', '--property=Id,Names,User,ActiveState,UnitFileState,ControlGroup,Delegate,Triggers,TriggeredBy,Restart,FragmentPath,DropInPaths'],
    'user_identities': ['runuser', '-u', 'mldsafail', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000', 'systemctl', '--user', 'show', '*.service', '*.timer', '*.socket', '*.path', '--property=Id,Names,User,ActiveState,UnitFileState,ControlGroup,Delegate,Triggers,TriggeredBy,Restart,FragmentPath,DropInPaths'],
    'system_timers': ['systemctl', 'list-timers', '--all', '--no-pager'],
    'user_units': ['runuser', '-u', 'mldsafail', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000', 'systemctl', '--user', 'list-unit-files', '--no-pager'],
    'user_loaded': ['runuser', '-u', 'mldsafail', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000', 'systemctl', '--user', 'list-units', '--all', '--no-pager'],
    'user_timers': ['runuser', '-u', 'mldsafail', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000', 'systemctl', '--user', 'list-timers', '--all', '--no-pager'],
    'processes': ['ps', '-eo', 'uid,pid,ppid,comm'],
    'at_service': ['systemctl', 'show', 'atd.service', '-p', 'LoadState', '-p', 'ActiveState', '-p', 'UnitFileState'],
    'at_queue': ['atq'],
}
ROOTS = ('/etc/crontab', '/etc/anacrontab', '/etc/cron.d', '/etc/cron.hourly', '/etc/cron.daily', '/etc/cron.weekly', '/etc/cron.monthly', '/var/spool/cron', '/var/spool/at', '/var/spool/atjobs', '/var/spool/cron/atjobs', '/etc/systemd/system', '/run/systemd/system', '/root/.config/systemd/user', '/home/mldsafail/.config/systemd/user')


class CollectionDeadline(Exception):
    """Bypass per-command and per-path recoverable error handlers."""


MAX_HOPS = 16
MAX_ENTRIES = 2048
MAX_FILE = 1048576


def identity(st):
    return dict(device=st.st_dev, inode=st.st_ino, mode=st.st_mode,
                uid=st.st_uid, size=st.st_size, mtime_ns=st.st_mtime_ns,
                ctime_ns=st.st_ctime_ns)


def inspect_path(path):
    """Resolve literal links, including parent links, and recheck every identity."""
    original = os.path.abspath(path)
    row = dict(path=original, chain=[])
    watched = []
    pending = Path(original).parts[1:]
    current = Path('/')
    seen = set()
    try:
        while pending:
            current = current / pending[0]
            pending = pending[1:]
            st = current.lstat()
            watched.append((current, identity(st)))
            if stat.S_ISLNK(st.st_mode):
                if str(current) in seen or len(row['chain']) >= MAX_HOPS:
                    raise ValueError('symlink_limit_or_loop')
                seen.add(str(current))
                target = os.readlink(current)
                row['chain'].append(dict(path=str(current), literal_target=target,
                                         identity=identity(st)))
                resolved = os.path.normpath(str(current.parent / target))
                pending = Path(resolved).parts[1:] + tuple(pending)
                current = Path('/')
        st = current.lstat()
        row.update(final_target=str(current), identity=identity(st),
                   symlink=bool(row['chain']), mask=str(current) == '/dev/null')
        if stat.S_ISREG(st.st_mode):
            if st.st_size > MAX_FILE:
                raise ValueError('file_limit')
            with current.open('rb') as stream:
                if identity(os.fstat(stream.fileno())) != identity(st):
                    raise ValueError('target_changed')
                data = stream.read(MAX_FILE + 1)
                if len(data) > MAX_FILE or identity(os.fstat(stream.fileno())) != identity(st):
                    raise ValueError('target_changed_or_limit')
            row['sha256'] = hashlib.sha256(data).hexdigest()
        elif not stat.S_ISDIR(st.st_mode) and not row['mask']:
            raise ValueError('unsupported_target')
        for item, before in watched:
            if identity(item.lstat()) != before:
                raise ValueError('target_changed')
    except FileNotFoundError:
        if not row['chain'] and not os.path.lexists(original):
            row['absent'] = True
        else:
            row['error'] = 'dangling_target'
    except (OSError, ValueError) as exc:
        row['error'] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
    return row


def _collect(collector_hash, raw_stream, reviewed_paths=()):
    """raw_stream is an owner-created private binary file, never stdout."""
    started = time.monotonic()
    started_wall = time.time()
    sections, paths = {}, []
    def expired():
        return time.monotonic() - started >= 180
    for name, command in SECTIONS.items():
        row = dict(command=command, error=None, truncated=False, no_crontab=False)
        try:
            if expired():
                raise ValueError('collection_deadline')
            import tempfile
            with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
                def output_limit():
                    import resource
                    resource.setrlimit(resource.RLIMIT_FSIZE, (262144, 262144))
                process = subprocess.run(command, stdout=out, stderr=err, preexec_fn=output_limit,
                                         timeout=min(10, 180-(time.monotonic()-started)))
                out.seek(0); err.seek(0)
                stdout, stderr = out.read(262145), err.read(262145)
            raw = json.dumps(dict(section=name, stdout=stdout.hex(), stderr=stderr.hex()),
                             sort_keys=True).encode() + b'\n'
            raw_stream.write(raw)
            row.update(returncode=process.returncode, raw_sha256=hashlib.sha256(raw).hexdigest(),
                       sha256=hashlib.sha256(stdout + stderr).hexdigest(),
                       truncated=len(stdout) >= 262144 or len(stderr) >= 262144,
                       no_crontab=b'no crontab for' in stderr)
            if name == 'at_service':
                row['not_found'] = b'LoadState=not-found' in stdout
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            row.update(error=type(exc).__name__, returncode=None)
            raw = json.dumps(dict(section=name, stdout='', stderr='', error=row['error']), sort_keys=True).encode() + b'\n'
            raw_stream.write(raw)
            row['raw_sha256'] = hashlib.sha256(raw).hexdigest()
        sections[name] = row
    for root in (*ROOTS, *reviewed_paths):
        try:
            if expired():
                raise ValueError('collection_deadline')
            paths.append(inspect_path(root))
            if Path(root).is_dir() and not Path(root).is_symlink():
                def fail(error):
                    raise error
                def inventory():
                    for base, directories, files in os.walk(root, followlinks=False, onerror=fail):
                        before = identity(Path(base).lstat())
                        for name in directories + files:
                            yield Path(base) / name
                        if identity(Path(base).lstat()) != before:
                            raise ValueError('directory_changed')
                for count, item in enumerate(inventory(), 1):
                    if count > MAX_ENTRIES or expired():
                        raise ValueError('inventory_limit_or_deadline')
                    paths.append(inspect_path(item))
        except (OSError, ValueError) as exc:
            paths.append(dict(path=str(root), error=str(exc)))
    known = {p['path'] for p in paths}
    for target in {p['final_target'] for p in paths if 'final_target' in p} - known:
        paths.append(inspect_path(target))
    return dict(schema='mldsafail.scheduling-collection.v2', host=socket.gethostname(),
                uid=os.getuid(), time=started_wall, provenance='owner_root_console',
                collector_sha256=collector_hash, sections=sections, paths=paths,
                reviewed_paths=list(reviewed_paths), complete=not expired() and
                all('error' not in p for p in paths) and
                all(not r['truncated'] and ((r['error'] is None and
                    (r.get('returncode') == 0 or r.get('no_crontab') is True and r.get('returncode') == 1)) or
                    (name == 'at_queue' and r['error'] == 'FileNotFoundError'))
                    for name, r in sections.items()))


def collect(collector_hash, raw_stream, reviewed_paths=()):
    # Linux owner-console collection is bounded even on a blocking filesystem read.
    import signal
    def deadline(signum, frame):
        raise CollectionDeadline('collection_deadline')
    previous = signal.signal(signal.SIGALRM, deadline)
    signal.alarm(180)
    try:
        return _collect(collector_hash, raw_stream, reviewed_paths)
    except CollectionDeadline:
        return dict(schema='mldsafail.scheduling-collection.v2', complete=False,
                    error='collection_deadline', collector_sha256=collector_hash)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-output', required=True)
    parser.add_argument('--reviewed-path', action='append', default=[])
    args = parser.parse_args()
    # Exclusive creation refuses replacement, symlinks and shared existing files.
    parent = Path(args.raw_output).absolute().parent
    if parent.is_symlink() or parent.stat().st_uid != os.getuid() or parent.stat().st_mode & 0o077:
        raise ValueError('owner_private_output_directory_required')
    fd = os.open(args.raw_output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as raw:
        result = collect(hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), raw,
                         args.reviewed_path)
    result['raw_sha256'] = hashlib.sha256(Path(args.raw_output).read_bytes()).hexdigest()
    print(json.dumps(result, sort_keys=True))
