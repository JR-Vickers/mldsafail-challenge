"""Bounded application-account inspection; no cgroups created or units changed."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time


def command(argv):
    try:
        result = subprocess.run(argv, capture_output=True, timeout=5)
        return dict(argv=argv, code=result.returncode, stdout=result.stdout[:262144].hex(),
                    stderr=result.stderr[:262144].hex(), truncated=max(len(result.stdout), len(result.stderr)) > 262144)
    except (OSError, subprocess.TimeoutExpired) as error:
        return dict(argv=argv, error=type(error).__name__)


def cgroup(path):
    row = dict(path=str(path), exists=path.exists())
    if not row['exists']:
        return row
    row.update(resolved=str(path.resolve()), uid=path.stat().st_uid, mode=stat.S_IMODE(path.stat().st_mode), files={})
    for name in ('cgroup.procs', 'cgroup.controllers', 'cgroup.subtree_control', 'cpu.max',
                 'memory.max', 'memory.swap.max', 'pids.max'):
        file = path/name
        try:
            st = file.stat()
            row['files'][name] = dict(uid=st.st_uid, mode=stat.S_IMODE(st.st_mode), writable=os.access(file, os.W_OK),
                                     value=file.read_text()[:16384])
        except OSError as error:
            row['files'][name] = dict(error=type(error).__name__)
    return row


def inspect():
    base = Path('/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service')
    paths = {base/'app.slice', base/'session.slice', base/'production.slice'/'production-epoch.slice'}
    for path in tuple(paths):
        paths.update(p for p in path.parents if p.is_relative_to('/sys/fs/cgroup'))
    commands = [
        ['systemctl', 'list-units', '--all', '--no-pager', 'getty@*.service'],
        ['systemctl', 'list-unit-files', '--no-pager', 'getty@*.service'],
        ['systemctl', 'show', 'getty@tty1.service', 'serial-getty@ttyS0.service',
         '--property=Id,Names,LoadState,ActiveState,UnitFileState,FragmentPath,DropInPaths,Triggers,TriggeredBy,Requires,Wants,PartOf,BindsTo,Restart,ExecStart'],
        ['systemctl', 'cat', 'getty@tty1.service', 'serial-getty@ttyS0.service'],
        ['systemctl', '--user', 'show', 'app.slice', 'session.slice', 'production-epoch.slice',
         '--property=Id,Names,LoadState,ActiveState,UnitFileState,ControlGroup,Delegate,FragmentPath,DropInPaths'],
    ]
    sources = {}
    for path in ('/bin/setupcon', '/etc/default/console-setup', '/etc/default/keyboard',
                 '/etc/console-setup/cached_setup_keyboard.sh', '/etc/console-setup/cached_setup_font.sh'):
        try:
            data = Path(path).read_bytes()
            sources[path] = dict(resolved=str(Path(path).resolve()), sha256=hashlib.sha256(data).hexdigest(),
                                 text_hex=data.hex() if len(data) <= 262144 and b'\0' not in data else None)
        except OSError as error:
            sources[path] = dict(error=type(error).__name__)
    return dict(time=time.time(), uid=os.getuid(), hostname=os.uname().nodename,
                commands=[command(c) for c in commands], cgroups=[cgroup(p) for p in sorted(paths)], sources=sources)


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True))
