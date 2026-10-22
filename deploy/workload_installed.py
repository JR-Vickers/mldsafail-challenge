"""Fresh Linux measurements for installed V3 controls; no synthetic promotion."""
import json
from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path
import subprocess

from deploy.workload_installation import identity,read_owned_file
from deploy.workload_release import digest, regular, verify
from mldsafail.evaluator.native_workload import require, values, process_birth


_RUNNER=ContextVar('workload_installed_observation_runner',default=None)

@contextmanager
def observation_runner(command):
    token=_RUNNER.set(command)
    try:yield
    finally:_RUNNER.reset(token)


def run(argv,*,timeout=8):
    injected=_RUNNER.get()
    if injected is not None:return injected(argv)
    import resource,signal,tempfile,sys
    require(type(timeout) in (int,float) and 0<timeout<=35,'installed_observation_budget_invalid')
    def bound_output():resource.setrlimit(resource.RLIMIT_FSIZE,(1024**2,1024**2))
    require(sys.platform=='linux','installed_observation_requires_linux')
    with tempfile.TemporaryDirectory() as directory,tempfile.TemporaryFile() as output,tempfile.TemporaryFile() as errors:
        report=Path(directory)/'report.json'
        wrapped=[sys.executable,'-I',str(Path(__file__).with_name('workload_observation.py')),str(report),str(timeout),*argv]
        process=subprocess.Popen(wrapped,stdout=output,stderr=errors,start_new_session=True,preexec_fn=bound_output)
        recorded=process_birth(process.pid);group_unverified=False;wrapper_timeout=False
        def evidence():
            result=json.loads(report.read_bytes()) if report.is_file() else None
            return json.dumps(dict(wrapper=recorded,report=result))
        try:
            process.wait(timeout=timeout+3)
        except subprocess.TimeoutExpired:wrapper_timeout=True
        finally:
            if process.poll() is None:
                require(process_birth(process.pid)==recorded,'installed_observation_client_replaced:'+evidence())
                os.killpg(process.pid,signal.SIGKILL)
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    require(False,'installed_observation_termination_unverified:'+evidence())
            # An exited leader is not proof that its process group is empty.
            # Do not signal a group after losing its live leader birth binding;
            # retain an explicit blocker for separately reviewed reconciliation.
            try:os.killpg(process.pid,0)
            except ProcessLookupError:pass
            else:group_unverified=True
        output.seek(0);errors.seek(0);raw=output.read(1024**2);stderr=errors.read(1024**2)
        require(len(raw)<1024**2 and len(stderr)<1024**2,'installed_observation_output_limit:'+evidence())
        require(not wrapper_timeout,'installed_observation_termination_unverified:'+evidence())
        require(not group_unverified,'installed_observation_descendants_unverified:'+evidence())
        require(process.returncode==0 and report.is_file(),'installed_observation_termination_unverified:'+evidence())
        result=json.loads(report.read_bytes())
        require(not result['remaining'] and not result.get('errors'),'installed_observation_termination_unverified:'+json.dumps(result))
        if result['timed_out']:raise subprocess.TimeoutExpired(argv,timeout,raw,stderr)
        require(not result['descendants'],'installed_observation_descendants_unverified:'+json.dumps(result))
        if result['returncode']:raise subprocess.CalledProcessError(result['returncode'],argv,raw,stderr)
        return raw


def mount(path):
    target=str(Path(path)); matches=[]
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left,right=line.split(' - ',1); fields=left.split(); extra=right.split()
        if fields[4]==target:
            matches.append(dict(mount_id=int(fields[0]),source_device=extra[1],filesystem=extra[0],
                mount_options=sorted(set(fields[5].split(','))|set(extra[2].split(',')))))
    require(len(matches)==1,'installed_output_mount_missing_or_ambiguous'); return matches[0]


