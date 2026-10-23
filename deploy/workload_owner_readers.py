"""Fixed supplemental host readers for a separately reviewed successor collector.

Private observations only. No utility installation, container mutation, cgroup
write, job execution or readiness certification. Paths are frozen at build time.
"""
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import tempfile
import time

from deploy.privileged_scheduling import identity, inspect_path

LIMIT = 262144
MAX_CONTAINERS = 128

# This program executes as the runtime user, never as root. os.access therefore
# measures that user's permissions. It only reads the existing manager ancestry.
CGROUP_READER = r'''
import json,os,pathlib,stat
assert os.getuid()==int(__import__('sys').argv[1]) and os.getuid()>0
root=pathlib.Path('/sys/fs/cgroup')
manager=root/('user.slice/user-%s.slice/user@%s.service'%(os.getuid(),os.getuid()))
limits=('memory.max','memory.high','memory.swap.max','pids.max','cpu.max','cpuset.cpus.effective')
def identity(path):
    s=path.lstat();assert not stat.S_ISLNK(s.st_mode)
    return dict(device=s.st_dev,inode=s.st_ino,uid=s.st_uid,gid=s.st_gid,mode=s.st_mode)
def sample():
    rows=[]
    for path in (manager,*manager.parents):
        if not path.is_relative_to(root):break
        traversal={str(p):identity(p) for p in (path,*path.parents)}
        permissions={}
        for name in ('cgroup.procs','cgroup.subtree_control'):
            item=path/name;before=identity(item);assert stat.S_ISREG(before['mode'])
            permissions[name]=dict(before,writable=os.access(item,os.W_OK))
            assert before==identity(item)
        row=dict(path=str(path),identity=identity(path),traversal=traversal,
            writable=os.access(path,os.W_OK),permissions=permissions,
            controllers=(path/'cgroup.controllers').read_text().split(),
            subtree_control=(path/'cgroup.subtree_control').read_text().split(),
            limits={name:(path/name).read_text().strip() if (path/name).exists() else None for name in limits})
        assert traversal=={str(p):identity(p) for p in (path,*path.parents)}
        rows.append(row)
    assert rows and rows[-1]['path']==str(root)
    return rows
before=sample();after=sample();assert before==after
print(json.dumps(dict(uid=os.getuid(),ancestors=before)))
'''


def validate_plan(plan):
    if (type(plan) is not dict or set(plan) != {'runtime_account', 'reviewed_paths', 'reviewed_sha256', 'output_paths'} or
            plan['runtime_account'] != 'mldsafail'):
        raise ValueError('fixed_reader_plan_required')
    for field, bound in (('reviewed_paths', 256), ('output_paths', 16)):
        values = plan[field]
        if (type(values) is not list or len(values) > bound or len(set(values)) != len(values) or
                any(type(value) is not str or not value.startswith('/') or '\x00' in value or
                    '..' in Path(value).parts or len(value) > 4096 for value in values)):
            raise ValueError('finite_absolute_reader_paths_required')
    hashes = plan['reviewed_sha256']
    if (type(hashes) is not dict or set(hashes) != set(plan['reviewed_paths']) or
            any(type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value)
                for value in hashes.values())):
        raise ValueError('reviewed_script_hash_bindings_required')
    return plan


def observe_command(argv, *, seconds):
    """Reuse the reviewed Linux subreaper, retaining uncertain cleanup evidence."""
    import resource
    import shutil
    import signal
    import sys
    directory = Path(tempfile.mkdtemp(prefix='mldsafail-owner-reader-command-'))
    report = directory/'report.json'
    def bounded():
        resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))
    process = None
    try:
        with (directory/'stdout').open('xb') as out, (directory/'stderr').open('xb') as err:
            process = subprocess.Popen([sys.executable, '-I', '-B',
                str(Path(__file__).with_name('workload_observation.py')), str(report),
                str(seconds), *argv], stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                start_new_session=True, preexec_fn=bounded)
            try:
                process.wait(timeout=seconds+2)
            finally:
                if process.poll() is None:
                    # The unreaped child PID cannot be reused. Group termination
                    # is owned, but escaped descendants still block certification.
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=.5)
        raw, stderr = (directory/'stdout').read_bytes(), (directory/'stderr').read_bytes()
        result = json.loads(report.read_bytes()) if report.is_file() else None
        births = report.with_name(report.name+'.births.jsonl')
        progress = births.read_text() if births.is_file() else ''
        group_present = True
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            group_present = False
        valid = (process.returncode == 0 and result is not None and not group_present and
                 not result.get('remaining') and not result.get('errors') and
                 not result.get('descendants') and not result.get('timed_out'))
        receipt = dict(wrapper_pid=process.pid, report=result, births_jsonl=progress,
                       group_present=group_present, verified=bool(valid))
        if not valid:
            # Keep compact raw failure and births before removing any fixture.
            receipt['retained_evidence'] = str(directory)
        else:
            shutil.rmtree(directory)
        return dict(returncode=result.get('returncode') if result else None,
                    stdout=raw, stderr=stderr, containment=receipt)
    except BaseException as error:
        # The enclosing collector records this private path. No uncertain
        # descendants or their evidence are silently discarded on an alarm.
        raise RuntimeError('reader_cleanup_unverified:'+str(directory)) from error


