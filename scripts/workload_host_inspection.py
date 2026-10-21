"""Bounded read-only protected-runtime evidence collector (stdlib, SSH streamable).

Raw observations go only to stdout; redirect to a private local file. This is
collection, never scheduling classification or installed acceptance. No file
contents from configurations, environments, process argv or keys are collected.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import resource
import socket
import stat
import subprocess
import time

LIMIT = 262144


def collect(*, paths=(), seconds=90):
    started = time.monotonic()
    uid = os.getuid()
    account = pwd.getpwuid(uid).pw_name
    rows = {}

    def read(path):
        try:
            with open(path, 'rb') as stream:
                data = stream.read(LIMIT + 1)
            return dict(text=data[:LIMIT].decode(errors='replace'), truncated=len(data) > LIMIT)
        except OSError as error:
            return dict(error=type(error).__name__)

    def run(name, argv):
        remaining = seconds - (time.monotonic() - started)
        if remaining <= 0:
            rows[name] = dict(error='collection_deadline', argv=argv)
            return
        def bounded():
            resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))
        import tempfile
        try:
            with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
                result = subprocess.run(argv, stdout=out, stderr=err, timeout=min(5, remaining), preexec_fn=bounded)
                out.seek(0); err.seek(0)
                stdout, stderr = out.read(LIMIT), err.read(LIMIT)
            rows[name] = dict(argv=argv, code=result.returncode, stdout=stdout.decode(errors='replace'),
                              stderr=stderr.decode(errors='replace'), truncated=max(len(stdout), len(stderr)) >= LIMIT)
        except (OSError, subprocess.TimeoutExpired) as error:
            rows[name] = dict(argv=argv, error=type(error).__name__)

    for manager, prefix in (('system', ['systemctl']), ('user', ['systemctl', '--user'])):
        for kind, args in (
            ('units', ['list-units', '--all', '--plain', '--no-pager', '--no-legend']),
            ('files', ['list-unit-files', '--no-pager', '--no-legend']),
            ('timers', ['list-timers', '--all', '--no-pager']),
            ('jobs', ['list-jobs', '--no-pager']),
            ('identities', ['show', '*.service', '*.timer', '*.socket', '*.path',
                            '--property=Id,Names,User,ActiveState,UnitFileState,ControlGroup,Delegate,Triggers,TriggeredBy,Restart,FragmentPath,DropInPaths'])):
            run(manager+'_'+kind, prefix+args)
    for name, argv in (
        ('cron', ['crontab', '-l']), ('at', ['atq']),
        ('processes', ['ps', '-eo', 'uid,pid,ppid,lstart,comm']),
        ('mounts', ['findmnt', '--json', '-o', 'TARGET,SOURCE,FSTYPE,OPTIONS,SIZE,AVAIL']),
        ('docker', ['docker', '--host', f'unix:///run/user/{uid}/docker.sock', 'info', '--format', '{{json .}}']),
        ('containers', ['docker', '--host', f'unix:///run/user/{uid}/docker.sock', 'ps', '-a', '--no-trunc', '--format', '{{json .}}']),
        ('privileged_visibility', ['sudo', '-n', 'true']),
    ): run(name, argv)
    # Container inspect is filtered to ownership/birth/security fields; no Env.
    for index, line in enumerate(rows.get('containers', {}).get('stdout', '').splitlines()[:64]):
        try:
            identifier = json.loads(line)['ID']
            if len(identifier) != 64 or any(c not in '0123456789abcdef' for c in identifier): continue
            run('container_'+str(index), ['docker', '--host', f'unix:///run/user/{uid}/docker.sock',
                'inspect', '--format', '{{json .Id}} {{json .Image}} {{json .State}} {{json .HostConfig.RestartPolicy}} {{json .Config.User}} {{json .HostConfig.CgroupParent}} {{json .Mounts}}', identifier])
        except (KeyError, ValueError): continue
    files = {path: read(path) for path in ('/proc/sys/kernel/random/boot_id', '/proc/self/uid_map',
             '/proc/self/gid_map', '/proc/self/cgroup', '/proc/meminfo', '/etc/subuid', '/etc/subgid')}
    # Rootless daemon ancestry is independent of the SSH session ancestry.
    cgroups, processes = {}, {}
    for proc in sorted(Path('/proc').glob('[0-9]*'), key=lambda p: int(p.name)):
        if len(processes) >= 2048 or time.monotonic()-started >= seconds: break
        try:
            if proc.stat().st_uid != uid: continue
            comm = (proc/'comm').read_text().strip()
            if comm not in ('dockerd', 'rootlesskit', 'containerd', 'systemd'): continue
            processes[proc.name] = {key: read(proc/key) for key in ('stat', 'uid_map', 'gid_map', 'cgroup')}
        except OSError: continue
    for entry in [files['/proc/self/cgroup'], *(r['cgroup'] for r in processes.values())]:
        for line in entry.get('text', '').splitlines():
            if not line.startswith('0::'): continue
            path = Path('/sys/fs/cgroup')/line[3:].lstrip('/')
            for ancestor in (path, *path.parents):
                if not ancestor.is_relative_to('/sys/fs/cgroup'): continue
                try:
                    st = ancestor.stat()
                    cgroups[str(ancestor)] = dict(device=st.st_dev, inode=st.st_ino, uid=st.st_uid,
                        files={name: read(ancestor/name) for name in ('cgroup.controllers', 'cgroup.subtree_control',
                          'cgroup.events', 'memory.max', 'memory.current', 'memory.swap.max', 'cpu.max', 'pids.max')})
                except OSError as error: cgroups[str(ancestor)] = dict(error=type(error).__name__)
    artifacts = {}
    for name in paths:
        path = Path(name)
        try:
            st = path.lstat()
            row = dict(device=st.st_dev, inode=st.st_ino, uid=st.st_uid, mode=stat.S_IMODE(st.st_mode), bytes=st.st_size)
            if stat.S_ISREG(st.st_mode) and st.st_size <= 16*1024**2:
                with path.open('rb') as stream:
                    before = os.fstat(stream.fileno())
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                    after = os.fstat(stream.fileno())
                if before != after or st != before: raise ValueError('artifact_changed')
                row['sha256'] = digest
            artifacts[name] = row
        except (OSError, ValueError) as error: artifacts[name] = dict(error=str(error))
    return dict(schema='mldsafail.workload-host-collection.v1', captured_at=time.time(),
        hostname=socket.gethostname(), uid=uid, account=account, commands=rows, files=files,
        daemon_processes=processes, cgroups=cgroups, artifacts=artifacts,
        scheduling_classified=False, execution_authority=False,
        owner_collection_required=['root/user cron and referenced scripts', 'other user managers and triggers',
                                  'retained release/schema compatibility', 'proposed delegation and output mount'])


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', action='append', default=[])
    args = parser.parse_args()
    print(json.dumps(collect(paths=args.path), sort_keys=True))