def loop_backing(mounted,backing,command):
    """Inspect the kernel loop association, not a receipt or source filename."""
    import re
    require(re.fullmatch(r'/dev/loop[0-9]+',mounted['source_device']) is not None,
            'installed_output_loop_device_required')
    script=('import os,sys,stat,fcntl,struct,json; '
        'fd=os.open(sys.argv[1],os.O_RDONLY|os.O_NOFOLLOW);s=os.fstat(fd); '
        'assert stat.S_ISBLK(s.st_mode); '
        'v=struct.unpack("=QQQQQIIII64s64s32sQQ",fcntl.ioctl(fd,0x4C05,bytes(232))); '
        'print(json.dumps(dict(device=v[0],inode=v[1],offset=v[3],size_limit=v[4],rdev=s.st_rdev)))')
    actual=json.loads(command(['/usr/bin/sudo','-n','/usr/bin/python3','-c',script,mounted['source_device']]))
    require(actual['device']==backing['device'] and actual['inode']==backing['inode'] and
            actual['offset']==0 and actual['size_limit']==0,'installed_output_backing_changed')
    return actual


def verify_output_ownership(source,mounted,journal,command):
    output=source['resources']['output']
    require(journal is not None,'installed_output_ownership_journal_required')
    rows=[row for row in journal.rows if row['event']=='resource_created' and row.get('resource')=='output_active_mount']
    require(len(rows)==1,'installed_output_mount_ack_missing_or_ambiguous')
    row=rows[0];backing=identity(output['backing_file'],content=False)
    originals=[r['observed'] for r in journal.rows if r['event']=='resource_created' and r.get('resource')=='output_backing']
    require(originals==[backing],'installed_output_original_backing_changed')
    require(backing==row['backing'] and identity(output['path'])==row['directory'] and
            mounted==row['observed'],'installed_output_mount_ownership_changed')
    require(loop_backing(mounted,backing,command)==row['loop_backing'],'installed_output_loop_binding_changed')


def docker(source,args):
    return run(['/usr/bin/docker','--host','unix://'+source['host']['runtime_identity']['socket_birth']['path'],*args])


def retained(source):
    result={}
    for role,row in source['retained_services'].items():
        actual=json.loads(docker(source,['inspect',row['id']]))[0]
        result[role]=dict(id=actual['Id'],image=actual['Image'],started_at=actual['State']['StartedAt'],running=actual['State']['Running'])
    return result


def scheduling(proposal, *, include_containers=True):
    from deploy.workload_preparation import manager_prefix
    from deploy.workload_schedule_v3 import unit_name
    source=proposal['identities']; dropins={}
    for row in proposal['scheduling']['resources']:
        path=Path(row['path']); data,_=read_owned_file(path,run)
        require(data==row['contents'].encode(),'installed_scheduling_dropin_changed'); dropins[str(path)]=digest(data)
    for owner in source['scheduling']['owners'].values():
        if owner['disposition']=='pause':
            path=Path(source['permission_root'])/(owner['manager']+'-'+str(owner['uid'])+'.allow')
            require(identity(path)['state']=='absent','installed_computation_permission_present')
    for unit in source['scheduling']['computational_units']:
        owner=source['scheduling']['owners'][unit]
        active=run([*manager_prefix(owner,source['host']['uid']),'show',unit_name(unit,owner),'--property=ActiveState','--value']).strip()
        require(active in (b'inactive',b'failed'),'installed_computational_unit_active')
    for row in source['containers'] if include_containers else []:
        if row['disposition']=='pause':
            actual=json.loads(docker(source,['inspect',row['id']]))[0]
            require(actual['Id']==row['id'] and actual['State']['Running'] is False and
                    actual['HostConfig']['RestartPolicy']['Name']=='no','installed_container_restart_not_inhibited')
    return dict(permission_files_absent=True,computational_units_stopped=True,computational_containers_stopped=True if include_containers else None,
                restart_policies_inhibited=True if include_containers else None,dropin_hashes=dropins)


CGROUP_LIMITS=('memory.max','memory.high','memory.swap.max','pids.max','cpu.max','cpuset.cpus.effective')
CGROUP_PERMISSIONS=('cgroup.procs','cgroup.subtree_control')


def cgroup_observation(path):
    path=Path(path)
    row=identity(path)
    require(row['state']=='observed','installed_cgroup_missing')
    permissions={}
    for name in CGROUP_PERMISSIONS:
        target=path/name;info=target.lstat()
        require(not target.is_symlink(),'installed_cgroup_control_symlink')
        permissions[name]=dict(uid=info.st_uid,gid=info.st_gid,mode=info.st_mode&0o7777,
                               writable=os.access(target,os.W_OK))
    row.update(controllers=sorted((path/'cgroup.controllers').read_text().split()),
               subtree_control=sorted((path/'cgroup.subtree_control').read_text().split()),
               control_permissions=permissions,
               writable=os.access(path,os.W_OK),
               limits={name:(path/name).read_text().strip() if (path/name).exists() else None for name in CGROUP_LIMITS})
    require(identity(path)=={key:value for key,value in row.items() if key not in
            ('controllers','subtree_control','control_permissions','writable','limits')},'installed_cgroup_observation_race')
    return row


