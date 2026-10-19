"""Read-only initial SSH admission; stdlib only, no provisioning or image calls.

Run as the deployment user. The caller records its bounded SSH interval in the
single initial preflight allowance. Returned inventories contain no environment,
credential values, command lines, SQL parameters or scientific evidence.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def snapshot(expected, *, seconds=60):
    if os.getuid() != 1000 or not 0 < seconds <= 300:
        raise ValueError('Bounded deployment-user inspection required')
    started = time.monotonic()
    deadline = started+seconds
    def command(args, ceiling=10):
        available = deadline-time.monotonic()
        if available <= 0:
            raise TimeoutError('Initial preflight deadline exhausted')
        result = subprocess.run(args, timeout=min(ceiling,available), capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError('Read-only initial preflight command failed')
        return result.stdout
    docker = ['docker','--host','unix:///run/user/1000/docker.sock']
    identifiers = command(docker+['ps','-aq','--no-trunc']).decode().split()
    if set(identifiers) != {row['Id'] for row in expected['containers']}:
        raise RuntimeError('Protected inventory changed')
    actual = json.loads(command(docker+['inspect',*identifiers]))
    indexed = {row['Id']:row for row in actual}
    for row in expected['containers']:
        value = indexed[row['Id']]
        if value['Image'] != row['Image'] or any(value['State'][key] != row['State'][key]
            for key in ('Running','Pid','StartedAt')):
            raise RuntimeError('Protected deployment identity changed')
    if command(['systemctl','--user','list-jobs','--no-legend']).strip():
        raise RuntimeError('Current user jobs prohibit admission')
    active = json.loads(command(['systemctl','--user','list-units','--state=active','--output=json','--no-legend']))
    allowed = expected.get('reconciled_active_units', {})
    selected = {row['unit']: row for row in active if row['unit'].startswith('mldsafail-')}
    if set(selected) != set(allowed):
        raise RuntimeError('Active application operator or maintenance requires reconciliation')
    for name, evidence in allowed.items():
        details = dict(line.split('=',1) for line in command(['systemctl','--user','show',name,
            '--property=ControlGroup','--property=ActiveState','--property=SubState',
            '--property=NextElapseUSecRealtime']).decode().splitlines() if '=' in line)
        if name.endswith('.slice'):
            group = Path('/sys/fs/cgroup')/details['ControlGroup'].lstrip('/')
            if (not group.is_dir() or not (group/'cgroup.procs').is_file()
                    or details['ControlGroup'] != evidence['control_group']) or any(
                    path.read_text().strip() for path in group.rglob('cgroup.procs')):
                raise RuntimeError('Reconciled slice is populated or changed')
        elif name.endswith('.timer'):
            if details != evidence:
                raise RuntimeError('Reconciled timer changed')
        else:
            raise RuntimeError('Active executable unit prohibits admission')
    coordinator = next(row for row in actual if row['Name']=='/mldsafail-private-coordinator-1')
    query = '''import os
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.orm import Session
from mldsafail.web.models import EvaluationJob
with Session(create_engine(os.environ['MLDSAFAIL_DATABASE_URL'])) as session:
 session.execute(text('SET TRANSACTION READ ONLY'))
 print(session.scalar(select(func.count()).select_from(EvaluationJob).where(EvaluationJob.status.in_(['queued','claimed','running']))))
'''
    if int(command(docker+['exec',coordinator['Id'],'/app/.venv/bin/python','-c',query])):
        raise RuntimeError('Pending evaluation jobs prohibit admission')
    free = shutil.disk_usage('/srv').free
    memory = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
        if line.startswith('MemAvailable:')))*1024
    if free < 8*1024**3 or memory < 128*1024**2:
        raise RuntimeError('Initial admission floor failed')
    if os.readlink('/srv/mldsafail/current') != expected['current_release']:
        raise RuntimeError('Protected current installation changed')
    for receipt in expected['receipts']:
        with Path(receipt['path']).open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest() != receipt['sha256']:
                raise RuntimeError('Protected retained record changed')
    if os.path.lexists(expected['c_socket']):
        raise RuntimeError('Terminal C endpoint remains')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    def process(pid):
        root = Path('/proc')/str(pid)
        fields = (root/'stat').read_text().rsplit(')',1)[1].split()
        return dict(pid=pid,start_ticks=int(fields[19]),uid=root.stat().st_uid,
            session=int(fields[3]),group=int(fields[2]),
            cmdline_sha256=hashlib.sha256((root/'cmdline').read_bytes()).hexdigest(),boot_id=boot)
    processes = [process(row['State']['Pid']) for row in actual if row['State']['Running']]
    domains = set()
    for entry in processes:
        group = (Path('/proc')/str(entry['pid'])/'cgroup').read_text().strip().split('::',1)[1]
        domains.add('/sys/fs/cgroup'+group)
    domains.add('/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/docker.service')
    domain_rows=[]
    for value in sorted(domains):
        path=Path(value);info=path.stat()
        domain_rows.append(dict(path=value,device=info.st_dev,inode=info.st_ino,boot_id=boot,
            uid=info.st_uid,mode=info.st_mode&0o777))
    assert_no_foreign_jobs(domain_rows)
    # Discover existing interpreters without scanning Docker stores or secrets.
    candidates=[]
    for base in [Path('/srv/mldsafail/current'),*Path.home().iterdir()]:
        if base.name in ('.local','.cache','.ssh','.config') or not base.is_dir():
            continue
        candidates.extend([base/'.venv/bin/python',base/'venv/bin/python',base/'bin/python'])
    valid=[]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            probe = command([str(path),'-B','-c',
                "import platform,sqlalchemy,psycopg,flask; print(platform.python_version())"],ceiling=10).decode().strip()
        except RuntimeError:
            continue
        if probe == '3.12.10':
            with path.open('rb') as stream: identity=hashlib.file_digest(stream,'sha256').hexdigest()
            valid.append(dict(path=str(path),sha256=identity,version=probe))
    containers=[dict(Id=row['Id'],Image=row['Image'],Name=row['Name'],
        State={key:row['State'][key] for key in ('Running','Pid','StartedAt')}) for row in actual]
    return dict(passed=True,source_sha256=expected['bootstrap_source_sha256'],
        elapsed_seconds=time.monotonic()-started,boot_id=boot,
        host_machine_id_sha256=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest(),
        protected_containers=containers,protected_processes=processes,protected_domains=domain_rows,
        protected_coordinator=coordinator['Id'],interpreters=valid,disk_available_bytes=free,
        memory_available_bytes=memory,current_release=expected['current_release'],
        new_generations=0,new_private_epochs=0,delivery=False,spending_usd=0,
        probe_process=process(os.getpid()))


def assert_no_foreign_jobs(protected_domains, *, operator_parent=None, proc_root=Path('/proc')):
    """Reject unaccounted user research/build/maintenance processes, no argv logs."""
    allowed = [Path(row['path']) for row in protected_domains]
    if operator_parent is not None:
        allowed.append(Path(operator_parent))
    tools = {'uv','make','cmake','ninja','gcc','clang','rustc','cargo','docker','dockerd','rootlesskit','dockerd-rootless.sh'}
    for root in Path(proc_root).iterdir():
        if not root.name.isdigit() or int(root.name)==os.getpid():
            continue
        try:
            if root.stat().st_uid != os.getuid():
                continue
            command = (root/'cmdline').read_bytes().split(b'\0')
            executable = Path(os.fsdecode(command[0])).name if command and command[0] else ''
            if not (executable.startswith('python') or executable in tools):
                continue
            group = (root/'cgroup').read_text().strip().split('::',1)[1]
            domain = Path('/sys/fs/cgroup')/group.lstrip('/')
            if not any(domain.is_relative_to(value) for value in allowed):
                raise RuntimeError('Unreconciled user research, build or maintenance process: '+root.name)
        except (FileNotFoundError, ProcessLookupError):
            continue  # This birth already ended; never infer identity from PID reuse.