def scheduling_command(argv, *, timeout):
    import shutil
    if shutil.which(argv[0]) is None:
        raise FileNotFoundError(argv[0])
    if timeout <= 3:
        raise ValueError('collection_cleanup_reserve')
    return observe_command(argv, seconds=min(8, timeout-3))


def collect(plan, *, seconds=90):
    validate_plan(plan)
    if os.getuid() != 0:
        raise ValueError('owner_root_console_required')
    deadline = time.monotonic() + seconds
    observations = {}
    exported_bytes = 0

    def run(name, argv):
        nonlocal exported_bytes
        if exported_bytes >= 6*1024**2:
            observations[name] = dict(error='aggregate_output_bound')
            return None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            observations[name] = dict(error='collection_deadline')
            return None
        try:
            if remaining <= 3:
                observations[name] = dict(error='collection_cleanup_reserve')
                return None
            process = observe_command(argv, seconds=min(8, remaining-3))
            stdout, stderr = process['stdout'], process['stderr']
            exported_bytes += len(stdout) + len(stderr)
            row = dict(argv=argv, returncode=process['returncode'], containment=process['containment'],
                       stdout_hex=stdout.hex(), stderr_hex=stderr.hex(),
                       truncated=max(len(stdout), len(stderr)) >= LIMIT)
            observations[name] = row
            return stdout if process['returncode'] == 0 and row['containment']['verified'] and not row['truncated'] else None
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            observations[name] = dict(argv=argv, error=type(error).__name__, detail=str(error))
            return None

    account = pwd.getpwnam(plan['runtime_account'])
    if account.pw_uid <= 0:
        raise ValueError('runtime_nonroot_account_required')
    run('runtime_cgroups', ['/usr/sbin/runuser', '-u', account.pw_name, '--',
        '/usr/bin/python3', '-I', '-B', '-c', CGROUP_READER, str(account.pw_uid)])
    run('mounts', ['/usr/bin/findmnt', '--json', '-o', 'TARGET,SOURCE,FSTYPE,OPTIONS,SIZE,AVAIL,MAJ:MIN'])
    files = []
    file_bytes = 0
    for name in plan['reviewed_paths']:
        if file_bytes >= 6*1024**2:
            files.append(dict(path=name, error='aggregate_file_bound')); break
        if time.monotonic() >= deadline:
            files.append(dict(path=name, error='collection_deadline')); break
        row = inspect_path(name)
        if row.get('sha256') != plan['reviewed_sha256'][name] or 'error' in row:
            # Never return bytes or hashes of a substituted root-readable target.
            files.append(dict(path=name, error='reviewed_file_identity_or_content_changed'))
            continue
        if row.get('sha256') and 'error' not in row:
            # Read only the already resolved regular file, then bind the bytes
            # and a repeated complete traversal. Failed/raced reads stay blocked.
            try:
                import hashlib
                target = Path(row['final_target'])
                with target.open('rb') as stream:
                    before = identity(os.fstat(stream.fileno()))
                    data = stream.read(1048577)
                    if (len(data) > 1048576 or before != identity(os.fstat(stream.fileno())) or
                            before != row['identity'] or hashlib.sha256(data).hexdigest() != row['sha256'] or
                            inspect_path(name) != row):
                        raise ValueError('reviewed_path_changed')
                file_bytes += len(data)
                if file_bytes > 6*1024**2:
                    raise ValueError('aggregate_file_bound')
                row['contents_hex'] = data.hex()
            except (OSError, ValueError) as error:
                row['error'] = str(error) if isinstance(error, ValueError) else type(error).__name__
        files.append(row)
    storage = []
    for name in plan['output_paths']:
        row = inspect_path(name)
        original = dict(row)
        try:
            before = Path(name).stat(); usage = os.statvfs(name)
            row.update(available_bytes=usage.f_bavail * usage.f_frsize,
                       total_bytes=usage.f_blocks * usage.f_frsize)
            if identity(before) != identity(Path(name).stat()) or inspect_path(name) != original:
                raise ValueError('storage_changed')
        except (OSError, ValueError) as error:
            row['error'] = type(error).__name__
        storage.append(row)
    # Discover standard owner endpoints only. Nonstandard endpoints remain a
    # separate classification blocker; absence here never proves daemon closure.
    accounts = pwd.getpwall()
    if len(accounts) > 128:
        raise ValueError('account_inventory_limit')
    clients = []
    with tempfile.TemporaryDirectory(prefix='mldsafail-readonly-docker-') as config:
        os.chmod(config, 0o755)  # empty, credential-free client configuration
        for owner in accounts:
            paths = ['/run/docker.sock'] if owner.pw_uid == 0 else [f'/run/user/{owner.pw_uid}/docker.sock']
            for endpoint in paths:
                path = Path(endpoint)
                try:
                    info = path.lstat()
                    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != owner.pw_uid:
                        clients.append(dict(account=owner.pw_name, path=endpoint, error='socket_owner_or_kind')); continue
                except FileNotFoundError:
                    continue
                prefix = ['/usr/sbin/runuser', '-u', owner.pw_name, '--', '/usr/bin/docker',
                          '--config', config, '--host', 'unix://' + endpoint]
                key = 'docker_' + str(owner.pw_uid)
                data = run(key + '_containers', prefix + ['ps', '-a', '--no-trunc', '--format', '{{.ID}}'])
                run(key + '_daemon', prefix + ['info', '--format', '{{json .ID}} {{json .SecurityOptions}} {{json .CgroupDriver}} {{json .CgroupVersion}}'])
                if data is not None:
                    identifiers = data.decode('ascii').splitlines()
                    if len(identifiers) > MAX_CONTAINERS or any(not re.fullmatch('[0-9a-f]{64}', value) for value in identifiers):
                        observations[key + '_identifiers'] = dict(error='container_inventory_limit_or_identity')
                    else:
                        for identifier in identifiers:
                            run(key + '_' + identifier, prefix + ['inspect', '--format',
                                '{{json .Id}} {{json .Image}} {{json .State.Pid}} {{json .State.StartedAt}} {{json .State.Running}} {{json .HostConfig.RestartPolicy}} {{json .Config.User}} {{json .HostConfig.CgroupParent}}', identifier])
                clients.append(dict(account=owner.pw_name, uid=owner.pw_uid, path=endpoint, identity=identity(info)))
                try:
                    if identity(info) != identity(path.lstat()):
                        observations[key + '_identity'] = dict(error='daemon_socket_changed')
                except OSError:
                    observations[key + '_identity'] = dict(error='daemon_socket_changed')
    if Path('/usr/bin/atq').is_file():
        queue = run('at_queue', ['/usr/bin/atq'])
    else:
        observations['at_queue'] = dict(absent=True, owner_absence_requires_scheduling_corroboration=True)
        queue = None
    if queue is not None:
        jobs = [line.split()[0] for line in queue.decode(errors='replace').splitlines() if line.split()]
        if len(jobs) > 128 or any(not value.isdecimal() for value in jobs):
            observations['at_jobs'] = dict(error='at_job_inventory_limit_or_identity')
        else:
            for job in jobs:
                run('at_job_' + job, ['/usr/bin/at', '-c', job])
    # Only PID identities and UID/GID maps; never process environments or argv.
    data = run('daemon_processes', ['/usr/bin/ps', '-eo', 'pid=,uid=,comm='])
    mappings = []
    if data is not None:
        for line in data.decode(errors='replace').splitlines():
            fields = line.split()
            if len(fields) != 3 or fields[2] not in ('dockerd', 'rootlesskit'):
                continue
            pid, uid, comm = fields
            if not pid.isdecimal() or not uid.isdecimal():
                observations['daemon_process_identity'] = dict(error='invalid_pid'); continue
            process = Path('/proc')/pid
            try:
                def birth():
                    raw = (process/'stat').read_text()
                    return dict(pid=int(pid), start_ticks=int(raw[raw.rfind(')')+2:].split()[19]), uid=process.stat().st_uid)
                before = birth()
                row = dict(process=before, command=comm,
                    uid_map=(process/'uid_map').read_text(), gid_map=(process/'gid_map').read_text(),
                    cgroup=(process/'cgroup').read_text())
                if birth() != before or before['uid'] != int(uid):
                    raise ValueError('daemon_process_changed')
                mappings.append(row)
            except (OSError, ValueError) as error:
                mappings.append(dict(pid=int(pid), error=type(error).__name__))
    complete = (time.monotonic() < deadline and
        all(not row.get('error') and not row.get('truncated') and
            (row.get('absent') is True or row.get('returncode') == 0 and
             row.get('containment', {}).get('verified') is True) for row in observations.values()) and
        all('error' not in row for row in [*files, *storage, *clients, *mappings]))
    return dict(schema='mldsafail.owner-supplemental-observation.v1', plan=plan, complete=complete,
        observations=observations, reviewed_files=files, output_backing=storage,
        daemon_clients=clients, daemon_mappings=mappings, readiness=False, execution_authority=False,
        unresolved=['recursive_reference_classification', 'nonstandard_daemon_endpoints',
                    'at_job_contents_if_present', 'coordinator_image_uid_mapping_join',
                    'retained_service_ancestry_join', 'output_preservation_review'])