def verify_ancestor_observations(source):
    for parent in source['resources']['delegation']['ancestors']:
        if parent['state']!='observed':continue
        actual=cgroup_observation(parent['path'])
        require(all(actual[k]==parent[k] for k in ('device','inode','writable','limits','subtree_control','control_permissions')) and
                set(actual['controllers'])==set(parent['controllers']),'installed_cgroup_ancestor_changed')


def prerequisites(source,journal=None):
    output=source['resources']['output']; actual=mount(output['path'])
    require(actual['filesystem']==output['filesystem'] and
            set(actual['mount_options'])>={'noexec','nosuid','nodev'},'installed_mount_enforcement_changed')
    info=os.statvfs(output['path'])
    require(info.f_blocks*info.f_frsize<=output['bytes'],'installed_output_capacity_changed')
    if output['state']=='observed':
        require(all(identity(output['path'])[k]==output[k] for k in ('device','inode')) and
                actual['mount_id']==output['mount_id'],'installed_mount_birth_changed')
    else:verify_output_ownership(source,actual,journal,run)
    verify_ancestor_observations(source)
    delegation=source['resources']['delegation']; root=Path(delegation['path'])
    require(set((root/'cgroup.controllers').read_text().split())>={'cpu','memory','pids'} and
            set((root/'cgroup.subtree_control').read_text().split())>={'cpu','memory','pids'},'installed_controllers_missing')
    require((root/'memory.swap.max').read_text().strip()=='0' and
            (root/'pids.max').read_text().strip()=='448' and
            (root/'cpu.max').read_text().strip()=='100000 100000' and
            0<int((root/'memory.max').read_text().strip())<=source['installation']['memory_ceiling'],
            'installed_aggregate_limits_changed')
    for parent in delegation['ancestors']:
        actual_parent=identity(parent['path'])
        if parent['state']=='observed':
            require(all(actual_parent[k]==parent[k] for k in ('device','inode')),'installed_cgroup_ancestor_birth_changed')
        else:
            require(actual_parent['state']=='observed' and actual_parent['uid']==source['host']['uid'],
                    'installed_proposed_ancestor_not_owned')
    return dict(output=actual,delegation=identity(root))


def verify_images(source,manifest=None):
    from deploy.workload_images import installed
    manifest=source['manifest'] if manifest is None else manifest
    require('images' in manifest,'installed_image_archive_binding_missing')
    return installed(manifest['images'],lambda identifier:json.loads(docker(source,['image','inspect',identifier]))[0])


def verify_supervisor_enable(proposal):
    from deploy.workload_installation import Journal,private,supervisor_enable_contents
    source=proposal['identities'];raw,loaded=private(source['recipe']['proposal_path'])
    require(loaded==proposal,'installed_enable_proposal_changed')
    journal=Journal(source['recipe']['journal_root'],digest(raw))
    acknowledged=journal.outcome('install:enable_supervisor')
    path=Path(source['resources']['release']['path'])/'.supervisor-enabled'
    data,mode=regular(path.parent,path.name);actual=identity(path)
    require(acknowledged and acknowledged['event'] in ('outcome','reconciled') and
            actual==acknowledged['observed'] and actual['uid']==source['host']['uid'] and
            mode==0o600 and data==supervisor_enable_contents(proposal),'installed_supervisor_enable_changed')
    return actual


