"""Complete synthetic V3 contract fixture; never native host evidence."""
from copy import deepcopy
from pathlib import Path

from deploy.workload_release import canonical, digest
from deploy.workload_units import render_v3 as render
from deploy.workload_v3 import BOOTSTRAP, INSTALLED, sha


def inspection():
    installation=dict(python='/srv/v3/release/.venv/bin/python',release='/srv/v3/release/bundle',
        configuration='/srv/v3/release/config/supervisor.json',gate_root='/srv/v3/gate',
        heavy_path='/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/mldsafail.slice/mldsafail-heavy.slice',memory_ceiling=2*1024**3,
        uid=1000,unit_directory='/home/operator/.config/systemd/user')
    units=render(installation)
    file=lambda data:dict(sha256=digest(data),bytes=len(data),mode=0o600)
    manifest=dict(schema='mldsafail.workload-frozen-release.v3',benchmark_version='0.5.0',
        interpreter=dict(implementation='cpython',version='3.12',platform='linux',architecture='x86_64',minimum_glibc='2.28'),
        files={'uv.lock':file(b'synthetic lock'),'offline/fixture-1.0-py3-none-any.whl':file(b'synthetic wheel')},
        dependencies=['offline/fixture-1.0-py3-none-any.whl'],units=['generated/'+name for name in units],
        configurations={role:dict(path='/srv/v3/release/config/'+role+'.json',sha256=digest(canonical(dict(fixture_role=role))))
                        for role in ('supervisor','native','controller')},
        coordinator_image='sha256:'+'b'*64,evaluator_fingerprint='c'*64,
        worker_environment=dict(image_id='sha256:'+'d'*64,trusted_fingerprint='e'*64,artifacts={},host={}))
    manifest['files'].update({'generated/'+name:file(data.encode()) for name,data in units.items()})
    proposed=lambda path:dict(state='proposed',path=path,creation='exclusive_owned_creation',preserve='current_and_rollback')
    observed=lambda path,inode:dict(state='observed',path=path,device=1,inode=inode)
    delegate=proposed(installation['heavy_path'])
    manager='/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service'
    ancestors=[dict(proposed(manager+'/mldsafail.slice'),writable=True,controllers=['cpu','memory','pids'],retained_service_ancestor=False)]
    parent=Path(manager)
    while True:
        ancestors.append(dict(observed(str(parent),50+len(ancestors)),writable=str(parent)==manager,
                              controllers=['cpu','memory','pids'],retained_service_ancestor=str(parent)!=manager,
                              subtree_control=['cpu','memory','pids'],
                              control_permissions={name:dict(uid=1000 if str(parent)==manager else 0,gid=1000 if str(parent)==manager else 0,
                                  mode=0o644,writable=str(parent)==manager) for name in ('cgroup.procs','cgroup.subtree_control')},
                              limits={name:None for name in ('memory.max','memory.high','memory.swap.max','pids.max','cpu.max','cpuset.cpus.effective')}))
        if str(parent)=='/sys/fs/cgroup':break
        parent=parent.parent
    delegate.update(controllers=['cpu','memory','pids'],ancestors=ancestors)
    scheduling=dict(unclassified=0,references_open=0,receipt_sha256='f'*64,units=['compute.service'],
        computational_units=['compute.service'],owners={'compute.service':dict(manager='user',account='operator',
            uid=1000,restart='always',triggers=[],disposition='pause',active=True,enabled=True,masked=False)})
    result=dict(schema=BOOTSTRAP,origin='synthetic',captured_at=1000,
        host=dict(hostname='synthetic',uid=1000,boot_id='synthetic-boot',daemon_id='synthetic-daemon',user_manager=observed(manager,51),runtime_identity=dict(
            boot_id='synthetic-boot',daemon_id='synthetic-daemon',daemon_mode=dict(driver='systemd',version='2',rootless=True),
            daemon_birth=dict(pid=200,start_ticks=300),daemon_executable=dict(device=1,inode=30),
            socket_birth=dict(path='/run/user/1000/docker.sock',device=1,inode=31))),
        installation=installation,manifest=manifest,
        recipe=dict(bundle_root='/srv/v3/frozen',artifact_root='/srv/v3/artifacts',
            interpreter=dict(path='/srv/v3/artifacts/python',sha256='1'*64,bytes=100,version='3.12.10'),
            installer=dict(path='/srv/v3/artifacts/uv',sha256='2'*64,bytes=100,version='0.13.1'),
            dependency_plan=dict(lock_sha256=manifest['files']['uv.lock']['sha256'],
                wheels={name:manifest['files'][name]['sha256'] for name in manifest['dependencies']},
                requirements_sha256='3'*64,target='cpython-3.12-linux-x86_64-glibc2.28'),
            installed_files={'bin/fixture':dict(sha256='4'*64,bytes=100,mode=0o755)},
            configuration_sources={role:'/srv/v3/private/'+role+'.json' for role in manifest['configurations']},
            configuration_templates={role:canonical(dict(fixture_role=role)).hex() for role in manifest['configurations']},
            activation_pointer='/srv/v3/current',proposal_path='/srv/v3/proposal.json',journal_root='/srv/v3/journal'),
        resources=dict(release=proposed('/srv/v3/release'),socket=proposed('/srv/v3/gate/supervisor.sock'),
            delegation=delegate,output=dict(observed('/srv/v3/output',7),filesystem='ext4',bytes=1024**3,
                mount_options=['noexec','nosuid','nodev'],mount_id=9),
            activation=dict(observed('/srv/v3/current',8),target='/srv/v3/previous')),
        scheduling=scheduling,unit_directories={'user:1000':installation['unit_directory']},
        permission_root='/srv/v3/permissions',containers=[],
        inventory=dict(receipt_sha256='f'*64,raw_sha256='0'*64,errors=0,truncations=0,unknown_owners=0,unresolved_references=0,original_files={'/home/operator/.config/systemd/user/compute.service':'c'*64},
            manager_settings={'compute.service':dict(ActiveState='active',UnitFileState='enabled',Restart='always',Triggers='')}),
        admission=dict(memory_available=2*1024**3,backing_free=7*1024**3),
        rollback=dict(release='/srv/v3/previous',target='/srv/v3/previous',manifest_sha256='5'*64,
            configuration_hashes={role:'6'*64 for role in manifest['configurations']},coordinator_image='sha256:'+'7'*64,
            schema_sha256='8'*64,installed_schema_sha256='8'*64,compatibility_receipt_sha256='9'*64,verified_files=True),
        retained_services={role:dict(id=str(index)*64,image='sha256:'+'a'*64,started_at='synthetic-birth',running=True)
                           for index,role in enumerate(('web','database','proxy'),1)},
        uid_mapping=dict(coordinator_container_uid=0,supervisor_host_uid=1000,uid_map=[[0,1000,1],[1,100000,65536]],receipt_sha256='b'*64))

    previous=deepcopy(manifest)
    previous['coordinator_image']=result['rollback']['coordinator_image']
    result['rollback'].update(manifest=previous,manifest_sha256=sha(previous),
        installed_files={'bin/previous':dict(sha256='a'*64,bytes=100,mode=0o700)},python_sha256='b'*64,
        compatibility_receipt_path='/srv/v3/private/compatibility.json',
        schema=dict(container_id=result['retained_services']['database']['id'],database='synthetic',username='postgres'))
    return result


