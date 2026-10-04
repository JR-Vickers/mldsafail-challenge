"""Dedicated rootless-daemon identities and kernel-proven uncertainty fencing.

No default daemon is eligible. Only explicit private manifests for dedicated
mldsafail-owned-daemon/mldsafail-cpu-daemon units may be controlled.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid
from deploy import owned_client

SCHEMA='mldsafail.owned-daemon.v1'


def publish(path, value):
    path=Path(path)
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex)
    try:
        with temporary.open('x') as stream:
            os.fchmod(stream.fileno(),0o600)
            json.dump(value,stream,sort_keys=True,allow_nan=False)
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        descriptor=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    finally:
        if temporary.exists(): temporary.unlink()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _canonical(path):
    path=Path(path)
    if not path.is_absolute() or any(part.is_symlink() for part in (path,*path.parents)):
        raise RuntimeError('Canonical absolute owned path required')
    return path


def _private_directory(path):
    path=_canonical(path)
    info=path.stat()
    if not path.is_dir() or info.st_uid!=os.getuid() or info.st_mode & 0o077:
        raise RuntimeError('Private owner directory required')
    return dict(path=str(path),device=info.st_dev,inode=info.st_ino,uid=info.st_uid,mode=info.st_mode&0o777)



def provision(base, *, unit, protected_roots):
    """Fresh private roots only; pre-existing daemon/evaluator roots are ineligible."""
    base=_canonical(base)
    _private_directory(base.parent)
    if not protected_roots:
        raise RuntimeError('Explicit protected staging/deployment roots required')
    protected=[_canonical(path) for path in protected_roots]
    protected.extend([Path.home()/'.local/share/docker',Path('/srv/mldsafail'),Path('/srv/mldsafail-evaluator')])
    if any(base==path or base in path.parents or path in base.parents for path in protected):
        raise RuntimeError('Dedicated daemon roots overlap protected infrastructure')
    if not re.fullmatch('mldsafail-(?:owned|cpu)-daemon-[a-z0-9-]+\\.service',unit):
        raise RuntimeError('Dedicated daemon unit required')
    base.mkdir(mode=0o700)  # Existing roots, including prior failed provision, are never reused.
    roots={}
    for name in ('root_dir','exec_root','rootless_state'):
        directory=base/name
        directory.mkdir(mode=0o700)
        roots[name]=_private_directory(directory)
    receipt=dict(schema='mldsafail.owned-daemon-provision.v1',id=uuid.uuid4().hex,
                 unit=unit,base=_private_directory(base),roots=roots,
                 protected_roots=[str(path) for path in protected],boot_id=owned_client.boot_id())
    publish(base/'provision.json',receipt)
    return receipt


def bind_worker(provisioning, *, worker_parent, worker_cgroup_parent, operator_parent, protected_domains):
    """Durably bind a fresh empty nonce-named parent before daemon mutations."""
    expected='mldsafail-'+provisioning['unit'].split('-')[1]+'-workers-'+provisioning['id']+'.slice'
    if worker_cgroup_parent!=expected or Path(worker_parent).name!=expected:
        raise RuntimeError('Fresh nonce-named dedicated worker slice required')
    if 'worker_birth' in provisioning: raise RuntimeError('Worker birth already bound')
    paths=[_canonical(worker_parent),_canonical(operator_parent)]
    protected=[_canonical(path) for path in protected_domains]
    _disjoint(paths,protected)
    for path in paths: owned_client.prepare_domain({'id':uuid.uuid4().hex},path)
    if owned_client.populated(paths[0]): raise RuntimeError('Fresh worker parent must be empty')
    receipt=dict(provisioning,worker_birth=owned_client.domain_identity(paths[0]),operator_domain=owned_client.domain_identity(paths[1]),worker_cgroup_parent=expected,protected_domains=[str(path) for path in protected])
    publish(Path(provisioning['base']['path'])/'provision.json',receipt)
    return receipt


def _disjoint(paths,protected):
    if any(a==b or a in b.parents or b in a.parents for index,a in enumerate(paths) for b in paths[index+1:]) or any(a==b or a in b.parents or b in a.parents for a in paths for b in protected):
        raise RuntimeError('Daemon/operator/worker/protected domains must be disjoint')


def _worker_binding(provisioning,worker_domain,worker_cgroup_parent,daemon_domain=None):
    expected='mldsafail-'+provisioning['unit'].split('-')[1]+'-workers-'+provisioning['id']+'.slice'
    if worker_cgroup_parent!=expected or Path(worker_domain['path']).name!=expected or provisioning.get('worker_birth')!=worker_domain:
        raise RuntimeError('Fresh dedicated worker birth identity required')
    operator=provisioning.get('operator_domain')
    if not operator or owned_client.domain_identity(operator['path'])!=operator or os.environ.get('MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT')!=operator['path']:
        raise RuntimeError('Exact provisioned operator domain required')
    paths=[Path(worker_domain['path']),Path(operator['path'])]
    if daemon_domain is not None: paths.append(Path(daemon_domain['path']))
    _disjoint(paths,[Path(path) for path in provisioning['protected_domains']])


def _provisioning(value, unit, roots):
    if not isinstance(value,dict) or value.get('schema')!='mldsafail.owned-daemon-provision.v1' or value.get('unit')!=unit:
        raise RuntimeError('Fresh dedicated daemon provisioning receipt required')
    base=value['base']
    if _private_directory(base['path'])!=base:
        raise RuntimeError('Fresh daemon base directory identity changed')
    for name,root in roots.items():
        if Path(root['path'])!=Path(base['path'])/name or value['roots'][name]['path']!=root['path'] or (name in {'root_dir','exec_root'} and value['roots'][name]!=root):
            raise RuntimeError('Daemon roots differ from fresh provisioning')
    for protected in value['protected_roots']:
        path=Path(protected); owned=Path(base['path'])
        if path==owned or path in owned.parents or owned in path.parents:
            raise RuntimeError('Dedicated roots overlap protected infrastructure')
    return value


def _unit(unit):
    if not isinstance(unit,str) or not re.fullmatch('mldsafail-(?:owned|cpu)-daemon-[a-z0-9-]+\\.service',unit):
        raise RuntimeError('Explicit dedicated daemon unit required')
    values=subprocess.check_output(['systemctl','--user','show',unit,'--property=MainPID',
        '--property=ControlGroup','--property=Restart','--property=KillMode','--property=Delegate',
        '--property=FragmentPath','--property=ActiveState'],timeout=15,text=True)
    state=dict(line.split('=',1) for line in values.splitlines() if '=' in line)
    if state.get('Restart')!='no' or state.get('KillMode')!='control-group' or state.get('Delegate')!='yes':
        raise RuntimeError('Dedicated unit requires Restart=no/KillMode=control-group/Delegate=yes')
    fragment=_canonical(state['FragmentPath'])
    if fragment.stat().st_uid!=os.getuid() or fragment.stat().st_mode & 0o022:
        raise RuntimeError('Dedicated unit fragment must be owner controlled')
    state['unit_fragment_sha256']=hashlib.sha256(fragment.read_bytes()).hexdigest()
    if state.get('ActiveState')=='active':
        domain=Path('/sys/fs/cgroup')/state['ControlGroup'].lstrip('/')
        if domain.name!=unit:
            raise RuntimeError('Dedicated unit must own its own exact cgroup')
        state['domain_path']=str(domain)
    return state


def _hash_executable(pid):
    with (Path('/proc')/str(pid)/'exe').open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def _daemon_process(domain, expected_sha256):
    matches=[]
    for file in Path(domain).rglob('cgroup.procs'):
        for pid in file.read_text().split():
            try:
                if _hash_executable(int(pid))==expected_sha256:
                    matches.append(owned_client.identity(int(pid)))
            except (FileNotFoundError,ProcessLookupError): pass
    if len(matches)!=1:
        raise RuntimeError('Exactly one dedicated digest-bound dockerd process required')
    return matches[0]


def _endpoint(socket):
    path=_canonical(socket)
    _private_directory(path.parent)
    import stat
    info=path.stat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=os.getuid():
        raise RuntimeError('Dedicated owner Unix socket required')
    if os.environ.get('DOCKER_HOST')!='unix://'+str(path) or os.environ.get('DOCKER_CONTEXT'):
        raise RuntimeError('Explicit isolated Docker endpoint required; contexts forbidden')


def register(*, unit, socket, root_dir, exec_root, rootless_state, manifest_path,
             expected_server_version, expected_server_git_commit, expected_executable_sha256,
             worker_parent, worker_cgroup_parent, provisioning):
    """Register already provisioned/started dedicated native services explicitly."""
    if not re.fullmatch('[0-9a-f]{64}',expected_executable_sha256):
        raise RuntimeError('Expected native dockerd executable SHA256 required')
    roots={name:_private_directory(value) for name,value in
           [('root_dir',root_dir),('exec_root',exec_root),('rootless_state',rootless_state)]}
    _provisioning(provisioning,unit,roots)
    if len({entry['path'] for entry in roots.values()})!=3:
        raise RuntimeError('Distinct dedicated daemon roots required')
    owned_client.prepare_domain({'id':uuid.uuid4().hex},worker_parent)  # Native fs/type/access proof, no mutation.
    worker_domain=owned_client.domain_identity(worker_parent)
    if worker_domain['uid']!=os.getuid() or worker_domain['mode'] & 0o022 or (Path(worker_parent)/'cgroup.type').read_text().strip()!='domain':
        raise RuntimeError('Exclusive owned worker domain required')
    _worker_binding(provisioning,worker_domain,worker_cgroup_parent)
    _endpoint(socket)
    state=_unit(unit)
    if state['ActiveState']!='active': raise RuntimeError('Dedicated daemon unit is not active')
    domain=owned_client.domain_identity(state['domain_path'])
    _worker_binding(provisioning,worker_domain,worker_cgroup_parent,domain)
    daemon_process=_daemon_process(domain['path'],expected_executable_sha256)
    argv=(Path('/proc')/str(daemon_process['pid'])/'cmdline').read_bytes().split(b'\0')
    arguments=[os.fsdecode(value) for value in argv if value]
    for option,value in [('data-root',root_dir),('exec-root',exec_root),('host','unix://'+str(socket)),('live-restore','false'),('cgroup-parent',worker_cgroup_parent)]:
        values=[]
        for index,arg in enumerate(arguments):
            if arg=='--'+option and index+1<len(arguments): values.append(arguments[index+1])
            elif arg.startswith('--'+option+'='): values.append(arg.split('=',1)[1])
        if values != [str(value)]: raise RuntimeError('Explicit isolated daemon argument mismatch: '+option)
    leader=owned_client.identity(int(state['MainPID']))
    leader_environment=(Path('/proc')/str(leader['pid'])/'environ').read_bytes().split(b'\0')
    expected_env=os.fsencode('DOCKERD_ROOTLESS_ROOTLESSKIT_STATE_DIR='+str(rootless_state))
    if expected_env not in leader_environment:
        raise RuntimeError('Explicit isolated rootlesskit state required')
    info=json.loads(subprocess.check_output(['docker','info','--format','{{json .}}'],timeout=30))
    version=json.loads(subprocess.check_output(['docker','version','--format','{{json .Server}}'],timeout=30))
    if info.get('DockerRootDir')!=str(root_dir) or info.get('ServerVersion')!=expected_server_version or version.get('GitCommit')!=expected_server_git_commit:
        raise RuntimeError('Dedicated daemon root/version/build mismatch')
    if info.get('LiveRestoreEnabled') is not False or str(info.get('CgroupVersion'))!='2' or info.get('CgroupDriver')!='systemd' or not any('rootless' in option for option in info.get('SecurityOptions',[])):
        raise RuntimeError('Rootless cgroup-v2 daemon with live restore disabled required')
    manifest=dict(schema=SCHEMA,epoch=uuid.uuid4().hex,unit=unit,socket=str(socket),
                  roots=roots,domain=domain,leader=leader,daemon_process=daemon_process,
                  worker_domain=worker_domain,worker_cgroup_parent=worker_cgroup_parent,provisioning=provisioning,
                  server_version=expected_server_version,server_git_commit=expected_server_git_commit,
                  daemon_executable_sha256=expected_executable_sha256,
                  unit_fragment_sha256=state['unit_fragment_sha256'])
    publish(_canonical(manifest_path),manifest)
    return manifest


def load_manifest(path=None):
    aliases=[value for value in (os.environ.get('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST'),os.environ.get('MLDSAFAIL_CPU_DAEMON_MANIFEST')) if value]
    if path is None:
        if not aliases or len(set(aliases))!=1:
            raise RuntimeError('One explicit dedicated-daemon manifest required')
        path=aliases[0]
    path=_canonical(path)
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(descriptor,'rb') as stream:
        info=os.fstat(stream.fileno())
        if info.st_uid!=os.getuid() or info.st_mode & 0o077:
            raise RuntimeError('Private owner daemon manifest required')
        raw=stream.read(65537)
    if len(raw)>65536: raise RuntimeError('Daemon manifest exceeds cap')
    manifest=json.loads(raw)
    required={'schema','epoch','unit','socket','roots','domain','leader','daemon_process',
              'server_version','server_git_commit','daemon_executable_sha256','unit_fragment_sha256',
              'worker_domain','worker_cgroup_parent','provisioning'}
    if set(manifest)!=required or manifest['schema']!=SCHEMA or not re.fullmatch('[0-9a-f]{32}',manifest['epoch']):
        raise RuntimeError('Exact versioned daemon epoch manifest required')
    return manifest


def verify_environment(manifest, *, measurement_parent=None, docker_info=None):
    _endpoint(manifest['socket'])
    state=_unit(manifest['unit'])
    if state['ActiveState']!='active' or int(state['MainPID'])!=manifest['leader']['pid'] or state['domain_path']!=manifest['domain']['path'] or state['unit_fragment_sha256']!=manifest['unit_fragment_sha256']:
        raise RuntimeError('Dedicated daemon unit identity changed')
    if owned_client.domain_identity(manifest['domain']['path'])!=manifest['domain'] or owned_client.identity(manifest['leader']['pid'])!=manifest['leader'] or owned_client.identity(manifest['daemon_process']['pid'])!=manifest['daemon_process']:
        raise RuntimeError('Dedicated daemon kernel process/domain identity changed')
    if _hash_executable(manifest['daemon_process']['pid'])!=manifest['daemon_executable_sha256']:
        raise RuntimeError('Dedicated daemon executable identity changed')
    _provisioning(manifest['provisioning'],manifest['unit'],manifest['roots'])
    _worker_binding(manifest['provisioning'],manifest['worker_domain'],manifest['worker_cgroup_parent'],manifest['domain'])
    for name,value in manifest['roots'].items():
        if _private_directory(value['path'])!=value: raise RuntimeError('Dedicated daemon root identity changed')
    owned_client.prepare_domain({'id':uuid.uuid4().hex},manifest['worker_domain']['path'])
    if owned_client.domain_identity(manifest['worker_domain']['path'])!=manifest['worker_domain']:
        raise RuntimeError('Entire owned worker parent identity changed')
    if measurement_parent is not None and str(measurement_parent)!=manifest['worker_domain']['path']:
        raise RuntimeError('Accounting parent differs from dedicated daemon worker parent')
    domains=[Path(manifest['domain']['path']),Path(manifest['worker_domain']['path'])]
    operator=os.environ.get('MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT')
    if operator: domains.append(_canonical(operator))
    if measurement_parent is not None: _canonical(measurement_parent)
    if any(a==b or a in b.parents or b in a.parents for index,a in enumerate(domains) for b in domains[index+1:]):
        raise RuntimeError('Daemon/operator/worker domains must be separate')
    if docker_info is not None:
        if docker_info.get('DockerRootDir')!=manifest['roots']['root_dir']['path'] or docker_info.get('ServerVersion')!=manifest['server_version'] or docker_info.get('LiveRestoreEnabled') is not False:
            raise RuntimeError('Dedicated Docker API identity mismatch')
    return manifest


def shutdown_barrier(manifest, *, worker_domains=(), evidence_directory, attempt_id):
    """Kernel shutdown of exact old epoch; all steps independent, never fallback."""
    if not re.fullmatch('[a-zA-Z0-9_-]{1,128}',attempt_id): raise ValueError('Safe attempt identity required')
    errors=[]
    control_safe=False
    try:
        if fingerprint(load_manifest())!=fingerprint(manifest):
            raise RuntimeError('Current dedicated manifest authority differs from old epoch')
        state=_unit(manifest['unit'])
        if state['unit_fragment_sha256']!=manifest['unit_fragment_sha256']:
            raise RuntimeError('Dedicated unit config changed; control prohibited')
        if state['ActiveState']=='active':
            if int(state['MainPID'])!=manifest['leader']['pid'] or state['domain_path']!=manifest['domain']['path'] or owned_client.identity(manifest['leader']['pid'])!=manifest['leader']:
                raise RuntimeError('Dedicated unit epoch changed; control prohibited')
            control_safe=True
            subprocess.run(['systemctl','--user','stop',manifest['unit']],check=True,timeout=45,capture_output=True)
        elif state['ActiveState'] not in {'inactive','failed'}:
            raise RuntimeError('Dedicated unit state is not reconciled')
        else:
            control_safe=True
    except BaseException as error: errors.append(dict(step='dedicated_unit_stop',error=repr(error)))
    try:
        if not control_safe: raise RuntimeError('Daemon control identity was not proved')
        owned_client.stop({'cgroup':manifest['domain']})
    except BaseException as error: errors.append(dict(step='dedicated_daemon_domain_stop',error=repr(error)))
    if any(domain!=manifest['worker_domain'] for domain in worker_domains):
        errors.append(dict(step='worker_domain_identity',error='Caller worker receipt differs from entire registered parent'))
    # All late/unacknowledged containers are confined by daemon default parent
    # and explicit operator overrides, so the complete parent is mandatory.
    for domain in [manifest['worker_domain']]:
        try:
            if not control_safe: raise RuntimeError('Old daemon epoch authority not proved; worker control prohibited')
            path=owned_client.verify_domain({'cgroup':domain})
            if path is not None:
                (path/'cgroup.kill').write_text('1')
                deadline=time.monotonic()+15
                while owned_client.populated(path):
                    if time.monotonic()>deadline: raise RuntimeError('Owned worker domain remains populated')
                    time.sleep(.05)
                owned_client.verify_domain({'cgroup':domain})
        except BaseException as error: errors.append(dict(step='dedicated_worker_domain_stop',error=repr(error)))
    receipt=dict(schema='mldsafail.owned-daemon-barrier.v1',attempt_id=attempt_id,
                 daemon_epoch=manifest['epoch'],daemon_manifest_sha256=fingerprint(manifest),
                 shutdown_proven=not errors,errors=errors,restart_required=True)
    name=attempt_id+'-daemon-barrier-'+uuid.uuid4().hex+'.json'
    publish(Path(evidence_directory)/name,receipt)
    receipt['receipt_file']=name
    return receipt


def restart_and_refresh(manifest, shutdown_receipt, *, manifest_path, client_entries=(), evidence_directory, attempt_id):
    """Only after positive old-epoch proof and independently empty client domains."""
    if shutdown_receipt.get('shutdown_proven') is not True or shutdown_receipt.get('daemon_manifest_sha256')!=fingerprint(manifest) or shutdown_receipt.get('daemon_epoch')!=manifest['epoch']:
        raise RuntimeError('Positive exact daemon shutdown receipt required')
    for entry in client_entries:
        path=owned_client.verify_domain(entry)
        if path is not None and owned_client.populated(path): raise RuntimeError('Owned client survives barrier')
    state=_unit(manifest['unit'])
    intent_path=Path(evidence_directory)/(attempt_id+'-daemon-restart-intent.json')
    prior_intent=json.loads(intent_path.read_bytes()) if intent_path.exists() and not intent_path.is_symlink() and intent_path.stat().st_size<=65536 else None
    if state['unit_fragment_sha256']!=manifest['unit_fragment_sha256'] or (state['ActiveState'] not in {'inactive','failed'} and not (state['ActiveState']=='active' and prior_intent is not None and prior_intent.get('previous_epoch')==manifest['epoch'] and prior_intent.get('manifest_sha256')==fingerprint(manifest))):
        raise RuntimeError('Dedicated unit changed before restart')
    intent_path=Path(evidence_directory)/(attempt_id+'-daemon-restart-intent.json')
    previous_intent=None
    if intent_path.exists():
        if intent_path.is_symlink() or intent_path.stat().st_size>65536: raise RuntimeError('Invalid restart intent')
        previous_intent=json.loads(intent_path.read_bytes())
    intent=dict(schema='mldsafail.owned-daemon-restart-intent.v1',attempt_id=attempt_id,
                previous_epoch=manifest['epoch'],manifest_sha256=fingerprint(manifest),unit=manifest['unit'])
    if previous_intent is not None and previous_intent!=intent: raise RuntimeError('Restart intent identity mismatch')
    if previous_intent is None: publish(intent_path,intent)
    subprocess.run(['systemctl','--user','start',manifest['unit']],check=True,timeout=45,capture_output=True)
    deadline=time.monotonic()+45
    while True:
        try:
            refreshed=register(unit=manifest['unit'],socket=manifest['socket'],
                **{name:value['path'] for name,value in manifest['roots'].items()},manifest_path=manifest_path,
                expected_server_version=manifest['server_version'],expected_server_git_commit=manifest['server_git_commit'],
                expected_executable_sha256=manifest['daemon_executable_sha256'],
                worker_parent=manifest['worker_domain']['path'],worker_cgroup_parent=manifest['worker_cgroup_parent'],
                provisioning=manifest['provisioning'])
            break
        except (RuntimeError,subprocess.SubprocessError,FileNotFoundError):
            if time.monotonic()>deadline: raise
            time.sleep(.1)
    receipt=dict(schema='mldsafail.owned-daemon-restart.v1',attempt_id=attempt_id,
                 previous_epoch=manifest['epoch'],new_epoch=refreshed['epoch'],manifest_sha256=fingerprint(refreshed))
    publish(Path(evidence_directory)/(attempt_id+'-daemon-restart-'+uuid.uuid4().hex+'.json'),receipt)
    return refreshed