def activation_scheduling(proposal,*,installed_units=False,replacements=None,overrides=None,quiesced=()):
    """Fresh final closure, permitting only the reviewed inhibition transitions."""
    from deploy.workload_registry import observe,references,bound_files
    source=proposal['identities']
    observe(source,run,installed_units=installed_units)
    references(source,run,inhibited=True,overrides=overrides,quiesced=quiesced)
    bound_files(source,run,replacements=replacements)
    actual=original_settings(source)
    for unit,row in actual['manager_settings'].items():
        expected=dict(source['inventory']['manager_settings'][unit])
        if unit in source['scheduling']['computational_units']:
            require(row['ActiveState'] in ('inactive','failed'),'installation_scheduling_reactivated')
            expected['ActiveState']=row['ActiveState']
        if unit in quiesced:
            require(row['ActiveState'] in ('inactive','failed'),'handoff_previous_supervisor_reactivated')
            expected['ActiveState']=row['ActiveState']
        if overrides and unit in overrides:expected.update(Restart='on-failure',Triggers='')
        require(row==expected,'installation_original_manager_settings_drift')
    expected=[]
    for row in source['containers']:
        row=dict(row)
        if row['disposition']=='pause':row.update(restart_policy='no',running=False,process_birth=None)
        expected.append(row)
    require(actual['containers']==expected,'installation_original_container_policy_drift')
    scheduling(proposal)
    require(retained(source)==source['retained_services'],'installation_retained_service_changed')


def inspect_control(action,proposal,journal):
    source=proposal['identities']
    if action=='inhibit_scheduling': return dict(verified=True,observed=scheduling(proposal,include_containers=False))
    if action=='inhibit_containers':
        rows=[]
        for row in source['containers']:
            actual=json.loads(docker(source,['inspect',row['id']]))[0]
            require(actual['Id']==row['id'] and actual['Image']==row['image'] and actual['Created']==row['created_at'] and
                    actual['State']['StartedAt']==row['started_at'],'installed_container_birth_changed')
            if row['disposition']=='pause':
                require(actual['State']['Running'] is False and actual['HostConfig']['RestartPolicy']['Name']=='no','installed_container_inhibition_failed')
            rows.append(dict(id=actual['Id'],running=actual['State']['Running'],restart_policy=actual['HostConfig']['RestartPolicy']['Name']))
        return dict(verified=True,observed=rows)
    if action=='prerequisites': return dict(verified=True,observed=prerequisites(source,journal))
    if action=='verify_release':
        from deploy.workload_dependencies import installed_inventory
        release=Path(source['resources']['release']['path'])
        require(verify(release/'bundle',source['manifest'])==proposal['manifest_sha256'],'installed_frozen_release_changed')
        from deploy.workload_artifacts import verify_installed_tools
        verify_installed_tools(release,source['manifest'])
        verify_images(source)
        require(installed_inventory(release/'.venv',interpreter=source['recipe']['interpreter']['path'])==source['recipe']['installed_files'],'installed_dependency_files_changed')
        from deploy.workload_dependencies import entrypoint_import_command
        command,modules=entrypoint_import_command(release/'bundle',release/'.venv')
        require(json.loads(run(command))==modules,'installed_entrypoint_import_failed')
        # Imports may not mutate the approved bundle, toolchain or environment.
        verify_installed_tools(release,source['manifest'])
        require(installed_inventory(release/'.venv',interpreter=source['recipe']['interpreter']['path'])==source['recipe']['installed_files'],
                'installed_dependency_import_drift')
        require(verify(release/'bundle',source['manifest'])==proposal['manifest_sha256'],'installed_import_source_drift')
        from deploy.workload_configuration import hashes,measured_resources,verify_private_artifacts
        verify_private_artifacts(source)
        expected=hashes(source,measured_resources(source))
        for role,row in source['manifest']['configurations'].items():
            require(identity(row['path']).get('sha256')==expected[role],'installed_configuration_changed')
        return dict(verified=True,manifest_sha256=proposal['manifest_sha256'])
    if action=='verify_cleanup':
        gate=Path(source['installation']['gate_root']); path=gate/'workload.json'
        if not journal.outcome('install:start_paused'):
            require(identity(path)['state']=='absent','installed_unacknowledged_runtime_state_preserve')
            root=Path(source['installation']['heavy_path']);actual=identity(root)
            previous=source['resources']['delegation']
            if actual['state']=='observed':
                prerequisite=journal.outcome('install:prerequisites')
                expected=(prerequisite['observed']['observed']['delegation'] if prerequisite else previous)
                require(expected.get('state')=='observed' and all(actual[k]==expected[k] for k in ('device','inode')),
                        'installed_unacknowledged_delegation_preserve')
                require(values(root/'cgroup.events')['populated']==0,'installed_owned_cgroup_populated')
            else:require(previous['state']=='proposed','installed_delegation_disappeared')
            scheduling(proposal)
            return dict(verified=True,phase='not_started',paused=True,supervisor_never_started=True)
        state=json.loads(regular(path.parent,path.name)[0])
        require(state['paused'] is True and state['phase'] in ('cleaned','complete'),
                'installed_cleanup_or_transaction_unresolved')
        root=Path(source['installation']['heavy_path'])
        require(values(root/'cgroup.events')['populated']==0,'installed_owned_cgroup_populated')
        scheduling(proposal)
        return dict(verified=True,phase=state['phase'],paused=True)
    if action=='verify_rollback':
        verify_rollback(source)
        require(identity(source['recipe']['activation_pointer']).get('target')==source['rollback']['target'], 'installed_rollback_selection_changed')
        scheduling(proposal)
        require(retained(source)==source['retained_services'],'installed_retained_service_changed')
        return dict(verified=True,paused=True)
    require(False,'installed_control_unknown')