def installed(proposal):
    source=proposal['identities']; resources=deepcopy(source['resources'])
    for index,row in enumerate(resources.values(),20):
        if row['state']=='proposed':
            row.pop('creation'); row.pop('preserve'); row.update(state='observed',device=1,inode=index)
    for index,parent in enumerate(resources['delegation']['ancestors'],70):
        if parent['state']=='proposed':
            parent.pop('creation');parent.pop('preserve');parent.update(state='observed',device=1,inode=index)
    resources['delegation']['enforced_limits']={'memory.max':str(source['installation']['memory_ceiling']),'memory.swap.max':'0','pids.max':'448','cpu.max':'100000 100000'}
    resources['activation'].update(inode=40,target=resources['release']['path'])
    return dict(schema=INSTALLED,origin='synthetic',captured_at=1100,proposal_sha256=sha(proposal),host=deepcopy(source['host']),
        resources=resources,release_sha256=proposal['manifest_sha256'],
        configuration_hashes={role:row['sha256'] for role,row in source['manifest']['configurations'].items()},
        dependency_files=deepcopy(source['recipe']['installed_files']),
        units={name:digest(data.encode()) for name,data in proposal['units'].items()},
        uid_mapping=deepcopy(source['uid_mapping']),paused=True,retained_services=deepcopy(source['retained_services']),
        scheduling=dict(permission_files_absent=True,computational_units_stopped=True,computational_containers_stopped=True,
            restart_policies_inhibited=True,dropin_hashes={row['path']:digest(row['contents'].encode()) for row in proposal['scheduling']['resources']}),
        supervisor=dict(pid=100,start_ticks=1000,boot_id=source['host']['boot_id'],uid=1000,cgroup='/sys/fs/cgroup/user.slice/app.slice'))
