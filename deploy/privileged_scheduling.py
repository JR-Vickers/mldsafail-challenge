"""Owner console collector: read only, bounded, no environments or command contents.

Paste this file into `python3 - <<'PY' ... PY` in the existing root console.
Save stdout privately. Classification deliberately remains pending; hashed cron
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
    'system_timers': ['systemctl', 'list-timers', '--all', '--no-pager'],
    'user_units': ['runuser', '-u', 'mldsafail', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000', 'systemctl', '--user', 'list-unit-files', '--no-pager'],
    'user_loaded': ['runuser', '-u', 'mldsafail', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000', 'systemctl', '--user', 'list-units', '--all', '--no-pager'],
    'user_timers': ['runuser', '-u', 'mldsafail', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000', 'systemctl', '--user', 'list-timers', '--all', '--no-pager'],
    'processes': ['ps', '-eo', 'uid,pid,ppid,comm'],
    'at_service': ['systemctl', 'show', 'atd.service', '-p', 'LoadState', '-p', 'ActiveState', '-p', 'UnitFileState'],
    'at_queue': ['atq'],
}
ROOTS = ('/etc/crontab', '/etc/anacrontab', '/etc/cron.d', '/etc/cron.hourly', '/etc/cron.daily', '/etc/cron.weekly', '/etc/cron.monthly', '/var/spool/cron', '/var/spool/at', '/var/spool/atjobs', '/var/spool/cron/atjobs', '/etc/systemd/system', '/run/systemd/system', '/root/.config/systemd/user', '/home/mldsafail/.config/systemd/user')


def collect(collector_hash):
    sections = {}
    for name, command in SECTIONS.items():
        row = dict(command=command, error=None, truncated=False, no_crontab=False)
        try:
            # Temporary file bounds memory; command runtime bounded independently.
            import tempfile
            with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
                p = subprocess.run(command, stdout=out, stderr=err, timeout=10)
                out.seek(0); err.seek(0)
                raw = out.read(262145) + err.read(262145)
            row.update(returncode=p.returncode, sha256=hashlib.sha256(raw).hexdigest(),
                       truncated=len(raw) > 262144, no_crontab=b'no crontab for' in raw)
            # Crontab/queue content may contain secrets: retain identities only.
            if name not in ('root_crontab', 'user_crontab', 'at_queue'):
                row['output'] = raw[:262144].decode(errors='replace')
        except (OSError, subprocess.SubprocessError) as exc:
            row.update(error=type(exc).__name__, returncode=None)
        sections[name] = row
    paths = []
    for root in ROOTS:
        try:
            p = Path(root)
            if not p.exists():
                paths.append(dict(path=root, absent=True)); continue
            candidates = [p] if not p.is_dir() else list(itertools.islice(p.rglob('*'), 2049))
            if len(candidates) > 2048:
                raise ValueError('path_limit')
            for item in candidates:
                row = dict(path=str(item), symlink=item.is_symlink(), uid=item.lstat().st_uid)
                if stat.S_ISREG(item.lstat().st_mode) and not item.is_symlink():
                    if item.stat().st_size > 1048576:
                        raise ValueError('file_limit')
                    row['sha256'] = hashlib.sha256(item.read_bytes()).hexdigest()
                paths.append(row)
        except (OSError, ValueError) as exc:
            paths.append(dict(path=root, error=type(exc).__name__))
    return dict(schema='mldsafail.privileged-scheduling.v1', host=socket.gethostname(), uid=os.getuid(),
                time=time.time(), provenance='owner_root_console', collector_sha256=collector_hash,
                sections=sections, paths=paths, at_state='inspection_failed',
                classification_complete=False, unclassified_paths=list(ROOTS))


if __name__ == '__main__':
    # When pasted, supply the locally reviewed source hash as the first input line
    # via COLLECTOR_SHA256; no credentials or root access configuration is stored.
    print(json.dumps(collect(os.environ.get('COLLECTOR_SHA256', 'UNBOUND')), sort_keys=True))