def collect(proposal, *, now=None):
    """Measure a complete installed record from Linux, never from fixture births."""
    import time
    from deploy.workload_artifacts import verify_installed_tools
    verify_installed_tools(proposal['identities']['resources']['release']['path'],proposal['identities']['manifest'])
    from copy import deepcopy
    from deploy.workload_v3 import INSTALLED,sha,validate_proposal
    from deploy.workload_dependencies import installed_inventory
    from mldsafail.evaluator.native_workload import NativeRuntime,private_json
    from mldsafail.evaluator.workload_client import WorkloadClient
    validate_proposal(proposal); source=proposal['identities']
    verify_supervisor_enable(proposal)
    from deploy.workload_installation import Journal,LinuxBackend,private
    proposal_raw,loaded=private(source['recipe']['proposal_path'])
    require(loaded==proposal,'installed_proposal_changed')
    journal=Journal(source['recipe']['journal_root'],digest(proposal_raw));backend=LinuxBackend(proposal)
    require(backend.installed_units_selected(journal),'installed_supervisor_unit_transition_missing')
    replacements,overrides=backend.unit_transitions(journal)
    from deploy.workload_registry import generated_supervisor,bound_files
    generated_supervisor(proposal,run)
    bound_files(source,run,replacements=replacements)
    from deploy.workload_configuration import verify_private_artifacts
    verify_private_artifacts(source)
    require(source['origin'] in ('local_linux','host_observation'),'installed_synthetic_source_forbidden')
    native_row=source['manifest']['configurations']['native']
    native=private_json(native_row['path'])
    from deploy.workload_configuration import hashes,measured_resources
    expected_configuration_hashes=hashes(source,measured_resources(source))
    require(identity(native_row['path']).get('sha256')==expected_configuration_hashes['native'],'installed_native_configuration_changed')
    runtime=NativeRuntime(native); actual_identity=runtime.identity()
    require(actual_identity==source['host']['runtime_identity'],'installed_daemon_identity_changed')
    uid_map=[[int(v) for v in line.split()] for line in Path('/proc/'+str(actual_identity['daemon_birth']['pid'])+'/uid_map').read_text().splitlines()]
    require(uid_map==source['uid_mapping']['uid_map'],'installed_actual_rootless_mapping_changed')
    measured=measured_resources(source)
    resources={}
    for name,previous in measured.items():
        current=identity(previous['path']); row=deepcopy(previous)
        row.pop('creation',None);row.pop('preserve',None)
        row.update({key:current[key] for key in ('state','device','inode') if key in current})
        if name=='activation': row['target']=current.get('target')
        if name=='delegation':
            row['controllers']=(Path(previous['path'])/'cgroup.controllers').read_text().split()
            row['enforced_limits']={key:(Path(previous['path'])/key).read_text().strip() for key in ('memory.max','memory.swap.max','pids.max','cpu.max')}
            for parent in row['ancestors']:
                observed_parent=cgroup_observation(parent['path'])
                parent.update({key:observed_parent[key] for key in ('controllers','writable','limits','subtree_control','control_permissions')})
        if name=='output':
            measured=mount(previous['path']);row['mount_id']=measured['mount_id']
            require(set(measured['mount_options'])>=set(previous['mount_options']),'installed_mount_options_changed')
        resources[name]=row
    supervisor_path=Path(source['installation']['gate_root'])/'socket.json'
    supervisor_record=private_json(supervisor_path); process=supervisor_record['process']
    require(process_birth(process['pid'])==process,'installed_supervisor_birth_changed')
    pid=process['pid']; cg=Path('/proc/'+str(pid)+'/cgroup').read_text().strip()
    require(cg.startswith('0::/'),'installed_supervisor_not_cgroup_v2')
    sock=identity(source['resources']['socket']['path'])
    require(sock['mode']==0o600 and sock['uid']==source['host']['uid'] and
            (sock['device'],sock['inode'])==(supervisor_record['device'],supervisor_record['inode']),
            'installed_socket_birth_or_permissions_changed')
    unit_hashes={}
    for name,contents in proposal['units'].items():
        path=Path(source['installation']['unit_directory'])/name
        data,_=regular(path.parent,path.name);unit_hashes[name]=digest(data)
    verify_images(source)
    gate=WorkloadClient(source['resources']['socket']['path'],Path(source['recipe']['journal_root'])/'installed-client')
    state=gate.status()
    from deploy.workload_registry import observe as observe_registry
    observe_registry(source,run,installed_units=True)
    from deploy.workload_registry import references
    references(source,run,inhibited=True,overrides=overrides,quiesced=backend.quiesced_units(journal))
    prerequisites(source,journal)
    record=dict(schema=INSTALLED,origin=source['origin'],captured_at=time.time() if now is None else now,
        proposal_sha256=sha(proposal),host=deepcopy(source['host']),resources=resources,
        release_sha256=verify(Path(source['resources']['release']['path'])/'bundle',source['manifest']),
        configuration_hashes={role:identity(row['path']).get('sha256') for role,row in source['manifest']['configurations'].items()},
        dependency_files=installed_inventory(Path(source['resources']['release']['path'])/'.venv',interpreter=source['recipe']['interpreter']['path']),
        units=unit_hashes,uid_mapping=deepcopy(source['uid_mapping']),paused=state['paused'],
        retained_services=retained(source),scheduling=scheduling(proposal),
        supervisor=dict(process,boot_id=source['host']['boot_id'],uid=Path('/proc/'+str(pid)).stat().st_uid,
                        cgroup='/sys/fs/cgroup'+cg.removeprefix('0::')))
    return record


