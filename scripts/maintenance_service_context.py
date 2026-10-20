"""Bounded read-only service-context collection; never executes service programs.

Capture PATH only from environment values. Inspect installed/loaded/active states
separately. Missing manager/context evidence remains incomplete, never SSH-PATH
inferred. No owner-console collection or external-path allowlist is generated.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

PROPERTIES = ('Id','Names','LoadState','ActiveState','SubState','UnitFileState',
    'FragmentPath','DropInPaths','User','Group','WorkingDirectory','RootDirectory',
    'ExecSearchPath','EnvironmentFiles','ExecStart','ExecStartPre','ExecStartPost',
    'Triggers','TriggeredBy','Requires','Wants','PartOf','BindsTo','Conflicts',
    'Restart','RestartMode','ControlGroup','MainPID','InvocationID','Transient','Environment')
UNITS = {
    'system': ('getty@tty1.service','serial-getty@ttyS0.service','cron.service',
               'atd.service','mldsafail-host-check.service','mldsafail-host-check.timer',
               'mldsafail-backup.service','mldsafail-backup.timer'),
    'user': ('docker.service','docker.socket','default.target','app.slice','session.slice',
             'production-epoch.slice'),
}


def inspect(*, runner=subprocess.run):
    deadline = time.monotonic() + 40
    rows = {}
    for manager, units in UNITS.items():
        prefix = ['systemctl'] + (['--user'] if manager == 'user' else [])
        for unit in units:
            if time.monotonic() >= deadline:
                rows[manager+':'+unit] = dict(error='collection_deadline')
                continue
            try:
                result = runner(prefix+['show',unit,'--no-pager','--property='+','.join(PROPERTIES)],
                                capture_output=True, timeout=min(2,deadline-time.monotonic()))
                if max(len(result.stdout),len(result.stderr)) > 131072:
                    raise ValueError('output_limit')
                properties = dict(line.split('=',1) for line in result.stdout.decode().splitlines() if '=' in line)
                # Never retain unrelated environment variables or their raw bytes.
                environment = shlex.split(properties.pop('Environment',''))
                paths = [v.split('=',1)[1] for v in environment if v.startswith('PATH=')]
                properties['EnvironmentPATH'] = paths
                rows[manager+':'+unit] = dict(returncode=result.returncode, properties=properties,
                    service_path_complete=False, limitation='EnvironmentFiles, manager defaults and executable/import semantics still require review')
            except (OSError,ValueError,subprocess.TimeoutExpired) as error:
                rows[manager+':'+unit] = dict(error=type(error).__name__)
    sources = {}
    for row in rows.values():
        props=row.get('properties',{})
        paths=props.get('FragmentPath','').split()+props.get('DropInPaths','').split()
        for name in paths:
            path=Path(name)
            try:
                st=path.stat()
                if not path.is_absolute() or not path.is_file() or st.st_size>1048576:
                    raise ValueError('source_limit')
                data=path.read_bytes()
                sources[name]=dict(resolved=str(path.resolve()),sha256=hashlib.sha256(data).hexdigest(),
                                   uid=st.st_uid,mode=st.st_mode&0o777,bytes=st.st_size)
            except (OSError,ValueError) as error:
                sources[name]=dict(error=type(error).__name__)
    return dict(schema='mldsafail.service-context.v1',time=time.time(),uid=os.getuid(),
                host=os.uname().nodename,units=rows,sources=sources,complete=False,
                limitation='Read-only context evidence; no restart-owner exclusion, semantic closure or execution approval')


if __name__ == '__main__':
    print(json.dumps(inspect(),sort_keys=True))