def schema_fingerprint(source):
    """Read-only schema dump; never migrations, row writes or schema downgrade."""
    row=source['rollback']['schema']
    raw=docker(source,['exec','--user','postgres',row['container_id'],'pg_dump','--schema-only','--no-owner','--no-privileges',
                       '--username',row['username'],'--dbname',row['database']])
    stable=b'\n'.join(line for line in raw.splitlines() if line.strip() and not line.startswith((b'--',b'\\restrict ',b'\\unrestrict ')))+b'\n'
    return digest(stable)


def rollback_private_files(rollback):
    records={};controller=None
    for role,row in rollback['manifest']['configurations'].items():
        path=Path(row['path']);data,mode=regular(path.parent,path.name);actual=identity(path)
        require(mode==0o600 and actual['uid']==os.getuid() and
                digest(data)==rollback['configuration_hashes'][role],
                'installed_rollback_configuration_changed')
        records[role]=dict(actual,bytes=len(data))
        if role=='controller':controller=json.loads(data)
    require(controller is not None,'installed_rollback_controller_missing')
    key=Path(controller['signing_key']);data,mode=regular(key.parent,key.name);actual=identity(key)
    require(rollback['manifest'].get('private_artifacts',{}).get('signing_key')==dict(sha256=digest(data),bytes=len(data)) and
            mode==0o600 and actual['uid']==os.getuid() and 32<=len(data)<=4096,
            'installed_rollback_private_artifact_changed')
    return dict(configurations=records,signing_key=dict(actual,bytes=len(data)))


def observe_rollback(source):
    """Verify actual previous bytes and imports before describing compatibility.

    Compatibility is restricted to selecting the preserved release with the
    unchanged schema and computation inhibited. It never authorizes starting an
    older coordinator or downgrading a schema.
    """
    import sys
    from deploy.workload_dependencies import installed_inventory,entrypoint_import_command
    from deploy.workload_release import canonical
    require(sys.platform=='linux' and source['origin'] in ('local_linux','host_observation'),
            'installed_rollback_native_observation_required')
    import socket
    require(os.uname().machine=='x86_64' and socket.gethostname()==source['host']['hostname'] and
            os.getuid()==source['host']['uid'] and
            Path('/proc/sys/kernel/random/boot_id').read_text().strip()==source['host']['boot_id'],
            'installed_rollback_observation_wrong_host')
    rollback=source['rollback'];root=Path(rollback['release'])
    require(verify(root/'bundle',rollback['manifest'])==rollback['manifest_sha256'],'installed_rollback_manifest_changed')
    from deploy.workload_artifacts import verify_installed_tools
    verify_installed_tools(root,rollback['manifest'])
    python=root/'.venv/bin/python'
    require(python.is_symlink() and python.resolve().is_file() and digest(python.resolve().read_bytes())==rollback['python_sha256'],
            'installed_rollback_interpreter_changed')
    require(installed_inventory(root/'.venv',interpreter=python.resolve())==rollback['installed_files'],
            'installed_rollback_dependencies_changed')
    private_files=rollback_private_files(rollback)
    row=json.loads(docker(source,['image','inspect',rollback['coordinator_image']]))[0]
    require(row['Id']==rollback['coordinator_image'],'installed_rollback_image_changed')
    verify_images(source,rollback['manifest'])
    require(schema_fingerprint(source)==rollback['schema_sha256'],'installed_schema_changed_rollback_forbidden')
    command,modules=entrypoint_import_command(root/'bundle',root/'.venv',release_files=rollback['manifest']['files'])
    require(json.loads(run(command,timeout=35))==modules,'installed_rollback_entrypoint_import_failed')
    verify_installed_tools(root,rollback['manifest'])
    require(installed_inventory(root/'.venv',interpreter=python.resolve())==rollback['installed_files'] and
            verify(root/'bundle',rollback['manifest'])==rollback['manifest_sha256'],
            'installed_rollback_import_drift')
    require(rollback_private_files(rollback)==private_files,'installed_rollback_private_import_drift')
    return dict(schema='mldsafail.workload-rollback-compatibility.v3',origin=source['origin'],
        hostname=source['host']['hostname'],release=rollback['release'],
        manifest_sha256=rollback['manifest_sha256'],
        installed_files_sha256=digest(canonical(rollback['installed_files'])),
        configuration_hashes=rollback['configuration_hashes'],python_sha256=rollback['python_sha256'],
        private_files=private_files,
        coordinator_image=rollback['coordinator_image'],worker_image=rollback['manifest']['worker_environment']['image_id'],
        database_schema_sha256=rollback['schema_sha256'],database=rollback['schema'],entrypoints=modules,
        compatibility='unchanged_schema_and_inhibited_release_selection',coordinator_start_authorized=False)


def verify_rollback(source):
    expected=observe_rollback(source)
    rollback=source['rollback']
    receipt=Path(rollback['compatibility_receipt_path'])
    raw,_=regular(receipt.parent,receipt.name)
    require(digest(raw)==rollback['compatibility_receipt_sha256'],
            'installed_rollback_compatibility_receipt_changed')
    require(json.loads(raw)==expected,'installed_rollback_compatibility_binding_changed')
    return True


def original_settings(source):
    """Fresh raw manager settings and container policies, before inhibition."""
    from deploy.workload_preparation import manager_prefix
    from deploy.workload_schedule_v3 import unit_name
    units={};containers=[]
    for unit,owner in source['scheduling']['owners'].items():
        raw=run([*manager_prefix(owner,source['host']['uid']),'show',unit_name(unit,owner),
                 '--property=ActiveState,UnitFileState,Restart,Triggers']).decode()
        observed=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
        units[unit]={key:observed.get(key,'') for key in ('ActiveState','UnitFileState','Restart','Triggers')}
        units[unit]['Triggers']=' '.join(sorted(units[unit]['Triggers'].split()))
    identifiers=docker(source,['ps','-aq','--no-trunc']).decode().split()
    require(sorted(identifiers)==sorted(row['id'] for row in source['containers']),'installed_container_inventory_changed')
    for row in source['containers']:
        actual=json.loads(docker(source,['inspect',row['id']]))[0]
        containers.append(dict(id=actual['Id'],daemon_id=source['host']['daemon_id'],owner_uid=source['host']['uid'],
            restart_policy=actual['HostConfig']['RestartPolicy']['Name'],running=actual['State']['Running'],disposition=row['disposition'],
            image=actual['Image'],created_at=actual['Created'],started_at=actual['State']['StartedAt'],
            process_birth=process_birth(actual['State']['Pid']) if actual['State']['Running'] else None))
    return dict(manager_settings=units,containers=containers)
